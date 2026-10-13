"""Convert a SpellSpeak Audience release to Core ML.

    uv run convert.py                      # rc2.1's 16-bit graphs from Hugging Face -> build/rc2.1/
    uv run convert.py --model-dir DIR      # graphs already on disk
    uv run convert.py --precision fp32     # the full-precision graphs: twice the size, the reference weights

The release's two ONNX graphs become two Core ML models (ML Program, iOS 18 and macOS 15 on):

- `AudienceEncoder.mlpackage` encodes one text: a card, or a line with the line before it. Its inputs are fixed at
  96 tokens; shorter texts are padded and masked, which leaves every real token's output unchanged.
- `AudienceHead.mlpackage` scores the people from the line and their cards. It holds one function per number of
  people, `people_1` to `people_8`, sharing one copy of the weights: the head's `unclear` and `group` read everyone
  present, so the count is part of the shape. The line's token states are padded to 64 rows with `cur` 0 and the
  cards to 96 with `card_mask` 0, which leaves the answer unchanged.

Weights keep the source graphs' values: the 16-bit graphs' weights are stored in 16 bits and widened to 32 bits when
the model loads, as ONNX Runtime does with them. Everything is computed in 32 bits. Computing in 16 bits instead turns
the encoder's padded attention rows to NaN on the CPU and moves its outputs by up to 0.14 elsewhere, so it is not
offered. `check.py` compares the result with ONNX Runtime.

onnx2torch carries the graphs into PyTorch, which coremltools converts. Five of its converters are replaced
(`patch_onnx2torch`): two operators it lacks, the axis it gets wrong in Flatten, an alias coremltools lacks, and Expand,
which it writes as a product with a tensor of ones; Core ML's CPU sums such a product wrongly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
HF_REPO = "spellspeak/audience"
ENCODER_LEN = 96  # the card length the release reads (config `card_len`); lines read 64
HEAD_LINE_LEN = 64  # config `line_len`
MAX_PEOPLE = 8
PAD_ID = 50283  # [PAD]: padded positions are masked, so any id would do
GRAPHS = {"fp16": ("encoder_fp16.onnx", "head_fp16.onnx"), "fp32": ("encoder.onnx", "head.onnx")}
HEAD_INPUTS = ["q", "h", "hp", "cur", "g", "gp", "card_mask", "pfeat", "lfeat"]


def patch_onnx2torch() -> None:
    """Replace the onnx2torch converters these graphs need fixed."""
    import torch
    from onnx import defs
    from onnx2torch.node_converters.registry import _CONVERTER_REGISTRY, OperationDescription
    from onnx2torch.utils.common import (
        OnnxToTorchModule,
        OperationConverterResult,
        onnx_mapping_from_node,
    )
    from torch import nn

    class Compare(nn.Module, OnnxToTorchModule):
        def __init__(self, fn):
            super().__init__()
            self.fn = fn

        def forward(self, a, b):
            return self.fn(a, b)

    class Flatten(nn.Module, OnnxToTorchModule):
        """ONNX Flatten: (product of dims before `axis`, product of the rest), also when axis is the rank."""

        def __init__(self, axis: int):
            super().__init__()
            self.axis = axis

        def forward(self, x):
            axis = self.axis if self.axis >= 0 else x.dim() + self.axis
            if axis == 0:
                return x.reshape(1, -1)
            y = torch.flatten(x, 0, axis - 1)
            return y.unsqueeze(-1) if axis == x.dim() else torch.flatten(y, 1)

    class Expand(nn.Module, OnnxToTorchModule):
        """ONNX Expand as a broadcast, which coremltools turns into a tile."""

        def forward(self, x, shape):
            return x.expand(torch.broadcast_shapes(x.shape, tuple(int(d) for d in shape)))

    def register(op: str, version: int, make) -> None:
        def converter(node, graph):
            return OperationConverterResult(torch_module=make(node), onnx_mapping=onnx_mapping_from_node(node))

        _CONVERTER_REGISTRY[OperationDescription(domain=defs.ONNX_DOMAIN, operation_type=op, version=version)] = converter

    register("GreaterOrEqual", 16, lambda node: Compare(torch.ge))
    register("LessOrEqual", 16, lambda node: Compare(torch.le))
    register("Less", 13, lambda node: Compare(torch.lt))  # coremltools converts aten::lt, not its alias aten::less
    register("Flatten", 13, lambda node: Flatten(node.attributes.get("axis", 1)))
    register("Expand", 13, lambda node: Expand())


def prepare_graph(source: pathlib.Path, out: pathlib.Path) -> None:
    """The graph as onnx2torch can read it, computing exactly what the source does: 16-bit weights widened to 32 bits
    ahead of time (in place of the graph's own casts), Clip bounds as initializers, no empty trailing inputs."""
    import onnx
    from onnx import TensorProto, numpy_helper

    model = onnx.load(source)
    graph = model.graph
    widened = set()
    for init in graph.initializer:
        if init.data_type == TensorProto.FLOAT16:
            init.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(init).astype(np.float32), init.name))
            widened.add(init.name)
    for node in graph.node:
        if node.op_type == "Constant":
            for attr in node.attribute:
                if attr.name == "value" and attr.t.data_type == TensorProto.FLOAT16:
                    attr.t.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(attr.t).astype(np.float32)))
                    widened.add(node.output[0])
    for node in graph.node:
        if node.op_type == "Cast" and node.input[0] in widened:
            if next(a.i for a in node.attribute if a.name == "to") == TensorProto.FLOAT:
                node.op_type = "Identity"
                del node.attribute[:]
    producers = {o: n for n in graph.node for o in n.output}
    for node in list(graph.node):
        if node.op_type != "Clip":
            continue
        while node.input and not node.input[-1]:
            node.input.pop()
        for name in node.input[1:]:
            const = producers.get(name)
            if const is not None and const.op_type == "Constant" and const in graph.node:
                value = next(a.t for a in const.attribute if a.name == "value")
                graph.initializer.append(numpy_helper.from_array(numpy_helper.to_array(value), name))
                graph.node.remove(const)
    onnx.checker.check_model(model)
    onnx.save(model, out)


def store_16_bit(program) -> int:
    """Store each weight whose value is exact in 16 bits that way, widened to 32 bits when the model loads."""
    from coremltools.converters.mil import Builder as mb
    from coremltools.converters.mil.mil import types
    from coremltools.converters.mil.mil.scope import ScopeInfo

    stored = 0
    for fn in program.functions.values():
        with fn:
            for op in list(fn.operations):
                if op.op_type != "const" or op.outputs[0].dtype != types.fp32:
                    continue
                value = op.outputs[0].val
                if not isinstance(value, np.ndarray) or value.size < 1024:
                    continue
                with np.errstate(over="ignore"):
                    half = value.astype(np.float16)
                if not np.array_equal(half.astype(np.float32), value):
                    continue
                with mb.scope(*[ScopeInfo(source=k, data=v) for k, v in op.scopes.items()]):
                    widened = mb.constexpr_cast(source_val=half, output_dtype="fp32", before_op=op)
                fn.replace_uses_of_var_after_op(anchor_op=op, old_var=op.outputs[0], new_var=widened)
                fn.remove_ops([op])
                stored += 1
    return stored


def to_core_ml(traced, inputs, outputs):
    import coremltools as ct

    program = ct.convert(traced, inputs=inputs, outputs=outputs, compute_precision=ct.precision.FLOAT32,
                         minimum_deployment_target=ct.target.iOS18, convert_to="milinternal")
    store_16_bit(program)
    return ct.convert(program, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                      compute_precision=ct.precision.FLOAT32)


def describe(model, release: str, what: str) -> None:
    model.author = "SpellSpeak"
    model.license = "Apache-2.0 (base model jhu-clsp/ettin-encoder-32m: MIT)"
    model.short_description = f"SpellSpeak Audience {release}: {what}"
    model.version = release


def convert_encoder(graph: pathlib.Path, out: pathlib.Path, release: str) -> None:
    import coremltools as ct
    import torch
    from onnx2torch import convert

    class Encoder(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, ids, mask):
            return self.inner(ids.long(), mask.long())

    ids = torch.full((1, ENCODER_LEN), PAD_ID, dtype=torch.int32)
    mask = torch.zeros((1, ENCODER_LEN), dtype=torch.int32)
    ids[0, :12], mask[0, :12] = torch.arange(100, 112), 1
    with torch.no_grad():
        traced = torch.jit.trace(Encoder(convert(graph).eval()).eval(), (ids, mask), check_trace=False)
    model = to_core_ml(
        traced,
        [ct.TensorType(name="ids", shape=(1, ENCODER_LEN), dtype=np.int32),
         ct.TensorType(name="mask", shape=(1, ENCODER_LEN), dtype=np.int32)],
        [ct.TensorType(name="h"), ct.TensorType(name="hp"), ct.TensorType(name="pooled")])
    describe(model, release, "the encoder, one card or line per call (96 tokens, padded and masked)")
    model.input_description["ids"] = "Token ids, padded to 96 with [PAD] (50283)"
    model.input_description["mask"] = "1 for each real token, 0 for padding"
    model.output_description["h"] = "Token states (1, 96, 384)"
    model.output_description["hp"] = "Projected token states (1, 96, 128)"
    model.output_description["pooled"] = "The text's vector (1, 384): the head's q when the text is the line"
    model.save(out)


def convert_head(graph: pathlib.Path, out: pathlib.Path, release: str) -> None:
    import coremltools as ct
    import torch
    from onnx2torch import convert

    class Head(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, q, h, hp, cur, g, gp, card_mask, pfeat, lfeat):
            return self.inner(q, h, hp, cur, g, gp, card_mask.long(), pfeat, lfeat)

    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for people in range(1, MAX_PEOPLE + 1):
            shapes = {"q": (1, 384), "h": (1, HEAD_LINE_LEN, 384), "hp": (1, HEAD_LINE_LEN, 128), "cur": (1, HEAD_LINE_LEN),
                      "g": (people, ENCODER_LEN, 384), "gp": (people, ENCODER_LEN, 128), "card_mask": (people, ENCODER_LEN),
                      "pfeat": (people, 26), "lfeat": (1, 18)}
            example = {n: torch.tensor(rng.normal(size=s).astype(np.float32)) for n, s in shapes.items()}
            example["card_mask"] = torch.ones(shapes["card_mask"], dtype=torch.int32)
            # A fresh module for each trace: some onnx2torch modules keep state from their first run.
            with torch.no_grad():
                traced = torch.jit.trace(Head(convert(graph).eval()).eval(), tuple(example[n] for n in HEAD_INPUTS),
                                         check_trace=False)
            inputs = [ct.TensorType(name=n, shape=shapes[n], dtype=np.int32 if n == "card_mask" else np.float32)
                      for n in HEAD_INPUTS]
            model = to_core_ml(traced, inputs, [ct.TensorType(name="person"), ct.TensorType(name="unclear"),
                                                ct.TensorType(name="group")])
            describe(model, release, "the head: one function per number of people, people_1 to people_8")
            path = pathlib.Path(tmp) / f"people_{people}.mlpackage"
            model.save(path)
            parts.append(path)
        functions = ct.utils.MultiFunctionDescriptor()
        for people, path in enumerate(parts, start=1):
            functions.add_function(str(path), src_function_name="main", target_function_name=f"people_{people}")
        functions.default_function_name = "people_2"
        if out.exists():
            shutil.rmtree(out)
        ct.utils.save_multifunction(functions, str(out))


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(path: pathlib.Path) -> str:
    """One digest over every file in a package, by relative path."""
    digest = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(f.relative_to(path)).encode())
        digest.update(sha256(f).encode())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a SpellSpeak Audience release to Core ML.")
    parser.add_argument("--release", default="rc2.1", help="the release tag on Hugging Face (default rc2.1)")
    parser.add_argument("--model-dir", type=pathlib.Path, help="a folder holding the release's model files")
    parser.add_argument("--precision", choices=GRAPHS, default="fp16",
                        help="which graphs to convert: fp16 (the default: 66 MB) or fp32 (twice the size)")
    parser.add_argument("--out", type=pathlib.Path, help="where to write the models (default build/<release>)")
    args = parser.parse_args()
    encoder_file, head_file = GRAPHS[args.precision]
    needed = [encoder_file, head_file, "tokenizer.json", "config.json"]
    source = args.model_dir
    if source is None:
        from huggingface_hub import snapshot_download

        source = pathlib.Path(snapshot_download(HF_REPO, revision=args.release, allow_patterns=needed))
    missing = [f for f in needed if not (source / f).exists()]
    if missing:
        sys.exit(f"{source} lacks {', '.join(missing)}")
    config = json.loads((source / "config.json").read_text())
    if (config.get("render_version"), config.get("card_len"), config.get("line_len")) != ("addressee-tt-0.6", ENCODER_LEN, HEAD_LINE_LEN):
        sys.exit(f"this converter reads addressee-tt-0.6 models with card_len {ENCODER_LEN} and line_len {HEAD_LINE_LEN}")
    out = args.out or HERE / "build" / args.release
    out.mkdir(parents=True, exist_ok=True)

    from importlib.metadata import version

    patch_onnx2torch()
    with tempfile.TemporaryDirectory() as tmp:
        encoder_graph, head_graph = pathlib.Path(tmp) / "encoder.onnx", pathlib.Path(tmp) / "head.onnx"
        prepare_graph(source / encoder_file, encoder_graph)
        prepare_graph(source / head_file, head_graph)
        convert_encoder(encoder_graph, out / "AudienceEncoder.mlpackage", args.release)
        convert_head(head_graph, out / "AudienceHead.mlpackage", args.release)
    for name in ("tokenizer.json", "config.json"):
        shutil.copyfile(source / name, out / name)
    manifest = {
        "release": args.release,
        "precision": args.precision,
        "source": {name: sha256(source / name) for name in needed},
        "converted_with": {name: version(name) for name in ("coremltools", "torch", "onnx2torch", "onnx")},
        "minimum_deployment_target": "iOS 18, macOS 15",
        "compute": "float32 (weights stored as in the source graphs)",
        "encoder": {"tokens": ENCODER_LEN, "pad_id": PAD_ID},
        "head": {"line_tokens": HEAD_LINE_LEN, "card_tokens": ENCODER_LEN,
                 "functions": {str(n): f"people_{n}" for n in range(1, MAX_PEOPLE + 1)}},
        "files": {name: {"sha256": tree_sha256(out / name) if (out / name).is_dir() else sha256(out / name)}
                  for name in ("AudienceEncoder.mlpackage", "AudienceHead.mlpackage", "tokenizer.json", "config.json")},
    }
    (out / "coreml.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
