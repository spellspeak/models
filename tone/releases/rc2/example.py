"""Tag a few lines of a group conversation with SpellSpeak Tone.

    pip install -r requirements.txt
    python example.py

The model files (model.opt.onnx, model.onnx, tokenizer.json, config.json) are read from this folder. Without them, as in
a git checkout, they are downloaded once from Hugging Face (spellspeak/tone, release rc2).
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "runtime"))

from contracts.schemas.line_tags import LineInput  # noqa: E402
from harness.expression.classifier import LineClassifier  # noqa: E402

MODEL_FILES = ["model.opt.onnx", "model.onnx", "tokenizer.json", "config.json"]
model_dir = HERE
if not all((HERE / f).exists() for f in MODEL_FILES):
    from huggingface_hub import snapshot_download

    model_dir = snapshot_download("spellspeak/tone", revision="rc2", allow_patterns=MODEL_FILES)
tone = LineClassifier(model_dir, threads=4)

# Three characters and the player. Each line names who speaks, who it is to (None: the room) and the line before it.
CAST = ["Mara", "Tomas", "Wren", "player"]
QUESTION = "player: Who knows where the mill key is?"
LINES = [
    ("player", None, "Who knows where the mill key is?", None),
    ("Mara", "player", "It's under the counter, love.", QUESTION),
    ("Tomas", "player", "I heard the miller had it last.", QUESTION),
    ("Wren", "player", "Why do you want to know?", QUESTION),
    ("Tomas", "player", "No idea, sorry.", QUESTION),
    ("player", "Mara", "thanks, that's all i needed", "Mara: It's under the counter, love."),
    ("player", "Tomas", "Touch my horse again and you'll regret it.", None),
]

for speaker, to, text, previous in LINES:
    line = LineInput(speaker=speaker, speaker_kind="player" if speaker == "player" else "npc", to=to,
                     targets=[p for p in CAST if p != speaker], text=text, previous=previous)
    tags = tone.tag(line)
    acts = ", ".join(f"{who} {a.act}" for who, a in tags.acts.items() if a.act != "none") or "none"
    move = getattr(tags, "exchange", None)  # models from rc2 on
    print(f"{speaker} to {to or 'everyone'}: {text!r}")
    print(f"    move {move.label} ({move.confidence:.2f}) · emotion {tags.emotion} · acts: {acts}" if move else
          f"    emotion {tags.emotion} · acts: {acts}")

# The full output for one line, as JSON
print(tone.tag(LineInput(speaker="Wren", speaker_kind="npc", to="Tomas", targets=["Tomas", "Mara", "player"],
                         text="Aye, I saw the whole thing.", previous="Tomas: Wren, you were there, weren't you?")).model_dump_json(indent=1))
