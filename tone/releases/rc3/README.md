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

# SpellSpeak Tone · RC3

When several AI characters share one conversation, as in a game, an interactive story or any other multi-character voice experience, each of them needs a structured reading of every line: how the speaker sounds, what the line does to each person present, and whether it leaves a question open for someone else to answer. The language model voicing a character could produce that reading, but only through extra output tokens, training or tool calls. That adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene.

SpellSpeak Tone treats the reading as multi-task classification by a separate small model. One pass over a line predicts the speaker's emotion, the social act directed at each person present with a hostility probability per person, and the move the line makes in the conversation: does it ask, answer, pass on a rumour, say it does not know, hold back, or close the exchange. The application uses the tags for faces, feelings and who speaks next. Its constraints are millisecond inference on a CPU, robustness to unstructured user input, and rare false hostility.

[Examples and source](https://github.com/spellspeak/models/tree/main/tone)

## What is new in RC3

- **It reads sarcasm.** On a held-out test of game dialogue in settings it never saw, it catches 73% of the sarcastic lines that are hostile toward someone (rc2: 52%), and reads 6% of sarcastic lines at face value, as thanks or praise (rc2: 14%). "Sure you will", "what gave it away?" and "wow, so helpful" now read as the jabs they are. Sarcasm about the weather, about oneself or between friends, and sincere lines with the same words ("thanks a lot" after good news), are called hostile less often than before: 3.3% against 5.5%.
- **Insults and teases in a row.** A short follow-up such as "a disgrace" after an insult is read as the insult it continues, and a complaint about a thing followed by the same words is not. Scripted feeling-meter scenes replayed with the model's own tags: 26 of 27 (rc2: 24).
- **A 16-bit file, as in rc2.1.** `model_fp16.onnx` is half the size (55.7 MB) and gives the same tags on 99.96% or more of the test lines in every input setting.
- **What it costs.** Emotion macro-F1 on the main test is 0.649 against rc2's 0.677, most of it in rare emotions (disgust, fear). The move on lines between characters is weaker (0.633 against 0.754). Without who a line is said to, harmless player lines are called hostile more often (3.9% against 1.9%).

| | |
|---|---|
| **Released** | 2026-10-13 · rc3 (package `spellspeak-tone-rc3.1`) |
| **What it does** | Reads one line of dialogue and tags the speaker's emotion, the social act toward each person present, and the line's move in the conversation |
| **What changed from rc2** | The encoder was trained again with sarcasm and its look-alikes, and the move head rebuilt on it. Same outputs, same size, same speed. The hostility threshold is 0.675 (rc2: 0.775), set so that harmless player lines are called hostile no more often than with rc2 |
| **Size** | 27.9M parameters · 111.1 MB ONNX in full precision (fp32), 55.7 MB with the weights in 16 bits (`model_fp16.onnx`) |
| **Speed** | p95 per line on 4 CPU threads (Apple M1 Max): 9.6 ms for a scene of 8 people, the same as rc2 timed side by side. On 1 thread: 28.6 ms. The 16-bit file takes the same time |
| **Runtime** | ONNX Runtime (1.24 or later) and tokenizers, on CPU. A Python reference runtime ships with it |
| **Files** | `model.opt.onnx` (the graph to run), `model.onnx` (the same graph unoptimized), `model_fp16.onnx` (the graph to run with its weights in 16 bits), `tokenizer.json` and `config.json`, with the reference runtime (`runtime/`), `example.py` and `requirements.txt`. `MANIFEST.json` lists every file with its size and sha256 |
| **Licence** | Apache-2.0 |

## Quick start

```bash
pip install -U huggingface_hub
hf download spellspeak/tone --revision rc3 --local-dir spellspeak-tone
cd spellspeak-tone
pip install -r requirements.txt
python example.py
```

The example puts three characters and the player in a room. The player asks everyone a question, the characters answer in different ways, and two more lines follow:

```
player to everyone: 'Who knows where the mill key is?'
    move asks (0.92) · emotion neutral · acts: none
Mara to player: "It's under the counter, love."
    move answers (0.92) · emotion neutral · acts: none
Tomas to player: 'I heard the miller had it last.'
    move hedges (0.98) · emotion neutral · acts: none
Wren to player: 'Why do you want to know?'
    move withholds (0.61) · emotion neutral · acts: none
Tomas to player: 'No idea, sorry.'
    move doesnt_know (0.99) · emotion neutral · acts: player apology
player to Mara: "thanks, that's all i needed"
    move closes (0.98) · emotion happy · acts: Mara thanks
player to Tomas: "Touch my horse again and you'll regret it."
    move other (0.71) · emotion angry · acts: Tomas threat
```

The small download leaves out the two full-precision graphs and runs the 16-bit file. It prints the same tags:

```bash
hf download spellspeak/tone --revision rc3 --local-dir spellspeak-tone-small --exclude model.onnx --exclude model.opt.onnx
cd spellspeak-tone-small
pip install -r requirements.txt
python example.py --fp16
```

In your own code, with the downloaded folder as the working directory:

```python
import sys
sys.path.insert(0, "runtime")

from contracts.schemas.line_tags import LineInput
from harness.expression.classifier import LineClassifier

tone = LineClassifier(".")  # full precision (model.opt.onnx), the default
# tone = LineClassifier(".", precision="fp16")  # the 16-bit file (model_fp16.onnx), for the small download
tags = tone.tag(LineInput(speaker="player", speaker_kind="player", to="Mara", targets=["Mara", "Tomas"],
                          text="oh great, thanks a lot", previous="Mara: Sorry, we're out of rooms tonight."))
print(tags.emotion, tags.acts["Mara"])  # angry act='insult' ... after bad news; after good news the same words read as thanks
```

## Input and output

- **Input:** the line, the line before it, who speaks (the player or a character), who it is said to (or the room), and everyone present (tested up to 8 people; 160 tokens at most). Who it is said to and the line before are optional, and help: see the table below. Sarcasm is mostly read from the line before.
- **Per line:** an emotion (neutral, happy, amused, angry, sad, afraid, surprised, disgusted, contemptuous) with intensity (low, medium, high) and a confidence. Whether the line is only a listening sound such as "mm-hm" (backchannel). The **move**, with a confidence.
- **Per person:** an act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and a confidence.
- **The moves.** asks: wants a reply or an action. answers: gives what was asked for, or offers information. hedges: offers something second-hand or unsure. doesnt_know: says it does not know. withholds: declines, deflects or dodges. closes: winds the exchange down and wants no reply. other: anything else.
- **Hostile** means insult, threat, accusation, or demand at high intensity. A tag is hostile when the hostility score reaches 0.675.
- **Confidence** is the chance the tag is right (calibrated). For a hostile tag it is the chance the line is hostile toward that person.

## Performance (held-out test sets, committee labels)

Sarcasm, on 600 lines of game dialogue in six settings that no training line uses (397 sarcastic, 203 sincere look-alikes):

| Measure | rc2 | rc3 |
|---|---|---|
| Sarcastic lines hostile toward someone: caught (141 pairs) | 52% | 73% (21 points more; 95% interval 13 to 30) |
| Sarcastic lines read at face value (294) | 14% | 6% |
| Look-alikes and harmless sarcasm called hostile | 5.5% | 3.3% |

On sarcasm from sitcoms and Reddit, which is mostly not aimed at anyone present, rc3 is about level with rc2.

The emotion, the acts and the move:

| Measure | rc2 | rc3 |
|---|---|---|
| Act macro-F1, main test (1,905 lines) | 0.678 | 0.661 (0.630 to 0.689) |
| Emotion macro-F1, main test | 0.677 | 0.649 |
| Natural player speech (900 lines): act F1, emotion F1 | 0.761, 0.711 | 0.781, 0.687 |
| Game settings never seen in training (900 lines): act F1 | 0.784 | 0.771 |
| Harmless lines called hostile: prose-style, player speech | 1.1%, 1.7% | 1.4%, 2.3% |
| Hostile lines caught: main test, player speech | 72%, 78% | 76%, 84% |
| Move macro-F1 (824 lines) | 0.812 | 0.816 (0.785 to 0.845) |
| Answered or still open (454 lines) | 82.6% | 83.0% |
| Asks or not (824 lines) | 95.3% | 96.0% |
| Move macro-F1 on player lines, between characters | 0.737, 0.754 | 0.774, 0.633 |
| Calibration error: act tags, emotion, move | 0.08, 0.05, 0.04 | 0.07, 0.05, 0.05 |

For scale, two frontier labellers agree with each other at 0.766 act F1, 0.709 emotion F1 and 0.845 move F1.

### With and without the optional inputs

The same test lines, scored again without who a line is said to, without the line before, and without either, against the same labels:

| Measure | As given | Without `to` | Without the line before | Without either |
|---|---|---|---|---|
| Act macro-F1, main test | 0.661 | 0.564 | 0.656 | 0.552 |
| Emotion macro-F1, main test | 0.649 | 0.649 | 0.640 | 0.636 |
| Harmless lines called hostile, prose | 1.4% | 1.5% | 1.3% | 1.8% |
| Harmless lines called hostile, player speech | 2.3% | 3.9% | 2.9% | 5.7% |
| Hostile lines caught, main test | 76% | 77% | 76% | 77% |
| Move macro-F1 | 0.816 | 0.805 | 0.722 | 0.683 |
| Answered or still open | 83.0% | 80.0% | 66.1% | 60.1% |

- **Send who a line is said to when you know it.** Without it, more harmless player lines are called hostile.
- **Send the line before.** Sarcasm and the move are both read from it.

### The 16-bit file

The same 5,204 test lines, tagged by `model_fp16.onnx` and by full precision, in the same four columns:

| | As given | Without `to` | Without the line before | Without either |
|---|---|---|---|---|
| Lines with every tag the same as full precision | 100% | 99.98% (one act toward one person differs) | 100% | 99.96% (two lines differ) |

Every measure in the tables above is the same with the 16-bit file. It computes in 32 bits, so it saves the download and the disk, not time or memory (224 MB resident against 205 MB).

## How it was made

- **Model:** MiniLM-L6 (`sentence-transformers/all-MiniLM-L6-v2` at 1110a24, Apache-2.0) with six small heads. For the move, trainable copies of its top two layers read its fourth layer's output, and a small head reads them.
- **Distillation:** the emotion and the acts from three Ettin-1B teachers (`jhu-clsp/ettin-encoder-1b`, MIT) over 374,534 lines, plus 20,286 lines labelled directly. The move from rc2's three move teachers over 113,201 lines, plus 3,296 labelled training lines.
- **Labels:** the majority vote of a committee of three large language models.
- **Lines:** our own game dialogue, Project Gutenberg dialogue, GoEmotions (Apache-2.0), Civil Comments (CC0), and lines written for this project by Qwen3.8-27B. New in rc3: 40,758 lines of sarcasm in twelve kinds with sincere look-alikes, and 8,284 of a speaker's two lines in a row. Sitcom and Reddit sarcasm was used only as a test.
- **Calibration:** the hostility threshold was matched on a player-speech dev set; the act, emotion and move curves were fitted on dev.
- **The 16-bit file:** full precision's graph with every weight tensor of 1,024 values or more stored in 16 bits and turned back into 32 bits by the graph itself, so the same runtime and calibration serve both files.

## Use and limits

- **Use it** for character reactions and turn-taking in multi-character conversations: faces, feeling meters, moods, and who speaks next. **Do not use it** for moderation, safety decisions or judging real people.
- **English only.** It reads one previous line.
- **It misses things.** It misses about one in four hostile sarcastic lines in game dialogue, and most sarcasm in sitcom and Reddit text. It gets "answered or still open" wrong about one time in six.
- **Rare emotions are weaker than in rc2**, disgust and fear most.
- **The move on lines between characters is weaker than in rc2** (0.633 against 0.754).
- **It has only been tested in game settings.** Its test lines are committee-labelled generated and game dialogue, not logs from real players or from other multi-character voice experiences.

The numbers come from the training repository's report for this release, `2026-10-13-linecls-r9-sarcasm.md` (at commit ecaafed), with the open-data sarcasm test in `2026-10-13-linecls-r9-sarcasm-test.md`. The full-precision files were packaged from git tag `spellspeak-tone-rc3` (commit c85d633), and this release was packaged from git tag `spellspeak-tone-rc3.1`. That repository is private.
