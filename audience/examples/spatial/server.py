"""Drag people around a room, type a line, see who SpellSpeak Audience thinks it is for.

A small local web server for index.html. Two engines score each line:
- rules: the rules baseline that ships with the runtime (harness/addressee/rules.py). Instant.
- model: the trained model on the CPU, from the release folder's model files.

    uv run server.py        # then open http://127.0.0.1:8768

AUDIENCE_DIR is the release folder with the runtime (default ../../releases/rc1). Its model files are used when they
are there; otherwise they are fetched once from Hugging Face (spellspeak/audience, release rc1).
AUDIENCE_THREADS sets the model's CPU threads (default 4). Listens on 127.0.0.1 only.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

HERE = pathlib.Path(__file__).resolve().parent
# Audience's model files and reference runtime: a release folder of this repo.
RELEASE = pathlib.Path(os.getenv("AUDIENCE_DIR", HERE.parent.parent / "releases" / "rc1")).resolve()
sys.path.insert(0, str(RELEASE / "runtime"))

from contracts.schemas.addressee import AddresseeAnswer, AddresseeRequest  # noqa: E402
from harness.addressee.bands import BandConfig  # noqa: E402
from harness.addressee.render import render  # noqa: E402
from harness.addressee.rules import rules_answer  # noqa: E402

from scene import scene_request  # noqa: E402

PORT = int(os.getenv("PORT", "8768"))
THREADS = int(os.getenv("AUDIENCE_THREADS", "4"))
MODEL_FILES = ["encoder.onnx", "head.onnx", "tokenizer.json", "config.json"]
HF_REPO, HF_REVISION = "spellspeak/audience", "rc1"
DATA = yaml.safe_load((HERE / "scenes.yaml").read_text())
CARDS, SCENES = DATA["cards"], DATA["scenes"]


class Engines:
    def __init__(self):
        self.model = None
        self.model_error = None
        try:
            from harness.addressee.classifier import load_classifier

            model_dir = RELEASE
            if not all((RELEASE / f).exists() for f in MODEL_FILES):  # a git checkout: fetch them from Hugging Face once
                from huggingface_hub import snapshot_download

                model_dir = pathlib.Path(snapshot_download(HF_REPO, revision=HF_REVISION, allow_patterns=MODEL_FILES))
            self.model = load_classifier(model_dir, threads=THREADS)
        except Exception as exc:  # the page still works with the rules, and says why the model is missing
            self.model_error = f"{type(exc).__name__}: {exc}"

    def available(self) -> dict:
        return {"rules": True, "model": self.model is not None, "model_name": RELEASE.name, "model_error": self.model_error}

    def score(self, engine: str, req: AddresseeRequest) -> tuple[AddresseeAnswer, float]:
        t0 = time.perf_counter()
        if engine == "rules":
            ans = rules_answer(req)
        elif engine == "model":
            if self.model is None:
                raise RuntimeError(self.model_error or "no model loaded")
            ans = self.model.answer(req)
        else:
            raise ValueError(engine)
        return ans, (time.perf_counter() - t0) * 1000


ENGINES: Engines | None = None
LOCK = threading.Lock()  # one scoring at a time: the model's sessions are shared


def score_scene(body: dict) -> dict:
    scene, engines, text_only = body["scene"], body.get("engines") or ["rules"], bool(body.get("text_only"))
    req, b, out = scene_request(scene, CARDS, text_only=text_only)
    text, _ = render(req)
    results = {}
    for e in engines:
        try:
            ans, ms = ENGINES.score(e, req)
            results[e] = {"answer": ans.model_dump(), "ms": round(ms, 2)}
        except Exception as exc:  # one engine failing never hides the other
            results[e] = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    return {"present": req.ids, "out_of_earshot": out, "rendered": text,
            "bands": {pid: {"distance_m": x.distance_m, "angle_deg": x.angle_deg, "can_hear": x.can_hear,
                            **x.spatial.model_dump()} for pid, x in b.items()},
            "results": results}


def heatmap(body: dict) -> dict:
    """Move one person over a grid and score the line at each cell."""
    scene, pid, engine = body["scene"], body["person"], body.get("engine", "rules")
    step = max(0.25, float(body.get("step", 0.5)))
    w, h = float(scene["room"]["w"]), float(scene["room"]["h"])
    who = next(p for p in scene["people"] if (p["card"] if isinstance(p["card"], str) else p["card"]["id"]) == pid)
    cells = []
    y = step / 2
    while y < h:
        row, x = [], step / 2
        while x < w:
            who["x"], who["y"] = x, y
            req, _, _ = scene_request(scene, CARDS, text_only=bool(body.get("text_only")))
            if pid not in req.ids:
                row.append(None)
            else:
                ans, _ = ENGINES.score(engine, req)
                row.append(round(ans.addressed[pid], 3))
            x += step
        cells.append(row)
        y += step
    return {"person": pid, "step": step, "cells": cells}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode())

    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/scenes":
            self._json({"scenes": SCENES, "cards": CARDS, "engines": ENGINES.available(), "bands": BandConfig().__dict__})
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            with LOCK:
                if self.path == "/api/score":
                    return self._json(score_scene(body))
                if self.path == "/api/heatmap":
                    return self._json(heatmap(body))
            self._send(404, b"not found", "text/plain")
        except Exception as exc:  # shown in the page, not a crash
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def main() -> None:
    global ENGINES
    ENGINES = Engines()
    status = "rules and the model" if ENGINES.model else f"rules only ({ENGINES.model_error})"
    print(f"SpellSpeak Audience, spatial example: http://127.0.0.1:{PORT}  ({status})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
