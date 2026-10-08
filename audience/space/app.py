"""SpellSpeak Audience on Hugging Face Spaces: who is a line for?

Pick a room, choose where the player looks and who they were just talking with, and type a line. The model answers
twice: with the spatial facts a game would send, and from the words alone.

The release (the reference runtime and the model files) sits in ./release, or wherever AUDIENCE_DIR points.
scene.py and scenes.yaml are the spatial example's (../examples/spatial/).
"""
from __future__ import annotations

import html
import math
import os
import pathlib
import sys
import time

import gradio as gr
import yaml

HERE = pathlib.Path(__file__).resolve().parent
RELEASE = pathlib.Path(os.getenv("AUDIENCE_DIR", HERE / "release")).resolve()
sys.path.insert(0, str(RELEASE / "runtime"))
sys.path.insert(0, str(HERE))

from harness.addressee.bands import BandConfig  # noqa: E402
from harness.addressee.classifier import load_classifier  # noqa: E402
from harness.addressee.features import card_only, line_input  # noqa: E402
from scene import scene_request  # noqa: E402

MODEL = load_classifier(RELEASE, threads=int(os.getenv("AUDIENCE_THREADS", "2")))
DATA = yaml.safe_load((HERE / "scenes.yaml").read_text())
CARDS, ROOMS = DATA["cards"], DATA["scenes"]
CFG = BandConfig()
NOBODY = "nobody"

# Lines to try: (line, room, where the player looks, who they were just talking with, that person's last line)
SITUATIONS = [
    ("You in the red hat, another round.", "tavern", "p:wren", NOBODY, ""),
    ("Hello.", "tavern", "p:wren", NOBODY, ""),
    ("You lied to me.", "tavern", "p:wren", NOBODY, ""),
    ("Yes.", "tavern", "p:wren", "tomas", "Another round?"),
    ("Thanks, that helps.", "tavern", "p:oskar", "wren", "The bridge is out. Take the ford."),
    ("Right, listen up, all of you.", "tavern", "p:wren", NOBODY, ""),
    ("Who are you?", "tavern", "p:stranger", NOBODY, ""),
    ("Hey, chrome arm, you know your way round a reactor?", "station", "p:lunn", NOBODY, ""),
]
BY_LINE = {s[0]: s for s in SITUATIONS}


def _name(pid: str) -> str:
    return CARDS[pid]["label"]


def _people(room: str) -> list[str]:
    return [p["card"] for p in ROOMS[room]["people"]]


def faces_choices(room: str) -> list[tuple[str, str]]:
    people = [(_name(pid), f"p:{pid}") for pid in _people(room)]
    things = [(f"the {o['name']}", f"o:{o['name']}") for o in ROOMS[room].get("objects", [])]
    return people + things


def talking_choices(room: str) -> list[tuple[str, str]]:
    return [("nobody", NOBODY)] + [(_name(pid), pid) for pid in _people(room)]


def build_scene(room: str, faces: str, talking: str, before: str, text: str) -> dict:
    """The room as a game would know it when the player speaks."""
    base = ROOMS[room]
    scene = {**base, "player": dict(base["player"]), "text": text}
    kind, _, key = (faces or "").partition(":")
    spots = {p["card"]: p for p in base["people"]} if kind == "p" else {o["name"]: o for o in base.get("objects", [])}
    if key in spots:
        px, py = scene["player"]["x"], scene["player"]["y"]
        scene["player"]["facing"] = math.degrees(math.atan2(spots[key]["y"] - py, spots[key]["x"] - px))
    if talking and talking != NOBODY:
        scene["last_spoke"] = talking
        said = (before or "").strip()
        if said:
            scene["history"] = [{"speaker": talking, "to": ["player"], "text": said}]
            if said.endswith("?"):
                scene["asked"] = [talking]
    return scene


def _verdict(a, names: dict[str, str]) -> tuple[str, str]:
    """One way a game might read the scores: unclear first, then the whole group, then the top person."""
    if a.unclear >= 0.5:
        return "Unclear", f"unclear {a.unclear:.2f}: nobody should take it personally yet, a “Who, me?” moment"
    if a.to_group >= 0.5:
        return "The whole group", f"whole group {a.to_group:.2f}"
    top = a.top()
    return names[top][:1].upper() + names[top][1:], f"probability {a.addressed[top]:.2f}"


def _panel(title: str, note: str, a, names: dict[str, str]) -> str:
    head, sub = _verdict(a, names)
    rows = "".join(
        f'<div class="aud-row"><span class="aud-who">{html.escape(names[pid])}</span>'
        f'<span class="aud-bar"><i style="width:{max(p, 0.004) * 100:.1f}%"></i></span>'
        f'<span class="aud-num">{p:.2f}</span></div>'
        for pid, p in sorted(a.addressed.items(), key=lambda kv: -kv[1]))
    extra = (f'<div class="aud-extra"><span>unclear <b>{a.unclear:.2f}</b></span>'
             f'<span>whole group <b>{a.to_group:.2f}</b></span></div>')
    return (f'<section class="aud-panel"><div class="aud-kicker">{title}</div><div class="aud-note">{note}</div>'
            f'<div class="aud-verdict">{html.escape(head)}</div><div class="aud-sub">{html.escape(sub)}</div>'
            f'<div class="aud-rows">{rows}</div>{extra}</section>')


def _yes(v: bool | None) -> str:
    return "yes" if v is True else "no" if v is False else "?"


def map_svg(scene: dict, bands: dict, answer, out: list[str]) -> str:
    """The room from above: the player's view cone, the near and mid rings, and everyone shaded by the answer."""
    w, h = scene["room"]["w"], scene["room"]["h"]
    p = scene["player"]
    px, py, f = p["x"], p["y"], math.radians(p["facing"])
    half, reach = math.radians(CFG.gaze_half_angle_deg), max(w, h) * 1.5
    a1, a2 = f - half, f + half
    cone = (f"M{px:.2f},{py:.2f} L{px + reach * math.cos(a1):.2f},{py + reach * math.sin(a1):.2f} "
            f"A{reach:.1f},{reach:.1f} 0 0 1 {px + reach * math.cos(a2):.2f},{py + reach * math.sin(a2):.2f} Z")
    parts = [f'<svg class="aud-map" viewBox="-0.6 -0.6 {w + 1.2} {h + 1.2}" role="img" '
             f'aria-label="{html.escape(scene["title"])}, seen from above">',
             '<defs><clipPath id="room"><rect x="0" y="0" width="%s" height="%s" rx="0.3"/></clipPath></defs>' % (w, h),
             f'<rect class="room" x="0" y="0" width="{w}" height="{h}" rx="0.3"/>',
             f'<g clip-path="url(#room)"><path class="cone" d="{cone}"/>',
             f'<circle class="ring" cx="{px}" cy="{py}" r="{CFG.near_m}"/>',
             f'<circle class="ring" cx="{px}" cy="{py}" r="{CFG.mid_m}"/></g>']
    for o in scene.get("objects", []):
        parts.append(f'<rect class="thing" x="{o["x"] - 0.28:.2f}" y="{o["y"] - 0.28:.2f}" width="0.56" height="0.56" rx="0.1"/>'
                     f'<text class="thinglabel" x="{o["x"]:.2f}" y="{o["y"] - 0.45:.2f}">{html.escape(o["name"])}</text>')
    for spec in scene["people"]:
        pid, x, y = spec["card"], spec["x"], spec["y"]
        fa = math.radians(spec.get("facing", 0.0))
        heard = pid not in out
        prob = answer.addressed.get(pid, 0.0) if heard else 0.0
        cls = "person" if heard else "person away"
        parts.append(f'<line class="nose" x1="{x:.2f}" y1="{y:.2f}" x2="{x + 0.75 * math.cos(fa):.2f}" y2="{y + 0.75 * math.sin(fa):.2f}"/>'
                     f'<circle class="{cls}" cx="{x:.2f}" cy="{y:.2f}" r="0.5" style="fill-opacity:{0.1 + 0.9 * prob:.2f}"/>'
                     f'<text class="who" x="{x:.2f}" y="{y - 0.75:.2f}">{html.escape(_name(pid))}</text>'
                     f'<text class="prob" x="{x:.2f}" y="{y + 1.15:.2f}">{f"{prob:.2f}" if heard else "out of earshot"}</text>')
    parts.append(f'<line class="you-nose" x1="{px:.2f}" y1="{py:.2f}" x2="{px + 0.95 * math.cos(f):.2f}" y2="{py + 0.95 * math.sin(f):.2f}"/>'
                 f'<circle class="you" cx="{px:.2f}" cy="{py:.2f}" r="0.42"/>'
                 f'<text class="who" x="{px:.2f}" y="{py + 1.1:.2f}">you</text></svg>')
    parts.append(f'<div class="aud-legend">{html.escape(scene["title"])} from above. Shaded: where the player looks. '
                 f'Dashed rings: near ({CFG.near_m:g} m) and mid range ({CFG.mid_m:g} m). '
                 'The darker a person, the likelier the line is for them.</div>')
    return "".join(parts)


def facts_table(req, bands: dict, out: list[str]) -> str:
    rows = []
    for c in req.present:
        s = c.spatial
        rows.append(f"<tr><th>{html.escape(c.label)}</th><td>{s.distance or '?'}</td><td>{_yes(s.in_view)}</td>"
                    f"<td>{_yes(s.in_group)}</td><td>{_yes(s.last_spoke_with_you)}</td><td>{_yes(s.asked_you)}</td></tr>")
    for pid in out:
        rows.append(f'<tr class="away"><th>{html.escape(_name(pid))}</th><td colspan="5">out of earshot, left out of the request</td></tr>')
    return ('<div class="aud-facts"><div class="aud-kicker">What the game knows, as the facts the model reads</div>'
            '<div class="aud-scroll"><table><thead><tr><th></th><th>distance</th><th>in view</th><th>in group</th>'
            '<th>talking with you</th><th>asked you</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div></div>")


def model_reads(req) -> str:
    line, _ = line_input(req)
    cards = "\n".join(f"  {c.label}: {card_only(c)}" for c in req.present)
    facts = "\n".join(f"  {c.label}: {c.spatial.model_dump(exclude_none=True)}" for c in req.present)
    return (f"Line (encoded on every line, with the line before it):\n  {line}\n\n"
            f"Cards (what the player can see of each person; encoded once, then cached):\n{cards}\n\n"
            f"Facts and conversation state (a small vector per person, never text):\n{facts}")


def score(room: str, faces: str, talking: str, before: str, text: str):
    text = (text or "").strip()
    if not text:
        return gr.skip(), '<div class="aud-empty">Type a line, or pick one below.</div>', gr.skip(), gr.skip()
    scene = build_scene(room, faces, talking, before, text[:400])
    req, b, out = scene_request(scene, CARDS, cfg=CFG)
    words, _, _ = scene_request(scene, CARDS, text_only=True, cfg=CFG)
    t0 = time.perf_counter()
    a = MODEL.answer(req)
    ms = (time.perf_counter() - t0) * 1000
    a_words = MODEL.answer(words)
    names = {c.id: c.label for c in req.present}
    panels = ('<div class="aud-panels">'
              + _panel("With what the game knows", "the words, the cards and the spatial facts", a, names)
              + _panel("From the words alone", "the same cards and conversation, no spatial facts", a_words, names)
              + f'</div><div class="aud-time">Scored in {ms:.0f} ms on this Space\'s CPU '
              "(the first line in a room also encodes everyone's card).</div>")
    return map_svg(scene, b, a, out), panels, facts_table(req, b, out), model_reads(req)


def change_room(room: str, text: str):
    first = next(s for s in SITUATIONS if s[1] == room)
    faces, talking = first[2], NOBODY
    outs = score(room, faces, talking, "", text)
    return (gr.update(choices=faces_choices(room), value=faces), gr.update(choices=talking_choices(room), value=talking),
            "", *outs)


def load_situation(text: str):
    line, room, faces, talking, before = BY_LINE.get(text, SITUATIONS[0])
    outs = score(room, faces, talking, before, line)
    return (room, gr.update(choices=faces_choices(room), value=faces), gr.update(choices=talking_choices(room), value=talking),
            before, line, *outs)


CSS = """
.aud-intro { max-width: 72ch; }
.aud-map { width: 100%; height: auto; display: block; }
.aud-map .room { fill: var(--background-fill-secondary); stroke: var(--border-color-primary); stroke-width: 0.06; }
.aud-map .cone { fill: var(--color-accent); fill-opacity: 0.12; }
.aud-map .ring { fill: none; stroke: var(--body-text-color-subdued); stroke-opacity: 0.45; stroke-width: 0.04; stroke-dasharray: 0.18 0.18; }
.aud-legend { font-size: 0.78rem; color: var(--body-text-color-subdued); margin-top: 0.35rem; }
.aud-map .thing { fill: var(--body-text-color-subdued); fill-opacity: 0.35; }
.aud-map .thinglabel { fill: var(--body-text-color-subdued); font-size: 0.42px; font-family: var(--font); text-anchor: middle; }
.aud-map .person { fill: var(--color-accent); stroke: var(--color-accent); stroke-width: 0.07; }
.aud-map .person.away { fill: none; stroke: var(--body-text-color-subdued); stroke-dasharray: 0.12 0.1; }
.aud-map .nose, .aud-map .you-nose { stroke: var(--body-text-color-subdued); stroke-width: 0.09; stroke-linecap: round; }
.aud-map .you-nose { stroke: var(--body-text-color); stroke-width: 0.12; }
.aud-map .you { fill: var(--body-text-color); }
.aud-map text { paint-order: stroke; stroke: var(--background-fill-secondary); stroke-width: 0.16px; stroke-linejoin: round; }
.aud-map .who { fill: var(--body-text-color); font-size: 0.52px; font-weight: 600; font-family: var(--font); text-anchor: middle; }
.aud-map .prob { fill: var(--body-text-color-subdued); font-size: 0.44px; font-family: var(--font-mono); text-anchor: middle; }
.aud-panels { display: grid; grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr)); gap: 0.75rem; }
.aud-panel { border: 1px solid var(--border-color-primary); border-radius: var(--radius-lg); padding: 0.85rem 1rem; min-width: 0; }
.aud-kicker { font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--body-text-color-subdued); font-weight: 600; }
.aud-note { font-size: 0.8rem; color: var(--body-text-color-subdued); margin-top: 0.1rem; }
.aud-verdict { font-size: 1.45rem; font-weight: 700; margin-top: 0.6rem; line-height: 1.2; }
.aud-sub { font-size: 0.85rem; color: var(--body-text-color-subdued); margin-bottom: 0.6rem; }
.aud-rows { display: grid; gap: 0.3rem; }
.aud-row { display: grid; grid-template-columns: minmax(5.5rem, 9rem) 1fr 2.6rem; gap: 0.5rem; align-items: center; font-size: 0.85rem; }
.aud-who { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.aud-bar { height: 0.55rem; background: var(--background-fill-secondary); border-radius: 999px; overflow: hidden; }
.aud-bar i { display: block; height: 100%; background: var(--color-accent); border-radius: 999px; }
.aud-num, .aud-extra b { font-family: var(--font-mono); font-variant-numeric: tabular-nums; text-align: right; }
.aud-extra { display: flex; gap: 1.25rem; flex-wrap: wrap; margin-top: 0.7rem; font-size: 0.8rem; color: var(--body-text-color-subdued); }
.aud-extra b { color: var(--body-text-color); font-weight: 600; }
.aud-time { font-size: 0.78rem; color: var(--body-text-color-subdued); margin-top: 0.5rem; }
.aud-empty { color: var(--body-text-color-subdued); padding: 1rem 0; }
.aud-facts { margin-top: 0.25rem; }
.aud-scroll { overflow-x: auto; }
.aud-facts table { border-collapse: collapse; font-size: 0.82rem; width: 100%; margin-top: 0.35rem; }
.aud-facts th, .aud-facts td { padding: 0.25rem 0.5rem; text-align: left; border-bottom: 1px solid var(--border-color-primary); white-space: nowrap; }
.aud-facts thead th { font-weight: 600; color: var(--body-text-color-subdued); }
.aud-facts tr.away { color: var(--body-text-color-subdued); }
"""

INTRO = """# SpellSpeak Audience

When several AI characters listen to the same person, something has to decide who each line is for before anyone \
answers. SpellSpeak Audience is a small model that does that in milliseconds on a CPU. It reads the line, what the \
speaker can see of each character and, when the application knows it, where everyone stands. It says how likely the \
line is to be for each character, whether it is for the whole group, and when the evidence leaves it unclear.

Pick a line below, or type your own. Then change where the player looks, or who they were just talking with, and \
watch the answer move. [Model card](https://huggingface.co/spellspeak/audience) · \
[Code and examples](https://github.com/spellspeak/models/tree/main/audience)"""

FOOTER = """**How it decides, in short.** A name, or a description that fits one person, picks them out. A bare answer \
("Yes.") goes to whoever asked. A greeting or a simple question goes to the person the player looks at within mid \
range, else the person they were talking with, else the one person in their group, else the one person nearby, else \
the whole group. A thank-you or a follow-up stays with the person they were talking with. A line with consequences \
that names nobody ("You lied to me.") is unclear unless the signals agree on one person.

Trained and tested on generated scenes in game settings, in English, with up to eight people present. The spatial \
facts come from positions through the runtime's `bands` function with its default band edges (near within 3 m, mid \
within 8 m, a view cone of 40 degrees). The answers are scores; the application decides."""

with gr.Blocks(title="SpellSpeak Audience") as demo:
    # Created first so the example lines (just under the input) can set them; rendered below.
    room = gr.Radio([(ROOMS[k]["title"], k) for k in ROOMS], value="tavern", label="Room", render=False)
    faces = gr.Radio(faces_choices("tavern"), value="p:wren", label="The player looks at", render=False)
    talking = gr.Radio(talking_choices("tavern"), value=NOBODY, label="The player was just talking with", render=False)
    before = gr.Textbox(label="Their last line to the player (optional)", placeholder="Another round?", max_length=400,
                        render=False)
    reads = gr.Code(language=None, show_label=False, wrap_lines=True, render=False)
    room_map, facts, result = gr.HTML(render=False), gr.HTML(render=False), gr.HTML(render=False)
    outputs = [room_map, result, facts, reads]

    gr.Markdown(INTRO, elem_classes="aud-intro")
    with gr.Row(equal_height=False):
        with gr.Column(scale=5, min_width=320):
            line = gr.Textbox(label="The player says", placeholder="Hello.", max_length=400, submit_btn="Who is it for?")
            gr.Examples([[s[0]] for s in SITUATIONS], inputs=[line], label="Lines to try", fn=load_situation,
                        outputs=[room, faces, talking, before, line, *outputs], run_on_click=True, cache_examples=False)
            result.render()
        with gr.Column(scale=6, min_width=320):
            room_map.render()
            with gr.Group():
                room.render()
                faces.render()
                talking.render()
                before.render()
            facts.render()
    with gr.Accordion("What the model reads", open=False):
        reads.render()
    gr.Markdown(FOOTER)

    controls = [room, faces, talking, before, line]
    line.submit(score, controls, outputs)
    room.input(change_room, [room, line], [faces, talking, before, *outputs])
    for c in (faces, talking):
        c.input(score, controls, outputs)
    before.submit(score, controls, outputs)
    demo.load(load_situation, [line], [room, faces, talking, before, line, *outputs])

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(primary_hue="amber", neutral_hue="stone"), css=CSS)
