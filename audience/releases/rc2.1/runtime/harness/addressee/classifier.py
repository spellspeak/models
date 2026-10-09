"""The addressee model at run time: ONNX Runtime on the CPU, no torch.

A model folder holds `model.onnx` (encoder and heads in one graph; inputs input_ids, attention_mask and the
per-person marker masks; outputs one logit per person, the unclear logit and the group logit), `tokenizer.json` and
`config.json` (temperatures fitted on dev, max length, render version). One encoder pass per line, whatever the number
of people. The input is rendered by `harness/addressee/render.py`, the same code training used.
"""
from __future__ import annotations

import json
import math
import pathlib
import time

from contracts.schemas.addressee import AddresseeAnswer, AddresseeRequest
from harness.addressee.render import RENDER_VERSION, render, span_mask


PRECISIONS = ("fp32", "fp16")


def graph_files(model_dir: str | pathlib.Path, precision: str = "fp32") -> tuple[pathlib.Path, pathlib.Path]:
    """The cached-cards model's two graphs for a precision: `encoder.onnx` and `head.onnx` (full precision, the default
    and the reference), or `encoder_fp16.onnx` and `head_fp16.onnx` (16-bit weights, cast to fp32 when they load: half
    the file, the same answers). A clear error when the chosen files are not in the folder."""
    if precision not in PRECISIONS:
        raise ValueError(f"precision must be one of {', '.join(PRECISIONS)}, not {precision!r}")
    d = pathlib.Path(model_dir)
    suffix = "" if precision == "fp32" else "_fp16"
    enc, head = d / f"encoder{suffix}.onnx", d / f"head{suffix}.onnx"
    missing = [p.name for p in (enc, head) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"precision {precision!r} needs {' and '.join(missing)} in {d}; "
                                f"download them, or use precision='fp32' with encoder.onnx and head.onnx")
    return enc, head


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


class AddresseeClassifier:
    def __init__(self, model_dir: str | pathlib.Path, onnx_file: str = "model.onnx", threads: int = 4):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        d = pathlib.Path(model_dir)
        self.config = json.loads((d / "config.json").read_text())
        if self.config.get("render_version", RENDER_VERSION) != RENDER_VERSION:
            raise ValueError(f"model expects {self.config['render_version']}, the runtime renders {RENDER_VERSION}")
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(self.config["max_len"])
        self.tok.no_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(d / onnx_file), so, providers=["CPUExecutionProvider"])
        self.temps = self.config["temperatures"]

    def logits(self, req: AddresseeRequest) -> tuple[list[float], float, float]:
        np = self.np
        text, spans = render(req)
        enc = self.tok.encode(text)
        sm = np.asarray(span_mask(enc.offsets, spans), dtype=np.float32)
        lp, lu, lg = self.sess.run(None, {"input_ids": np.asarray([enc.ids], dtype=np.int64),
                                          "attention_mask": np.asarray([enc.attention_mask], dtype=np.int64),
                                          "span_mask": sm})
        return [float(x) for x in lp.reshape(-1)], float(lu.reshape(-1)[0]), float(lg.reshape(-1)[0])

    def answer(self, req: AddresseeRequest) -> AddresseeAnswer:
        lp, lu, lg = self.logits(req)
        t = self.temps
        return AddresseeAnswer(addressed={pid: _sigmoid(x / t["person"]) for pid, x in zip(req.ids, lp)},
                               unclear=_sigmoid(lu / t["unclear"]), to_group=_sigmoid(lg / t["group"]))

    def timed(self, req: AddresseeRequest) -> tuple[AddresseeAnswer, float]:
        t0 = time.perf_counter()
        a = self.answer(req)
        return a, (time.perf_counter() - t0) * 1000


class CachedCardsClassifier:
    """The cached-cards model (addressee-tt-0.1) at run time. Two ONNX graphs: `encoder.onnx` encodes a card's text
    (without facts; the result is kept per card text) and, per utterance, the line; `head.onnx` scores each
    person from the line, their cached card and their facts and conversation vector. A model reads the inputs of the
    version it was trained on (its config's `render_version`): rc1 reads addressee-tt-0.5, rc2
    addressee-tt-0.6, which also takes lines spoken by characters."""

    def __init__(self, model_dir: str | pathlib.Path, threads: int = 4, precision: str = "fp32"):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        from harness.addressee.features import TT_VERSIONS

        self.np = np
        d = pathlib.Path(model_dir)
        enc_file, head_file = graph_files(d, precision)
        self.precision = precision
        self.config = json.loads((d / "config.json").read_text())
        self.version = self.config.get("render_version")
        if self.version not in TT_VERSIONS:
            raise ValueError(f"model expects {self.version}, the runtime renders {', '.join(TT_VERSIONS)}")
        self.card_tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.card_tok.enable_truncation(self.config["card_len"])
        self.card_tok.no_padding()
        self.line_tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.line_tok.enable_truncation(self.config["line_len"])
        self.line_tok.no_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.enc = ort.InferenceSession(str(enc_file), so, providers=["CPUExecutionProvider"])
        self.head = ort.InferenceSession(str(head_file), so, providers=["CPUExecutionProvider"])
        self.temps = self.config["temperatures"]
        self.cache: dict[str, tuple] = {}

    def card(self, text: str) -> tuple:
        """(token states, projected token states) for one card text, from the cache or encoded now."""
        hit = self.cache.get(text)
        if hit is None:
            np = self.np
            enc = self.card_tok.encode(text)
            g, gp, _ = self.enc.run(None, {"ids": np.asarray([enc.ids], dtype=np.int64),
                                           "mask": np.asarray([enc.attention_mask], dtype=np.int64)})
            hit = (g[0], gp[0])
            self.cache[text] = hit
        return hit

    def logits(self, req: AddresseeRequest) -> tuple[list[float], float, float]:
        from harness.addressee.features import card_only, line_features, line_input, person_features

        np = self.np
        cached = [self.card(card_only(c)) for c in req.present]
        L = max(g.shape[0] for g, _ in cached)
        d, k = cached[0][0].shape[1], cached[0][1].shape[1]
        g = np.zeros((len(cached), L, d), dtype=np.float32)
        gp = np.zeros((len(cached), L, k), dtype=np.float32)
        cm = np.zeros((len(cached), L), dtype=np.int64)
        for i, (a, b) in enumerate(cached):
            g[i, :a.shape[0]], gp[i, :b.shape[0]], cm[i, :a.shape[0]] = a, b, 1
        text, cur_len = line_input(req)
        enc = self.line_tok.encode(text)
        cur = np.asarray([[1.0 if (b > a and b <= cur_len) else 0.0 for a, b in enc.offsets]], dtype=np.float32)
        h, hp, q = self.enc.run(None, {"ids": np.asarray([enc.ids], dtype=np.int64),
                                       "mask": np.asarray([enc.attention_mask], dtype=np.int64)})
        lp, lu, lg = self.head.run(None, {
            "q": q, "h": h, "hp": hp, "cur": cur, "g": g, "gp": gp, "card_mask": cm,
            "pfeat": np.asarray(person_features(req, self.version), dtype=np.float32),
            "lfeat": np.asarray([line_features(req, self.version)], dtype=np.float32)})
        return [float(x) for x in lp.reshape(-1)], float(lu.reshape(-1)[0]), float(lg.reshape(-1)[0])

    def answer(self, req: AddresseeRequest) -> AddresseeAnswer:
        lp, lu, lg = self.logits(req)
        t = self.temps
        return AddresseeAnswer(addressed={pid: _sigmoid(x / t["person"]) for pid, x in zip(req.ids, lp)},
                               unclear=_sigmoid(lu / t["unclear"]), to_group=_sigmoid(lg / t["group"]))

    def timed(self, req: AddresseeRequest) -> tuple[AddresseeAnswer, float]:
        t0 = time.perf_counter()
        a = self.answer(req)
        return a, (time.perf_counter() - t0) * 1000


def load_classifier(model_dir: str | pathlib.Path, threads: int = 4, precision: str = "fp32"):
    """The right runtime for an exported model folder: cached cards when it has a card encoder, else single pass.
    `precision`: "fp32" (the default) reads encoder.onnx and head.onnx; "fp16" reads encoder_fp16.onnx and
    head_fp16.onnx, in a folder that may hold only those (rc2.1 on)."""
    d = pathlib.Path(model_dir)
    if (d / "head.onnx").exists() or (d / "head_fp16.onnx").exists():
        return CachedCardsClassifier(d, threads, precision)
    if precision != "fp32":
        raise ValueError(f"precision {precision!r} needs a cached-cards model (encoder and head); {d} holds a single-pass model.onnx")
    return AddresseeClassifier(d, threads=threads)
