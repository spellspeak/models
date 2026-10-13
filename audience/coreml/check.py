"""Check a Core ML conversion against ONNX Runtime on the same requests.

    uv run check.py                          # build/rc2.1 against rc2.1's ONNX graphs from Hugging Face
    uv run check.py --units all --lines 2000

Every request goes to both runtimes. A reading is what example.py prints: unclear first (at least 0.5), then the
whole group (at least 0.5), then the top person. The requests are generated from fixed seeds: the example's tavern,
the Pipecat example's garage, a pair, and crowds of up to eight; the player or a character speaking; with and without
spatial facts; with up to four lines of history.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import statistics
import time

from classifier import HERE, load_coreml_classifier

PLAYER_LINES = [
    "You in the red hat, another round.", "Hello.", "You lied to me.", "Who knows where the mill key is?",
    "Tomas, another round.", "Wren, were you there last night?", "Hey, all of you!", "Listen up, everyone.",
    "Anyone seen my horse?", "Does anybody here sell rope?", "Good evening.", "Yes.", "No idea, sorry.",
    "What's your name?", "How much for a room?", "You're useless.", "Get out of my way.", "Thanks, both of you.",
    "Nova and Kai, what's the plan?", "Bruno, can you fix my bike?", "Oi, you!", "You in the orange jumpsuit, wait up.",
    "The robot by the door, what do you see?", "Kai, can you get into that terminal?", "Which of you is the mechanic?",
    "Who's got a light?", "Should I skip the gym today?", "Is it wrong to eat cake for breakfast?", "Angel, help me out.",
    "Devil, tempt me.", "Hey, you with the horns, what should I eat?", "Tell me, halo, should I go?", "What do you think?",
    "I don't know, it feels greedy.", "Can any of you help me?", "Excuse me.", "Sorry, I didn't mean that.",
    "You there, with the longbow.", "Old man, where's the harbour?", "Can I buy you a drink?", "That's not fair.",
    "I'll take two.", "Right, listen to me, all of you.", "You two, stop arguing.", "Bruno, ask Atlas if the door's locked.",
    "Nova, who can fix my bike?", "Is there anyone here who can read this?", "Where am I?", "Goodbye.",
    "Atlas, scan the room.", "Hey, barkeep!", "Tell Wren I said thanks.", "You, talking to the barkeep.", "Why?",
    "Come with me.", "Have you seen anyone suspicious?", "Who are you?", "Do you two know each other?", "Cheers.",
]
CHARACTER_LINES = [
    "No idea, sorry.", "Wren, were you there?", "You're no fun at all.", "Don't listen to them.", "Ask Bruno, he fixes bikes.",
    "Why are you always so serious?", "Because I care about them.", "Go to the gym. You'll thank yourself tonight.",
    "Oh, please, Angel. One lazy day won't ruin anything.", "Here you go, another round.", "I saw nothing.",
    "Can I help you?", "Keep your voice down.", "Says the one with a halo.", "Fine, I'll do it.", "Is that so?",
]


def card(pid: str, label: str, features: dict[str, str], aliases: tuple[str, ...] = ()):
    from contracts.schemas.person_card import PersonCard

    return PersonCard.model_validate({"id": pid, "label": label, "aliases": list(aliases),
                                      "features": [{"key": k, "value": v} for k, v in features.items()]})


def casts() -> dict[str, list]:
    tavern = [card("tomas", "Tomas", {"role": "barkeep", "headwear": "red hat", "holding": "a tankard"}, ("barkeep",)),
              card("wren", "Wren", {"role": "mercenary", "race": "elf", "carrying": "a longbow"}),
              card("oskar", "the old sailor", {"build": "stout", "holding": "a pipe"})]
    garage = []
    for e in json.loads((HERE.parent / "examples" / "pipecat" / "characters.json").read_text()):
        garage.append(card(e["id"], e["name"], {"role": e["role"].lower(), **e["features"]}, tuple(e.get("aliases", []))))
    pair = [card("angel", "Angel", {"role": "angel", "appearance": "white robe, feathered wings and a golden halo"}),
            card("devil", "Devil", {"role": "devil", "appearance": "red skin, little horns and a pointy tail"})]
    everyone = tavern + garage + pair
    return {"tavern": tavern, "garage": garage, "pair": pair, "everyone": everyone}


def requests(count: int, seed: int = 7):
    from contracts.schemas.addressee import PLAYER, AddresseeRequest, HistoryLine
    from contracts.schemas.person_card import SpatialFacts

    rng = random.Random(seed)
    groups = casts()
    player_card = card("player", "the traveller", {"clothing": "a green cloak"})
    out = []
    while len(out) < count:
        name = rng.choice(["tavern", "garage", "pair", "crowd", "one"])
        if name == "crowd":
            people = rng.sample(groups["everyone"], rng.randint(4, 8))
        elif name == "one":
            people = [rng.choice(groups["everyone"])]
        else:
            people = list(groups[name])
        speaker = PLAYER
        if rng.random() < 0.3 and len(people) >= 1:
            speaker_card = rng.choice(people)
            speaker = speaker_card.id
            people = [player_card] + [c for c in people if c.id != speaker]
        facts = rng.random() < 0.5
        if facts:
            last = rng.choice([None] + [c.id for c in people])
            people = [c.model_copy(update={"spatial": SpatialFacts(
                distance=rng.choice(["near", "mid", "far", None]), in_view=rng.choice([True, False, None]),
                in_group=rng.choice([True, False, None]), following=rng.random() < 0.1, asked_you=rng.random() < 0.1,
                last_spoke_with_you=None if last is None else c.id == last)}) for c in people]
        ids = [c.id for c in people]
        known = ids + [PLAYER] if speaker != PLAYER else ids
        history = []
        for _ in range(rng.randint(0, 4)):
            who = rng.choice(known + ([speaker] if speaker != PLAYER else [PLAYER]))
            to = [t for t in rng.sample(known + [speaker] if speaker != PLAYER else known + [PLAYER], rng.randint(0, 2)) if t != who]
            history.append(HistoryLine(speaker=who, to=to, text=rng.choice(PLAYER_LINES + CHARACTER_LINES)))
        try:
            if speaker == PLAYER:
                req = AddresseeRequest(text=rng.choice(PLAYER_LINES), present=people, history=history)
            else:
                req = AddresseeRequest(speaker=speaker, speaker_label=speaker_card.label, text=rng.choice(CHARACTER_LINES),
                                       present=people, history=history)
        except ValueError:
            continue  # a combination the schema refuses, such as a history naming someone absent
        out.append(req)
    return out


def reading(a) -> str:
    if a.unclear >= 0.5:
        return "unclear"
    if a.to_group >= 0.5:
        return "group"
    return a.top()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a Core ML conversion against ONNX Runtime.")
    parser.add_argument("--coreml", type=pathlib.Path, default=HERE / "build" / "rc2.1", help="convert.py's output")
    parser.add_argument("--model-dir", type=pathlib.Path, help="the release's ONNX files (default: from Hugging Face)")
    parser.add_argument("--units", choices=("cpu", "cpu_and_gpu", "all"), default="cpu")
    parser.add_argument("--lines", type=int, default=1500)
    args = parser.parse_args()
    meta = json.loads((args.coreml / "coreml.json").read_text())
    coreml = load_coreml_classifier(args.coreml, args.units)
    from harness.addressee.classifier import load_classifier

    source = args.model_dir
    if source is None:
        from huggingface_hub import snapshot_download

        files = ["encoder_fp16.onnx", "head_fp16.onnx"] if meta["precision"] == "fp16" else ["encoder.onnx", "head.onnx"]
        source = pathlib.Path(snapshot_download("spellspeak/audience", revision=meta["release"],
                                                allow_patterns=files + ["tokenizer.json", "config.json"]))
    reference = load_classifier(source, threads=4, precision=meta["precision"])

    # Grouped by the number of people, so the Python classifier loads each head function once.
    reqs = sorted(requests(args.lines), key=lambda r: len(r.present))
    agree = top_agree = 0
    diffs: list[float] = []
    by_kind: dict[str, list[int]] = {}
    misses = []
    times = {"coreml": [], "onnxruntime": []}
    for req in reqs:
        ref, t_ref = reference.timed(req)
        got, t_got = coreml.timed(req)
        times["onnxruntime"].append(t_ref)
        times["coreml"].append(t_got)
        d = max([abs(ref.addressed[i] - got.addressed[i]) for i in req.ids] + [abs(ref.unclear - got.unclear),
                                                                             abs(ref.to_group - got.to_group)])
        diffs.append(d)
        same = reading(ref) == reading(got)
        agree += same
        top_agree += ref.top() == got.top()
        kind = ("character" if req.npc_speaker else "player") + (", facts" if req.has_spatial else ", text only")
        tally = by_kind.setdefault(kind, [0, 0])
        tally[0] += same
        tally[1] += 1
        if not same:
            misses.append((req, ref, got))
    n = len(reqs)
    print(f"{n} requests: the same reading {agree}/{n} ({100 * agree / n:.2f}%), the same top person {top_agree}/{n}")
    for kind, (a, b) in sorted(by_kind.items()):
        print(f"  {kind:22} {a}/{b}")
    print(f"largest probability difference {max(diffs):.2e}, median {statistics.median(diffs):.2e}")
    warm = slice(20, None)  # the first requests encode every card once
    for name, ts in times.items():
        print(f"{name:12} median {statistics.median(ts[warm]):.1f} ms per line, p95 {sorted(ts[warm])[int(0.95 * len(ts[warm]))]:.1f} ms")
    for req, ref, got in misses[:10]:
        print(f"  differs: {req.text!r} reference {reading(ref)} {ref.model_dump()} coreml {reading(got)} {got.model_dump()}")


if __name__ == "__main__":
    main()
