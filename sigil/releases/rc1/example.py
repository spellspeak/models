"""Ask SpellSpeak Sigil 4B for one line of dialogue, on llama.cpp.

    pip install -r requirements.txt
    python example.py                        # the Q4_K_M file
    python example.py --file Q4_K_M     # or name another file in gguf/

Needs llama-server from llama.cpp build b11146 or later (https://github.com/ggml-org/llama.cpp), on PATH or given with
--server. Without the GGUF file beside this script, it is downloaded once from Hugging Face (jptaylor/sigil-4b, rc1).
"""
import argparse
import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "runtime"))

from contracts.protocols.actor_context import ActorContext, ActorIdentity, KnownItem, SettingView, Turn  # noqa: E402
from contracts.protocols.template import format_by_name, render_prompt  # noqa: E402

parser = argparse.ArgumentParser(description="Ask SpellSpeak Sigil 4B for one line of dialogue.")
parser.add_argument("--file", default="Q4_K_M", help="which quantization: Q4_K_M, Q5_K_M")
parser.add_argument("--server", default="llama-server", help="path to llama-server")
parser.add_argument("--gpu-layers", default="all", help="llama-server's -ngl: all, or 0 for CPU only")
args = parser.parse_args()

name = f"spellspeak-sigil-4b-{args.file}.gguf"
path = HERE / "gguf" / name
if not path.exists():
    from huggingface_hub import hf_hub_download

    path = pathlib.Path(hf_hub_download("jptaylor/sigil-4b", f"gguf/{name}", revision="rc1"))

# What this character knows, as of now. The game builds this: the model gets only what the character can know.
character = ActorContext(
    world_id="example", session_id="example", state_revision=1,
    actor=ActorIdentity(id="tomas", name="Tomas", role="the barkeep of the Crooked Lantern", voice="dry, unhurried, short sentences"),
    location_name="the Crooked Lantern",
    setting=SettingView(knowledge_policy="closed_fictional", technology="medieval", magic="present"),
    known=[KnownItem(subject="crooked_lantern", subject_name="the Crooked Lantern", predicate="sells", value="ale at two coppers a mug",
                     source_kind="self", learned_at_revision=1)],
)
scenes = {
    "A question it can answer": [Turn(speaker="player", text="What's a mug of ale cost here?")],
    "A question it cannot answer": [Turn(speaker="player", text="Who is the king's secret heir?")],
    "Something from outside its world": [Turn(speaker="player", text="Can I pay with my phone?")],
}

fmt = format_by_name("gemma4-instruct")
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
# --lazy-mode on reads Gemma's per-layer table from the file a row at a time, instead of holding it all in memory.
server = subprocess.Popen([args.server, "-m", str(path), "--host", "127.0.0.1", "--port", str(port), "-c", "4096", "-np", "1", "--no-ui",
                           "-cram", "0", "-ngl", args.gpu_layers, "--lazy-mode", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(600):
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).status == 200:
                break
        except (urllib.error.URLError, OSError):
            if server.poll() is not None:
                raise SystemExit("llama-server stopped while loading. Its build may be too old for this file.") from None
            time.sleep(1)
    else:
        raise SystemExit("llama-server did not become ready")
    for label, dialogue in scenes.items():
        body = {"prompt": render_prompt(character, dialogue, fmt), "n_predict": 80, "temperature": 0.0, "top_k": 1, "seed": 0,
                "cache_prompt": False, "stop": [fmt.reply_end]}
        request = urllib.request.Request(f"http://127.0.0.1:{port}/completion", json.dumps(body).encode(), {"Content-Type": "application/json"})
        reply = json.load(urllib.request.urlopen(request, timeout=600))["content"].strip()
        print(f"{label}\n  Player: {dialogue[-1].text}\n  Tomas: {reply}\n")
finally:
    server.terminate()
    server.wait()
