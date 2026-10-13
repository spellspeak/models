"""SpellSpeak Audience on Core ML, from Python on macOS: a drop-in for the reference runtime's CachedCardsClassifier.

The request, the cards and the features are the reference runtime's own (`runtime/` in a release folder), so this
differs from it only in how the two models run: tokens are padded to the Core ML models' fixed shapes, which leaves
the answer unchanged, and the head is the function for the number of people present.

    from classifier import load_coreml_classifier
    model = load_coreml_classifier("build/rc2.1")
    model.answer(AddresseeRequest(...))
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
COMPUTE_UNITS = ("cpu", "cpu_and_gpu", "all")


def use_runtime(release: str = "rc2.1") -> None:
    """Put a release's reference runtime on the import path."""
    runtime = HERE.parent / "releases" / release / "runtime"
    if str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


class CoreMLClassifier:
    """The cached-cards model on Core ML. A card's encoding is kept per card text, as in the reference runtime."""

    def __init__(self, model_dir: str | pathlib.Path, compute_units: str = "cpu"):
        import coremltools as ct
        from tokenizers import Tokenizer

        d = pathlib.Path(model_dir)
        self.dir = d
        self.units = {"cpu": ct.ComputeUnit.CPU_ONLY, "cpu_and_gpu": ct.ComputeUnit.CPU_AND_GPU,
                      "all": ct.ComputeUnit.ALL}[compute_units]
        self.config = json.loads((d / "config.json").read_text())
        self.meta = json.loads((d / "coreml.json").read_text())
        self.tokens = self.meta["encoder"]["tokens"]
        self.line_tokens = self.meta["head"]["line_tokens"]
        self.pad_id = self.meta["encoder"]["pad_id"]
        self.card_tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.card_tok.enable_truncation(self.config["card_len"])
        self.card_tok.no_padding()
        self.line_tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.line_tok.enable_truncation(self.config["line_len"])
        self.line_tok.no_padding()
        self.encoder = ct.models.MLModel(str(d / "AudienceEncoder.mlpackage"), compute_units=self.units)
        self.heads: dict[int, object] = {}
        self.temps = self.config["temperatures"]
        self.cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def encode(self, ids: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Token states, projected states and the pooled vector for one text's real tokens."""
        n = len(ids)
        padded = np.full((1, self.tokens), self.pad_id, np.int32)
        mask = np.zeros((1, self.tokens), np.int32)
        padded[0, :n], mask[0, :n] = ids, 1
        out = self.encoder.predict({"ids": padded, "mask": mask})
        # Copies: the cache outlives the prediction's buffers.
        return (np.array(out["h"][0, :n], np.float32), np.array(out["hp"][0, :n], np.float32),
                np.array(out["pooled"], np.float32))

    def card(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        hit = self.cache.get(text)
        if hit is None:
            h, hp, _ = self.encode(self.card_tok.encode(text).ids)
            hit = self.cache[text] = (h, hp)
        return hit

    def head(self, people: int):
        """The head function for this many people. One is loaded at a time: coremltools' Python bridge crashes with
        several functions of one package loaded at once. Core ML itself, from Swift, runs them together."""
        if people not in self.heads:
            import coremltools as ct

            self.heads.clear()
            name = self.meta["head"]["functions"][str(people)]
            self.heads[people] = ct.models.MLModel(str(self.dir / "AudienceHead.mlpackage"), compute_units=self.units,
                                                   function_name=name)
        return self.heads[people]

    def logits(self, req) -> tuple[list[float], float, float]:
        from harness.addressee.features import card_only, line_features, line_input, person_features

        cards = [self.card(card_only(c)) for c in req.present]
        people = len(cards)
        g = np.zeros((people, self.tokens, 384), np.float32)
        gp = np.zeros((people, self.tokens, 128), np.float32)
        card_mask = np.zeros((people, self.tokens), np.int32)
        for i, (h, hp) in enumerate(cards):
            g[i, :len(h)], gp[i, :len(hp)], card_mask[i, :len(h)] = h, hp, 1
        text, cur_len = line_input(req)
        enc = self.line_tok.encode(text)
        h, hp, q = self.encode(enc.ids)
        m = len(enc.ids)
        line_h = np.zeros((1, self.line_tokens, 384), np.float32)
        line_hp = np.zeros((1, self.line_tokens, 128), np.float32)
        cur = np.zeros((1, self.line_tokens), np.float32)
        line_h[0, :m], line_hp[0, :m] = h, hp
        cur[0, :m] = [1.0 if (b > a and b <= cur_len) else 0.0 for a, b in enc.offsets]
        out = self.head(people).predict({
            "q": q, "h": line_h, "hp": line_hp, "cur": cur, "g": g, "gp": gp, "card_mask": card_mask,
            "pfeat": np.asarray(person_features(req, self.config["render_version"]), np.float32),
            "lfeat": np.asarray([line_features(req, self.config["render_version"])], np.float32)})
        return ([float(x) for x in np.asarray(out["person"]).reshape(-1)], float(np.asarray(out["unclear"]).reshape(-1)[0]),
                float(np.asarray(out["group"]).reshape(-1)[0]))

    def answer(self, req):
        from contracts.schemas.addressee import AddresseeAnswer

        lp, lu, lg = self.logits(req)
        t = self.temps
        return AddresseeAnswer(addressed={pid: _sigmoid(x / t["person"]) for pid, x in zip(req.ids, lp)},
                               unclear=_sigmoid(lu / t["unclear"]), to_group=_sigmoid(lg / t["group"]))

    def timed(self, req):
        t0 = time.perf_counter()
        a = self.answer(req)
        return a, (time.perf_counter() - t0) * 1000


def load_coreml_classifier(model_dir: str | pathlib.Path, compute_units: str = "cpu", release: str | None = None):
    """A converted model folder (convert.py's output) as a classifier, with its release's runtime importable."""
    meta = json.loads((pathlib.Path(model_dir) / "coreml.json").read_text())
    use_runtime(release or meta["release"])
    return CoreMLClassifier(model_dir, compute_units)
