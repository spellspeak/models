"""Tag one line with this release.

    uv run example.py
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "runtime"))

from contracts.schemas.line_tags import LineInput  # noqa: E402
from harness.expression.classifier import LineClassifier  # noqa: E402

clf = LineClassifier(HERE, threads=4)  # loads model.opt.onnx, tokenizer.json and config.json from this folder
line = LineInput(speaker="player", speaker_kind="player", to="Mara", targets=["Mara", "Tomas"],
                 text="lol ur so slow", previous="Mara: The kitchen's backed up, your stew will be a while.")
print(clf.tag(line).model_dump_json(indent=1))
