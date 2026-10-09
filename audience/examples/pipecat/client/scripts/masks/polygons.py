"""Broad polygon outlines for the four characters in src/assets/base.png, written to src/scene-geometry.json.

    uv run --with opencv-python-headless --with numpy python scripts/masks/polygons.py

`polys.py` holds rough hand-traced outlines (in a 1600 px preview's coordinates). GrabCut refines each against the
image, front to back (the engineer and the hacker stand in front of the robot, so they're cut out of it). Each refined
shape is then grown by PAD px, cut where someone stands in front (DEPTH), and simplified to straight edges: a
close outline without pixel noise. The
output is in the image's own 2048 px coordinates.
"""
import importlib.util
import json
import pathlib

import cv2
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
CLIENT = HERE.parent.parent
spec = importlib.util.spec_from_file_location("polys", HERE / "polys.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

SIZE, WORK = 2048, 1024
PAD = 8  # px (2048 scale) the outline stands off the figure
EPSILON = 5  # px: how far the simplified outline may stray from the grown shape
CLOSE = 15  # px: gaps narrower than this (between fingers, under an arm) are filled in
# Back to front: who stands behind whom. Each outline is cut where someone in front of them stands.
DEPTH = {"atlas": 0, "nova": 1, "bruno": 1, "kai": 1}

src = cv2.imread(str(CLIENT / "src" / "assets" / "base.png"))
img = cv2.resize(src, (WORK, WORK), interpolation=cv2.INTER_AREA)


def rough_mask(pts):
    m = np.zeros((WORK, WORK), np.uint8)
    cv2.fillPoly(m, [np.array([(int(x * WORK / 1600), int(y * WORK / 1600)) for x, y in pts], np.int32)], 255)
    return m


refined = {}
for name in ("nova", "bruno", "atlas", "kai"):
    rough = rough_mask(P.POLYS[name])
    gc = np.full((WORK, WORK), cv2.GC_BGD, np.uint8)
    gc[cv2.dilate(rough, np.ones((25, 25), np.uint8)) > 0] = cv2.GC_PR_BGD
    gc[rough > 0] = cv2.GC_PR_FGD
    gc[cv2.erode(rough, np.ones((23, 23), np.uint8)) > 0] = cv2.GC_FGD
    cv2.grabCut(img, gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 6, cv2.GC_INIT_WITH_MASK)
    m = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    ratio = m.sum() / max(rough.sum(), 1)
    refined[name] = m if 0.6 <= ratio <= 1.15 else rough  # GrabCut lost the figure: keep the trace
for front in ("bruno", "kai"):
    refined["atlas"] = cv2.subtract(refined["atlas"], refined[front])

grown = {}
for name, m in refined.items():
    m = cv2.resize(m, (SIZE, SIZE), interpolation=cv2.INTER_NEAREST)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE, CLOSE)))
    grown[name] = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * PAD + 1, 2 * PAD + 1)))
# Cut each outline where someone in front stands, after growing: the margin mustn't creep back over them.
for name in grown:
    for other in grown:
        if DEPTH[other] > DEPTH[name]:
            grown[name] = cv2.subtract(grown[name], grown[other])

out = {}
for name, m in grown.items():
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))  # slivers left by the cut
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(contours, key=cv2.contourArea)
    poly = cv2.approxPolyDP(c, EPSILON, True).reshape(-1, 2)
    x, y, w, h = cv2.boundingRect(poly)
    out[name] = {"z": DEPTH[name], "box": [int(x), int(y), int(x + w), int(y + h)], "outline": poly.astype(int).tolist()}
    print(f"{name}: {len(poly)} points, box {out[name]['box']}")

(CLIENT / "src" / "scene-geometry.json").write_text(json.dumps(out) + "\n")

sheet = (img * 0.3).astype(np.uint8)
for name, g in out.items():
    pts = (np.array(g["outline"]) * WORK / SIZE).astype(np.int32)
    lit = np.zeros((WORK, WORK), np.uint8)
    cv2.fillPoly(lit, [pts], 255)
    sheet[lit > 0] = img[lit > 0]
    cv2.polylines(sheet, [pts], True, P.COLORS[name][::-1], 2)
cv2.imwrite(str(HERE / "sheet.png"), sheet)  # a check image, not committed
