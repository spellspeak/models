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

# SpellSpeak Audience · RC2.1

When several AI characters listen to the same person, as in a game, an interactive story or any other multi-character voice experience, the application has to know who each line is for before any character answers or reacts. A name or a description often settles it, but much of what people say names nobody: "Hello.", "Who are you?", "You lied to me.". Once the characters talk among themselves, the application also needs to know who each character's line is for, to know who speaks next. The language model voicing each character could guess, but only by reading every character's context for every line. That adds latency, the characters can disagree, and a wrong guess is heard at once.

SpellSpeak Audience treats the question as classification by a small model. One pass reads the line, who said it, a card for each person who might be addressed (what the speaker can see of them) and, when the application knows it, where each one stands. It returns, for each of them, how likely it is that the line is for them. It also returns whether the evidence leaves it unclear and whether the line is for the whole group. It scores. The application decides. Its constraints are millisecond inference on a CPU, typed or transcribed speech, and an honest "unclear", so that a character can ask "Who, me?" instead of taking offence at a line that may not have been meant for them.

[Try it in your browser](https://huggingface.co/spaces/spellspeak/audience-demo) · [Examples and source](https://github.com/spellspeak/models/tree/main/audience)

## What is new in RC2.1

- **A 16-bit copy at half the size, with the same answers.** `encoder_fp16.onnx` and `head_fp16.onnx` hold the same weights stored in 16 bits: 66.0 MB against 131.7 MB. They are cast back to 32 bits when they load.
  - On the test lines, 99.92% of their answers read exactly as full precision's, with the spatial facts and without them. The other two lines only change which of several tied people is on top.
  - No scorecard item is worse. A difference counts when it is 0.1 points or more on a set of at least 30 lines.
  - A wrong person scored 0.8 or more stays at 0.69% with facts and 0.45% without.
- **Memory and speed match full precision's**, because the weights become 32-bit when they load: 364 MB resident against 370 MB. The p95 per line is within a millisecond of full precision's, on one thread of an Apple M1 Max.
- **Full precision is unchanged and stays the default.** It is the same files as RC2, byte for byte.

Full precision is the reference. Every other number on this card is full precision's, and it is the file to keep for any further training.

## What RC2 added

- **Questions to the room.** "Who knows where the mill key is?", "Anyone seen my horse?", "Does anybody here sell rope?" are for everyone who can hear them, whoever the speaker is looking at. RC1 sent most of them to the one person looked at. With the speaker facing one person, RC2 gets all 63 test lines right, with the facts and without them; RC1 gets 27% with the facts and 84% without.
- **Lines said by characters.** The speaker may be a character. The player is then one of the people the line can be said to, with a card of what the characters see of them. A character's line goes to the one it was answering, unless its words pick someone else out: "Wren, you were there, weren't you?" is for Wren, and "Ask Wren, she'd know." still answers the player.
- **Player lines read as before.** On RC1's own test lines RC2 is as good as RC1, with the facts and without them (line by line: +0.7 points and +0.0 points, neither beyond noise). Lines that should be unclear are caught more often.

| | |
|---|---|
| **Released** | 2026-10-09 · rc2.1 (package `spellspeak-audience-rc2.2`, model run `addr-r3-ettin-32m-tt-s0`, inputs `addressee-tt-0.6`) |
| **What it does** | Works out who a line is for, the player's or a character's: one person, several named on purpose, the whole group, or unclear |
| **Size** | About 33M parameters. Full precision (fp32): 131.7 MB in two graphs, a 128.0 MB encoder and a 3.7 MB head. 16-bit: 66.0 MB, a 64.1 MB encoder and a 1.9 MB head. Both use the same 3.6 MB tokenizer |
| **Speed** | p95 per line on 4 CPU threads (Apple M1 Max): 5.5 ms for 1 person, 5.7 for 2, 6.0 for 4, 6.6 for 8. On 1 thread: 11 to 12 ms. The first line of a scene also encodes everyone's card: 14 ms for 1 person to 61 ms for 8; cards are then cached. The 16-bit files time the same: within a millisecond of full precision's on one thread, timed in the same session |
| **Runtime** | ONNX Runtime and tokenizers, on CPU. A Python reference runtime ships with it, including the function that turns positions into the spatial facts and an instant rules baseline. It reads full precision unless asked for the 16-bit files (`precision="fp16"`), and it also runs RC1's model files unchanged |
| **Files** | `encoder.onnx` and `head.onnx` (full precision, the default), `encoder_fp16.onnx` and `head_fp16.onnx` (16-bit), `tokenizer.json` and `config.json`, with the reference runtime (`runtime/`), `example.py` and `requirements.txt`. `MANIFEST.json` lists every file with its size and sha256 |
| **Licence** | Apache-2.0 |

## Quick start

Everything, full precision and the 16-bit files:

```bash
pip install -U huggingface_hub
hf download spellspeak/audience --revision rc2.1 --local-dir spellspeak-audience
cd spellspeak-audience
pip install -r requirements.txt
python example.py
```

Or the small download, the 16-bit files without the full-precision graphs:

```bash
hf download spellspeak/audience --revision rc2.1 --local-dir spellspeak-audience-fp16 --exclude encoder.onnx --exclude head.onnx
cd spellspeak-audience-fp16
pip install -r requirements.txt
python example.py --fp16
```

The example puts a barkeep, an elf mercenary and an old sailor in a room, with the player facing the elf. It asks who four player lines are for, with and without the spatial facts. Then the barkeep speaks, after the player asked him where the mill key is:

```
'You in the red hat, another round.'   with facts  tomas (0.99)
'You in the red hat, another round.'   text only   tomas (0.97)
'Hello.'                               with facts  wren (0.99)
'Hello.'                               text only   the whole group (0.99)
'You lied to me.'                      with facts  wren (0.98)
'You lied to me.'                      text only   unclear (1.00): a 'Who, me?' moment
'Who knows where the mill key is?'     with facts  the whole group (0.99)
'Who knows where the mill key is?'     text only   the whole group (1.00)
Tomas: 'No idea, sorry.'               text only   player (1.00)
Tomas: 'Wren, were you there?'         text only   wren (1.00)
```

`python example.py --fp16` prints the same lines.

In your own code, with the downloaded folder as the working directory:

```python
import sys
sys.path.insert(0, "runtime")

from contracts.schemas.addressee import AddresseeRequest
from contracts.schemas.person_card import PersonCard
from harness.addressee.classifier import load_classifier

model = load_classifier(".")  # full precision: encoder.onnx, head.onnx, tokenizer.json and config.json
# model = load_classifier(".", precision="fp16")  # the 16-bit files instead: encoder_fp16.onnx and head_fp16.onnx
people = [
    PersonCard(id="tomas", label="Tomas", aliases=["the barkeep"], features=[{"key": "headwear", "value": "red hat"}]),
    PersonCard(id="wren", label="Wren", features=[{"key": "role", "value": "mercenary"}]),
]
answer = model.answer(AddresseeRequest(text="You in the red hat, another round.", present=people))
print(answer.top())                       # tomas

# A character speaks: the player becomes one of the people, and the speaker is not among them.
player = PersonCard(id="player", label="the traveller", features=[{"key": "clothing", "value": "a green cloak"}])
answer = model.answer(AddresseeRequest(speaker="tomas", speaker_label="Tomas", text="No idea, sorry.",
                                       present=[player, people[1]],
                                       history=[{"speaker": "player", "to": ["tomas"], "text": "Where's the mill key?"}]))
print(answer.top())                       # player
```

## Input and output

- **Input:** the line, typed or from speech to text, with the line before it, and who said it: the player, or a character (`speaker` and `speaker_label`). Then everyone who might be addressed (tested up to 8 people), one card each. When a character speaks, the player is one of them, with id `player`, and the speaker is not. A card holds a label ("Tomas", or "the barkeep" when the speaker would not know the name), aliases, and open `key: value` features for what the speaker can see. The application chooses its own keys: role, clothing, what someone holds or is doing, where they stand. A card is read up to 96 tokens, the line up to 64.
- **Optional facts per person**, from the speaker's place: distance (near, mid-range, far), in view, in the speaker's group, following the speaker, has asked the speaker something, spoke with the speaker last. `bands.py` turns positions and facings into these; give it the speaker's position. Up to four earlier lines of the conversation say who spoke to whom.
- **Per person:** the probability that the line is for them.
- **Per line:** `unclear` (the evidence fits several people, so nobody should take it personally yet) and `to_group` (the line is for everyone the speaker is talking with, or everyone who can hear a question to the room).

The rules it learned:
- A name, an alias or a description that fits one person picks them out, whatever the speaker is looking at. A name the line only talks about ("Ask Wren") does not.
- Group words ("Right, listen to me", "Evening, all") are for the speaker's group. A question to the room ("Who knows...?", "Anyone seen...?") is for everyone who can hear it. When a line has both, the group words win.
- A bare answer goes to whoever asked. A character's line that picks no one out goes to the one it was answering.
- A simple, harmless line ("Hello.", "Who are you?", "Thanks.") is never unclear. A line that carries the conversation on stays with the person the speaker was talking with. An opener goes to the person the speaker is looking at, else the conversation partner, else the one person nearby, else the whole group.
- A line with consequences that names nobody ("You lied to me.") is unclear unless the signals agree on one person.

## Performance (held-out test set, committee-checked labels)

Spatial facts are optional, so every measure is scored twice on the same lines: as the line is given, with its facts, and again with every fact removed, each against its own answer. On the main test 2,527 lines pair up this way; 1,089 of them carry no facts and score the same in both columns.

| Measure | With spatial facts | Text only |
|---|---|---|
| Whole answer right (people, unclear and group), main test (2,527 lines) | 95.2%. RC1 89.9%, rules 90.0% | 96.6%. RC1 94.2%, rules 91.1% |
| RC1's test lines (1,908); the difference line by line against RC1 on the 1,907 whose answers did not change in this release | 94.4% (+0.7 points, not beyond noise) | 96.1% (+0.0 points, not beyond noise) |
| Questions to the room, the speaker facing one person: test lines (63) / hand-placed scenes (50) | 100% / 96.0%. RC1 27.0% / 28.0% | 100% / 100%. RC1 84.1% / 74.0% |
| Lines said by characters: test lines (288) / hand-built scenes (30) | 97.2% / 93.3%. RC1 86.5% / 86.7% | 97.9% / 96.7%. RC1 89.6% / 90.0% |
| Simple lines such as "Hello." and "Who are you?" (689 lines) | 93.3% right; called unclear 1.6% | 98.3% right; called unclear 1.3% |
| A wrong person scored 0.8 or more on a clear line | 0.7% | 0.4% |
| Top person | 96.8% | 98.3% |
| Lines that should be unclear, caught | 92.2% | 94.8% |
| Clear lines called unclear | 1.2% | 1.4% |
| Facts that contradict a unique description, words followed | 97.2% | 99.5% (the same lines) |
| Settings never seen in training (714 lines) | 94.3% | 96.6% |
| Hand-written worked examples / hand-placed spatial scenes | 55 of 57 / 51 of 51 | 55 of 57 / 50 of 51 |
| Calibration error: person, unclear, group | 0.018, 0.015, 0.005 | 0.014, 0.011, 0.005 |
| For scale: a large language model asked the same questions, main test | 69.6% | 78.3% |

What the facts add: on 492 of the 1,438 test lines that carry facts, the facts settle what the words leave open (a hello goes to the one looked at instead of the whole group). There RC2 gives the answer the facts settle 94.1% of the time; without the facts the right answer is the group or "unclear", which it gives 98.8% of the time. The facts make the answer more specific; they do not make it more often right.

Measured on lines as given only:
- Spatial facts drawn the way an application makes them (2,748 lines): 96.9% right, top person 98.5%.
- Lines worded unlike their construction, labelled by the committee with their facts: no text-only answer exists, so they are left out of the columns above (374 lines). As given, RC2 gets 58.8% of them right, and 65.4% of all 590 such lines.

## How it was made

- **Model:** Ettin-32M (`jhu-clsp/ettin-encoder-32m` at 1b8ba06, MIT) in two towers. Each person's card is encoded once, and the line once per utterance. A small head scores each person from the two, their spatial facts and conversation state, and the word-match signals of the rules baseline.
- **Scenes:** 49,720 scenes built by code in 18 settings, each with a known answer from written rules of evidence. Lines and casts were written for this project by Qwen3.8-27B (Apache-2.0). RC2 adds 7,731 scenes: questions to the room, lines said by characters (one cast member speaks, another plays the player), corrections, and short lines with consequences that carry facts. Each line also has a text-only twin and some a speech-to-text twin.
- **Labels:** the construction's answer. On dev and test it is checked by the majority vote of a committee of three large language models, which agreed with it on 88% to 98% of lines (98.1% on RC2's new lines). Lines whose words broke their brief take the committee's label. One member of the committee was replaced while this release was tested; the test lines were voted again, and every number here uses the new votes.
- **Training:** the people of every training line in a new order in every batch, and a third of the lines with fresh spatial facts each epoch.

## Use and limits

- **Use it** to decide who answers a line, who speaks next, and whose feelings a line may change. Treat `unclear` as a cue for "Who, me?" and hold any change in feeling until the target is clear. **Do not use it** to judge real people.
- **English only.** Up to 8 people and four lines of history.
- **It misses things.** About one line in thirteen that should be unclear is given to a person when facts are present. An opener right after a conversation ("And what's your name?") is ambiguous. It does not know that "check this wound" means the doctor. A character's statement that starts with a name ("Officer Lunn does, mostly.") can be read as a call to that person. "Does anyone know, Wren?" without spatial facts can go to everyone. Lines worded unlike anything it was trained on are the weakest (59% to 65% right).
- **A question to the room in the middle of a conversation** goes to everyone who can hear it, not only the conversation group. An application that wants otherwise can keep only its group in the request.
- **Spatial facts depend on the application's band edges.** Tune them (`BandConfig` in `bands.py`).
- **It has not met real users yet.** It was tested in game settings only, on generated and hand-written lines, not on logs from real people or from other multi-character voice experiences.

The numbers come from the training repository's reports for this release: `2026-10-09-addr-r3.md` and `2026-10-09-addr-r3-setup.md` at commit `fce88bf`, and for the 16-bit files `2026-10-09-addr-precision.md` at commit `28e72a8`. The full-precision files are RC2's, trained and exported at git tag `spellspeak-audience-rc2` (commit `97f3320`), and this package was built at git tag `spellspeak-audience-rc2.2`. That repository is private.
