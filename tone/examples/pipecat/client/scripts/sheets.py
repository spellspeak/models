"""Each character's nine faces, combined into one mood sheet the client loads once.

    uv run --with pillow python scripts/sheets.py

Reads `src/assets/portraits/<id>/<id>-<mood>.webp` (one face per Tone emotion) and writes
`src/assets/moods/<id>.webp`: a 3 × 3 grid in Tone's order, left to right, top to bottom
(neutral, happy, amused / angry, sad, afraid / surprised, disgusted, contemptuous). The faces are
pixel art drawn at 256 px and scaled up about five times, so each is sampled back to 256 px (the
middle of every art pixel), the sheet is given one palette of 256 colours (the faces carry tens of
thousands of near-identical ones from being scaled; the palette halves the file and changes a
colour by about 1.5 levels in 255 on average), and saved lossless: 768 px, every face at once. The
client scales it back up with `image-rendering: pixelated`.

A character missing a face gets no sheet (the script says which), and shows their portrait instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "src" / "assets"
FACES = ASSETS / "portraits"
SHEETS = ASSETS / "moods"

MOODS = [
    "neutral", "happy", "amused",
    "angry", "sad", "afraid",
    "surprised", "disgusted", "contemptuous",
]  # fmt: skip
CELL = 256  # the art's own size: every face is drawn at 256 px
COLOURS = 256  # one palette for the whole sheet


def face(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if im.width != im.height:
        raise SystemExit(f"{path.name} is {im.width} × {im.height}: faces are square")
    # Nearest sampling picks the middle of each art pixel, so nothing is blurred.
    return im if im.width == CELL else im.resize((CELL, CELL), Image.NEAREST)


def main() -> int:
    SHEETS.mkdir(exist_ok=True)
    made = 0
    for folder in sorted(p for p in FACES.iterdir() if p.is_dir()):
        who = folder.name
        paths = [folder / f"{who}-{m}.webp" for m in MOODS]
        missing = [p.name for p in paths if not p.exists()]
        if missing:
            print(f"{who}: no sheet, missing {', '.join(missing)}")
            continue
        sheet = Image.new("RGB", (CELL * 3, CELL * 3))
        for i, path in enumerate(paths):
            sheet.paste(face(path), ((i % 3) * CELL, (i // 3) * CELL))
        palette = sheet.quantize(COLOURS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        out = SHEETS / f"{who}.webp"
        palette.convert("RGB").save(out, "WEBP", lossless=True, method=6)
        print(f"{who}: {out.relative_to(HERE.parent)} ({out.stat().st_size // 1024} KB)")
        made += 1
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
