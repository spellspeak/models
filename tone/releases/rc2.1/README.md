---
license: apache-2.0
language:
  - en
library_name: onnx
pipeline_tag: text-classification
base_model: sentence-transformers/all-MiniLM-L6-v2
tags:
  - onnx
  - voice-agents
  - conversational-ai
  - multi-agent
  - multi-party-conversation
  - emotion-recognition
  - dialogue-acts
  - turn-taking
  - real-time
  - pipecat
  - npc
  - dialogue
---

# SpellSpeak Tone · RC2.1

When several AI characters share one conversation, as in a game, an interactive story or any other multi-character voice experience, each of them needs a structured reading of every line: how the speaker sounds, what the line does to each person present, and whether it leaves a question open for someone else to answer. The language model voicing a character could produce that reading, but only through extra output tokens, training or tool calls. That adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene.

SpellSpeak Tone treats the reading as multi-task classification by a separate small model. One pass over a line predicts the speaker's emotion, the social act directed at each person present with a hostility probability per person, and, new in rc2, the move the line makes in the conversation: does it ask, answer, pass on a rumour, say it does not know, hold back, or close the exchange. The application uses the tags for faces, feelings and who speaks next. Its constraints are millisecond inference on a CPU, robustness to unstructured user input, and rare false hostility.

[Examples and source](https://github.com/spellspeak/models/tree/main/tone)

## What is new in RC2.1

- **A 16-bit file at half the size, with the same answers.** `model_fp16.onnx` is rc2's model with its weights stored in 16 bits: 55.7 MB against 111.1 MB. On 5,204 test lines, read in all four columns with and without the optional inputs, at most one line in a column gets a different tag from full precision. No scorecard measure changes beyond noise.
- **The same speed, and no memory saved.** It computes in 32 bits. p95 per line for 8 people on 4 threads of an Apple M1 Max: 10.0 ms against 9.9 ms for full precision, timed side by side (1 thread: 29.4 against 29.5 ms). Resident memory: 222 MB against 201 MB. What it saves is the download and the disk.
- **Full precision is unchanged and stays the default.** `model.opt.onnx`, `model.onnx`, `tokenizer.json` and `config.json` are rc2's, byte for byte. Ask for the 16-bit file with `precision="fp16"`, or `python example.py --fp16`.

Full precision is the reference: every other number on this card is full precision's, and it is the file to keep for any further training.

| | |
|---|---|
| **Released** | 2026-10-09 · rc2.1 (package `spellspeak-tone-rc2.2`) |
| **What it does** | Reads one line of dialogue and tags the speaker's emotion, the social act toward each person present, and the line's move in the conversation |
| **What changed from rc1** | One new output per line, the move, from two extra encoder layers and a small head beside rc1's unchanged encoder, in the same pass. Every rc1 output (emotion, acts, intensities, backchannel, hostility, confidences) is rc1's, checked on every one of 3,754 test lines |
| **Size** | 27.9M parameters (rc1's 23.6M plus 4.3M for the move) · 111.1 MB ONNX in full precision (fp32), 55.7 MB with the weights in 16 bits (`model_fp16.onnx`) |
| **Speed** | p95 per line on 4 CPU threads (Apple M1 Max): 7.0 ms for 1 person, 7.9 for 4, 9.7 for 8 (rc1: 5.5, 6.6, 7.3). On 1 thread: 19 to 28 ms. The 16-bit file takes the same time |
| **Runtime** | ONNX Runtime (1.24 or later) and tokenizers, on CPU. A Python reference runtime ships with it |
| **Files** | `model.opt.onnx` (the graph to run), `model.onnx` (the same graph unoptimized), `model_fp16.onnx` (the graph to run with its weights in 16 bits), `tokenizer.json` and `config.json`, with the reference runtime (`runtime/`), `example.py` and `requirements.txt`. `MANIFEST.json` lists every file with its size and sha256 |
| **Licence** | Apache-2.0 |

## Quick start

```bash
pip install -U huggingface_hub
hf download spellspeak/tone --revision rc2.1 --local-dir spellspeak-tone
cd spellspeak-tone
pip install -r requirements.txt
python example.py
```

The example puts three characters and the player in a room. The player asks everyone a question, the characters answer in different ways, and two more lines follow:

```
player to everyone: 'Who knows where the mill key is?'
    move asks (0.96) · emotion neutral · acts: none
Mara to player: "It's under the counter, love."
    move answers (0.91) · emotion neutral · acts: none
Tomas to player: 'I heard the miller had it last.'
    move hedges (0.98) · emotion neutral · acts: none
Wren to player: 'Why do you want to know?'
    move withholds (0.52) · emotion neutral · acts: none
Tomas to player: 'No idea, sorry.'
    move doesnt_know (0.99) · emotion neutral · acts: player apology
player to Mara: "thanks, that's all i needed"
    move closes (0.99) · emotion happy · acts: Mara thanks
player to Tomas: "Touch my horse again and you'll regret it."
    move asks (0.59) · emotion angry · acts: Tomas threat
```

A group conversation can play Mara's answer first, add Tomas's rumour as a second voice, and drop the dodge and the "no idea".

The small download leaves out the two full-precision graphs, about 56 MB in all, and runs the 16-bit file:

```bash
hf download spellspeak/tone --revision rc2.1 --local-dir spellspeak-tone-small --exclude model.onnx --exclude model.opt.onnx
cd spellspeak-tone-small
pip install -r requirements.txt
python example.py --fp16
```

It prints exactly the same output.

In your own code, with the downloaded folder as the working directory:

```python
import sys
sys.path.insert(0, "runtime")

from contracts.schemas.line_tags import LineInput
from harness.expression.classifier import LineClassifier

tone = LineClassifier(".")  # full precision (model.opt.onnx), the default
# tone = LineClassifier(".", precision="fp16")  # the 16-bit file (model_fp16.onnx), for the small download
tags = tone.tag(LineInput(speaker="Wren", speaker_kind="npc", to="Tomas", targets=["Tomas", "Mara", "player"],
                          text="Aye, I saw the whole thing.", previous="Tomas: Wren, you were there, weren't you?"))
print(tags.exchange)                      # label='answers' confidence=0.9413
print(tags.emotion, tags.acts["Tomas"])   # neutral, act='none' ...
```

## Input and output

- **Input:** the line, the line before it, who speaks (the player or a character), who it is said to (or the room), and everyone present (tested up to 8 people; 160 tokens at most). Who it is said to and the line before are optional, and help: see the table below.
- **Per line:** an emotion (neutral, happy, amused, angry, sad, afraid, surprised, disgusted, contemptuous) with intensity (low, medium, high) and a confidence. Whether the line is only a listening sound such as "mm-hm" (backchannel). New in rc2: the **move**, with a confidence.
- **Per person:** an act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and a confidence.
- **The moves.** asks: wants a reply or an action. answers: gives what was asked for, or offers information. hedges: offers something second-hand or unsure. doesnt_know: says it does not know. withholds: declines, deflects or dodges. closes: winds the exchange down and wants no reply. other: anything else. After doesnt_know or withholds, a question is still open, so someone else may answer it.
- **Hostile** means insult, threat, accusation, or demand at high intensity. A tag is hostile when the hostility score reaches 0.775.
- **Confidence** is the chance the tag is right (calibrated). For a hostile tag it is the chance the line is hostile toward that person.

## Performance (held-out test sets, committee labels)

The move:

| Measure | Result |
|---|---|
| Move macro-F1, main test (824 lines) | 0.812 (95% interval 0.781 to 0.842) |
| For scale: two frontier labellers agree with each other at | 0.845 on the same lines |
| Answered or still open: lines labelled answers, doesnt_know or withholds (454) | 82.6% on the right side (78.8% to 85.8%). **The target was 90%, and it is not met.** 7.5% land on the wrong side |
| The same, on characters' lines only (363) | 86.2% |
| Asks or not (824 lines) | 95.3% (93.6% to 96.5%) |
| Move macro-F1 on player lines (324), between characters (109), in settings never seen in training (293) | 0.737, 0.754, 0.712 |
| Move confidence calibration error | 0.04 |

The two frontier labellers themselves agree on "answered or still open" only about 89% of the time, so the 90% target sits near the labels' own ceiling. rc2 mixes answers with refusals most. A dodge often looks like an answer.

The emotion and the acts, the same as rc1:

| Measure | Result |
|---|---|
| Act macro-F1, main test (1,905 lines) | 0.678 (0.648 to 0.703) |
| Emotion macro-F1, main test | 0.677 |
| Natural player speech (900 lines): act F1, emotion F1 | 0.761, 0.711 |
| Game settings never seen in training (900 lines): act F1 | 0.784 |
| Harmless lines called hostile: prose-style, player speech | 1.1%, 1.7% |
| Hostile lines caught: main test, player speech | 72%, 78% |
| Calibration error: act tags, emotion | 0.08, 0.05 |
| For scale: two frontier labellers agree with each other at | 0.766 act F1, 0.709 emotion F1 |

### With and without the optional inputs

The same test lines, scored again without who a line is said to, without the line before, and without either, against the same labels:

| Measure | As given | Without `to` | Without the line before | Without either |
|---|---|---|---|---|
| Act macro-F1, main test | 0.678 | 0.571 | 0.663 | 0.553 |
| Emotion macro-F1, main test | 0.677 | 0.676 | 0.670 | 0.666 |
| Harmless lines called hostile, prose | 1.1% | 0.7% | 0.9% | 0.8% |
| Hostile lines caught, main test | 72% | 70% | 73% | 70% |
| Move macro-F1 | 0.812 | 0.810 | 0.740 | 0.707 |
| Answered or still open | 82.6% | 81.7% | 67.2% | 63.7% |
| Asks or not | 95.3% | 94.5% | 92.0% | 89.2% |

- **Send who a line is said to when you know it.** Without it, a "you" in a group is read as aimed at everyone. On those lines, harmless pairs called hostile go from 2.1% to 17.6%.
- **Send the line before for the move.** A bare "Yes." is an answer only after a question. Without the line before, "answered or still open" drops 15 points.

### The 16-bit file

The same 5,204 test lines, tagged by `model_fp16.onnx` and by full precision, in the same four columns:

| | As given | Without `to` | Without the line before | Without either |
|---|---|---|---|---|
| Lines with every tag the same as full precision | 100% | 100% | 99.98% (one move differs) | 99.98% (one act toward one person differs) |

Rounded as the tables above show them, every measure is the same with the 16-bit file. Calibration error moves by 0.0012 at most.

## How it was made

- **Model:** MiniLM-L6 (`sentence-transformers/all-MiniLM-L6-v2` at 1110a24, Apache-2.0) with six small heads, unchanged from rc1. For the move, trainable copies of its top two layers read its fourth layer's output, and a small head reads them. The encoder itself was frozen, so every rc1 output is unchanged.
- **Distillation:** the emotion and the acts from three Ettin-1B teachers (`jhu-clsp/ettin-encoder-1b`, MIT) over 359,424 lines, plus 11,486 lines labelled directly. The move from three more Ettin-1B teachers, fine-tuned on the move labels, over 113,201 lines, plus 3,296 labelled training lines (noisy copies included).
- **Labels:** the majority vote of a committee of three large language models. 4,992 lines were labelled for the move.
- **Lines:** our own game dialogue, Project Gutenberg dialogue, GoEmotions (Apache-2.0), Civil Comments (CC0), and lines written for this project by Qwen3.8-27B. The last include 95,000 of natural player speech, 48,000 aimed at sarcasm, doubling down and implied threats, and 9,126 short exchanges for the rarer moves: rumours, dodges, "don't know", closings, and exchanges between characters.
- **Calibration:** the hostility threshold and the act and emotion curves are rc1's. A curve for the move's confidence was fitted on the dev set.
- **The 16-bit file:** full precision's graph with every weight tensor of 1,024 values or more stored in 16 bits and turned back into 32 bits by the graph itself. Inputs, outputs and arithmetic stay 32-bit, so the same runtime and the same calibration curves serve both files.

## Use and limits

- **Use it** for character reactions and turn-taking in multi-character conversations: faces, feeling meters, moods, and who speaks next. **Do not use it** for moderation, safety decisions or judging real people.
- **English only.** It reads one previous line.
- **The move is read from the words.** It cannot know whether a character really knows something or is lying: "I don't know" is "doesn't know".
- **It misses things.** It gets "answered or still open" wrong about one time in six. It misses about two in three sarcastic jabs and about one in four hostile lines.
- **Player lines are harder** than characters' lines for the move (macro-F1 0.74 against 0.81), and new settings harder still (0.71).
- **About 30% slower than rc1**, because two extra encoder layers run for the move.
- **The 16-bit file saves download and disk, not time or memory.** It has been timed on CPU only.
- **It has only been tested in game settings.** Its test lines are committee-labelled generated and game dialogue, not logs from real players or from other multi-character voice experiences.

The numbers come from the training repository's reports: for the 16-bit file, `2026-10-09-linecls-precision.md` (at commit 9498f60); for the model, `2026-10-09-linecls-r8-exchange.md` (at commit a31743c) and, for the emotion and act heads unchanged since rc1, `2026-10-08-linecls-r6-sarcasm.md` and `2026-10-08-linecls-r7-calibration.md`. The full-precision files were packaged from git tag `spellspeak-tone-rc2` (commit 691b8e2), the 16-bit file was built from them by the code at commit 0c8ed10, and this release was packaged from git tag `spellspeak-tone-rc2.2`. That repository is private.
