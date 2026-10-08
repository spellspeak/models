"""The line classifier at run time: ONNX Runtime on the CPU, no torch (line classifier S6).

A model folder holds `model.onnx` (encoder and heads in one graph; inputs input_ids, attention_mask and the
per-person marker masks; outputs the five heads' logits), `tokenizer.json` and `config.json` (class lists, the
hostility threshold tau, max length).

One encoder pass per line, whatever the number of people. The act toward each person is read at that person's
marker. The operating point is shared with the scorecard (harness/expression/decide.py): a pair is hostile exactly when
its hostility probability reaches tau (plan §5: an invented grudge costs more than a miss).
"""
from __future__ import annotations

import json
import pathlib
import time

from contracts.schemas.line_tags import ActTag, LineInput, LineTags, is_hostile
from harness.expression.calibrate import emotion_confidence, tag_confidence
from harness.expression.decide import decide, summed_hostility
from harness.expression.render import render, span_mask


class LineClassifier:
    def __init__(self, model_dir: str | pathlib.Path, onnx_file: str | None = None, threads: int = 4):
        """`onnx_file` defaults to the transformer optimizer's graph when the export has one (r3 on: same outputs,
        a little faster; exp-219), else the plain graph."""
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = pathlib.Path(model_dir)
        onnx_file = onnx_file or ("model.opt.onnx" if (d / "model.opt.onnx").exists() else "model.onnx")
        self.onnx_file = onnx_file
        self.config = json.loads((d / "config.json").read_text())
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(self.config["max_len"])
        self.tok.no_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(d / onnx_file), so, providers=["CPUExecutionProvider"])
        self.acts = self.config["acts"]
        self.calibration = self.config.get("calibration")  # r7: reported confidences mean what they say
        self.emotions = self.config["emotions"]
        self.intensities = self.config["intensities"]
        self.tau = float(self.config["tau"])

    def logits(self, inp: LineInput):
        """Raw outputs for one line: emotion, emotion intensity, act per person, act intensity per person, backchannel."""
        import numpy as np

        text, spans = render(inp.model_dump())
        enc = self.tok.encode(text)
        ids = np.asarray([enc.ids], dtype=np.int64)
        mask = np.asarray([enc.attention_mask], dtype=np.int64)
        smask = np.asarray(span_mask(list(enc.offsets), spans), dtype=np.float32)
        return self.sess.run(None, {"input_ids": ids, "attention_mask": mask, "span_mask": smask})

    def tag(self, inp: LineInput) -> LineTags:
        import numpy as np

        def softmax(x):
            e = np.exp(x - x.max(-1, keepdims=True))
            return e / e.sum(-1, keepdims=True)

        out = self.logits(inp)
        le, lei, la, lai, lb = out[:5]
        p_host = 1 / (1 + np.exp(-out[5])) if len(out) > 5 else None  # the hostility head (models from exp-207 try 2 on)
        pe, pei, pa, pai = softmax(le[0]), softmax(lei[0]), softmax(la), softmax(lai)
        emo = self.emotions[int(pe.argmax())]
        if float(softmax(lb[0])[1]) >= 0.5:  # a backchannel is not a turn: no act toward anyone
            return LineTags(emotion=emo, emotion_intensity="low" if emo == "neutral" else self.intensities[int(pei.argmax())],
                            emotion_confidence=round(emotion_confidence(float(pe.max()), self.calibration), 4),
                            acts={t: ActTag(act="none") for t in inp.targets}, backchannel=True)
        acts = {}
        for i, t in enumerate(inp.targets):
            ph = float(p_host[i]) if p_host is not None else summed_hostility(pa[i])
            act, inten = decide(pa[i], ph, self.tau, self.intensities[int(pai[i].argmax())])
            # The confidence is the probability the decision rests on: for a hostile act, the hostility score (the
            # act's own class can sit under 0.5 while the line is clearly hostile); otherwise the act's probability.
            hostile = is_hostile(act, inten)
            conf = ph if hostile else float(pa[i][self.acts.index(act)])
            acts[t] = ActTag(act=act, intensity=inten, confidence=round(tag_confidence(conf, hostile, self.calibration), 4))
        return LineTags(emotion=emo, emotion_intensity="low" if emo == "neutral" else self.intensities[int(pei.argmax())],
                        emotion_confidence=round(emotion_confidence(float(pe.max()), self.calibration), 4), acts=acts, backchannel=False)

    def timed(self, inp: LineInput) -> tuple[LineTags, float]:
        t = time.perf_counter()
        out = self.tag(inp)
        return out, (time.perf_counter() - t) * 1000
