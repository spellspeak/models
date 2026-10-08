---
license: apache-2.0
language:
  - en
library_name: onnx
pipeline_tag: text-classification
base_model: jhu-clsp/ettin-encoder-32m
tags:
  - onnx
  - voice-agents
  - conversational-ai
  - multi-agent
  - multi-party-conversation
  - addressee-detection
  - speech
  - real-time
  - pipecat
  - npc
  - dialogue
---

# SpellSpeak Audience · RC1

When several AI characters listen to the same person, as in a game, an interactive story or any other multi-character voice experience, the application has to know who each line is for before any character answers or reacts. A name or a description often settles it, but much of what people say names nobody: "Hello.", "Who are you?", "You lied to me.". The language model voicing each character could guess, but only by reading every character's context for every line. That adds latency, the characters can disagree, and a wrong guess is heard at once.

SpellSpeak Audience treats the question as classification by a small model. One pass reads the line, a card for each character present (what the speaker can see of them) and, when the application knows it, where each one stands. It returns, for each character, how likely it is that the line is for them. It also returns whether the evidence leaves it unclear and whether the line is for the whole group. It scores. The application decides. Its constraints are millisecond inference on a CPU, typed or transcribed speech, and an honest "unclear", so that a character can ask "Who, me?" instead of taking offence at a line that may not have been meant for them.

[Try it in your browser](https://huggingface.co/spaces/spellspeak/audience-demo) · [Examples and source](https://github.com/spellspeak/models/tree/main/audience)

| | |
|---|---|
| **Released** | 2026-10-08 · rc1 (package `spellspeak-audience-rc1.2`, model run `addr-r2b-ettin-32m-tt-s1`) |
| **What it does** | Works out who a player's line is for: one person, several named on purpose, the whole group, or unclear |
| **Size** | About 33M parameters · 135 MB ONNX (fp32) in two graphs: a 128 MB encoder and a 3.7 MB head |
| **Speed** | p95 per line on 4 CPU threads (Apple M1 Max): 6.0 ms for 1 person, 6.4 for 2, 6.9 for 4, 7.1 for 8. On 1 thread: 11 to 13 ms. The first line of a scene also encodes everyone's card: 14 ms for 1 person to 62 ms for 8; cards are then cached |
| **Runtime** | ONNX Runtime and tokenizers, on CPU. A Python reference runtime ships with it, including the function that turns positions into the spatial facts and an instant rules baseline |
| **Files** | `encoder.onnx`, `head.onnx`, `tokenizer.json` and `config.json`, with the reference runtime (`runtime/`), `example.py` and `requirements.txt`. `MANIFEST.json` lists every file with its size and sha256 |
| **Licence** | Apache-2.0 |

## Quick start

```bash
pip install -U huggingface_hub
hf download spellspeak/audience --revision rc1 --local-dir spellspeak-audience
cd spellspeak-audience
pip install -r requirements.txt
python example.py
```

The example puts a barkeep, an elf mercenary and an old sailor in a room, with the player facing the elf. It asks who three lines are for, with and without the spatial facts:

```
'You in the red hat, another round.'   with facts  tomas (0.99)
'You in the red hat, another round.'   text only   tomas (1.00)
'Hello.'                               with facts  wren (0.99)
'Hello.'                               text only   the whole group (0.99)
'You lied to me.'                      with facts  wren (0.96)
'You lied to me.'                      text only   unclear (0.99): a 'Who, me?' moment
```

In your own code, with the downloaded folder as the working directory:

```python
import sys
sys.path.insert(0, "runtime")

from contracts.schemas.addressee import AddresseeRequest
from contracts.schemas.person_card import PersonCard
from harness.addressee.classifier import load_classifier

model = load_classifier(".")  # the folder with encoder.onnx, head.onnx, tokenizer.json and config.json
people = [
    PersonCard(id="tomas", label="Tomas", aliases=["the barkeep"], features=[{"key": "headwear", "value": "red hat"}]),
    PersonCard(id="wren", label="Wren", features=[{"key": "role", "value": "mercenary"}]),
]
answer = model.answer(AddresseeRequest(text="You in the red hat, another round.", present=people))
print(answer.top())                       # tomas
print(answer.addressed)                   # one probability per person: tomas 0.996, wren 0.00003
print(answer.unclear, answer.to_group)    # both near 0: the words pick out one person
```

## Input and output

The runtime calls the person speaking the player. Everyone who might be addressed gets a card.

- **Input:** the player's line, typed or from speech to text, with the line before it. Then everyone present (tested up to 8 people), one card each. A card holds a label ("Tomas", or "the barkeep" when the player would not know the name), aliases, and open `key: value` features for what the player can see. The game chooses its own keys: role, clothing, what someone holds or is doing, where they stand. A card is read up to 96 tokens, the line up to 64.
- **Optional facts per person:** distance (near, mid-range, far), in view, in the player's group, following the player, has asked the player something, spoke with the player last. `bands.py` turns positions and facings into these. Up to four earlier lines of the conversation say who spoke to whom.
- **Per person:** the probability that the line is for them.
- **Per line:** `unclear` (the evidence fits several people, so nobody should take it personally yet) and `to_group` (the line is for everyone the player is talking with).

The rules it learned:
- A name, an alias or a description that fits one person picks them out, whatever the player is looking at.
- A bare answer goes to whoever asked.
- A simple, harmless line ("Hello.", "Who are you?", "Thanks.") is never unclear. A line that carries the conversation on stays with the person the player was talking with. An opener goes to the person the player is looking at, else the conversation partner, else the one person nearby, else the whole group.
- A line with consequences that names nobody ("You lied to me.") is unclear unless the signals agree on one person.

## Performance (held-out test set, committee-checked labels)

| Measure | Result |
|---|---|
| Whole answer right (people, unclear and group), main test (3,294 lines) | 91.6% (95% interval 90.6 to 92.5). Rules baseline 86.4% |
| Simple lines such as "Hello." and "Who are you?" (1,193 lines) | 91.7% right; called unclear 0.7% |
| A wrong person scored 0.8 or more on a clear line | 1.3% |
| Top person, text only / with spatial facts | 98.6% / 91.1% |
| Lines that should be unclear, caught | 83.4% |
| Clear lines called unclear | 1.0% |
| Facts that contradict a unique description, words followed | 90.2% |
| Spatial facts drawn the way a game makes them (2,044 lines) | 96.5% right; top person 98.2% |
| Game settings never seen in training (919 lines) | 90.0% right |
| Lines worded unlike their construction, labelled by the committee (488 lines) | 64.3% right |
| Hand-written worked examples / hand-placed spatial scenes | 42 of 44 / 74 of 76 |
| Calibration error: person, unclear, group | 0.011, 0.005, 0.007 |
| For scale: a large language model asked the same questions | 63.8% right on 1,686 committee-labelled test lines (this model 89.0% on the same lines) |

## How it was made

- **Model:** Ettin-32M (`jhu-clsp/ettin-encoder-32m` at 1b8ba06, MIT) in two towers. Each person's card is encoded once, and the line once per utterance. A small head scores each person from the two, their spatial facts and conversation state, and the word-match signals of the rules baseline.
- **Scenes:** 41,989 scenes built by code in 18 game settings, each with a known answer from written rules of evidence. Lines and casts were written for this project by Qwen3.8-27B (Apache-2.0). The scenes include 12,730 of greetings, simple questions and lines with consequences, and openers said right after a conversation. Each line also has a text-only twin and some a speech-to-text twin.
- **Labels:** the construction's answer. On dev and test it is checked by the majority vote of a committee of three large language models, which agreed on 88% to 97% of lines. Lines whose words broke their brief take the committee's label.
- **Spatial facts:** drawn from positions through the bands function. A third of the training lines get fresh facts each epoch.

## Use and limits

- **Use it** to decide who answers a line and whose feelings it may change. Treat `unclear` as a cue for "Who, me?" and hold any change in feeling until the player makes the target clear. **Do not use it** to judge real people.
- **English only.** Up to 8 people and four lines of history.
- **It misses things.** About one line in six that should be unclear is given to a person. An opener right after a conversation ("And what's your name?") is ambiguous: the committee disagreed with the rule on 22% of those. It does not know that "check this wound" means the doctor.
- **Spatial facts depend on the game's band edges.** Tune them for each game (`BandConfig` in `bands.py`).
- **It has not met real players yet.** It was tested on generated and hand-written lines in game settings, not on logs from real players or from other multi-character settings.

The numbers come from the training repository's reports for this release (`2026-10-08-addr-r2-simple-lines.md` and `2026-10-08-addr-first-models.md`, at git tag `spellspeak-audience-rc1`). That repository is private.
