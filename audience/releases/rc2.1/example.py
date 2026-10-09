"""Ask SpellSpeak Audience who a line is for.

    pip install -r requirements.txt
    python example.py           # full precision: encoder.onnx and head.onnx
    python example.py --fp16    # the 16-bit files, where the release has them: half the download, the same answers

The model files (the two graphs, tokenizer.json and config.json) are read from this folder. Without them, as in a git
checkout, the ones the chosen precision needs are downloaded once from Hugging Face (spellspeak/audience, release rc2.1).
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "runtime"))

from contracts.schemas.addressee import AddresseeRequest  # noqa: E402
from contracts.schemas.person_card import PersonCard  # noqa: E402
from harness.addressee.bands import Pose, bands  # noqa: E402
from harness.addressee.classifier import load_classifier  # noqa: E402

parser = argparse.ArgumentParser(description="Ask SpellSpeak Audience who a line is for.")
parser.add_argument("--fp16", action="store_true", help="use the 16-bit files: half the download, the same answers")
PRECISION = "fp16" if parser.parse_args().fp16 else "fp32"
GRAPHS = ["encoder.onnx", "head.onnx"] if PRECISION == "fp32" else ["encoder_fp16.onnx", "head_fp16.onnx"]
MODEL_FILES = [*GRAPHS, "tokenizer.json", "config.json"]
model_dir = HERE
if not all((HERE / f).exists() for f in MODEL_FILES):
    from huggingface_hub import snapshot_download

    model_dir = snapshot_download("spellspeak/audience", revision="rc2.1", allow_patterns=MODEL_FILES)
model = load_classifier(model_dir, threads=4, precision=PRECISION)

# What the player can see of each person. Keys are open: a game uses its own.
people = [
    PersonCard(id="tomas", label="Tomas", aliases=["barkeep"],
               features=[{"key": "role", "value": "barkeep"}, {"key": "headwear", "value": "red hat"},
                         {"key": "holding", "value": "a tankard"}]),
    PersonCard(id="wren", label="Wren", features=[{"key": "role", "value": "mercenary"}, {"key": "race", "value": "elf"},
                                                  {"key": "carrying", "value": "a longbow"}]),
    PersonCard(id="oskar", label="the old sailor", features=[{"key": "build", "value": "stout"},
                                                             {"key": "holding", "value": "a pipe"}]),
]

# Where everyone stands (metres) and faces (degrees), turned into the facts the model reads. The player faces Wren.
facts = bands(Pose(0.0, 0.0, 90.0), {"tomas": Pose(-6.0, 5.0, -40.0), "wren": Pose(0.5, 2.0, -100.0), "oskar": Pose(5.0, 4.0, 180.0)})
with_facts = [p.model_copy(update={"spatial": facts[p.id].spatial}) for p in people]


def reading(a) -> str:
    """One way a game might read the scores: unclear first, then the whole group, then the top person."""
    if a.unclear >= 0.5:
        return f"unclear ({a.unclear:.2f}): a 'Who, me?' moment"
    if a.to_group >= 0.5:
        return f"the whole group ({a.to_group:.2f})"
    top = max(a.addressed, key=a.addressed.get)
    return f"{top} ({a.addressed[top]:.2f})"


for text in ("You in the red hat, another round.", "Hello.", "You lied to me.", "Who knows where the mill key is?"):
    for mode, cards in (("with facts", with_facts), ("text only", people)):
        print(f"{text!r:38} {mode:10}  {reading(model.answer(AddresseeRequest(text=text, present=cards)))}")

# A character speaks (inputs addressee-tt-0.6, rc2 on): the player is one of the people, and the speaker is not.
if model.config.get("render_version") == "addressee-tt-0.6":
    player = PersonCard(id="player", label="the traveller", features=[{"key": "clothing", "value": "a green cloak"}])
    asked = [{"speaker": "player", "to": ["tomas"], "text": "Where's the mill key?"}]
    for text in ("No idea, sorry.", "Wren, were you there?"):
        req = AddresseeRequest(speaker="tomas", speaker_label="Tomas", text=text, present=[player, people[1], people[2]], history=asked)
        print(f"{'Tomas: ' + repr(text):38} {'text only':10}  {reading(model.answer(req))}")
