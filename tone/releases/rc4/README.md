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
  - sarcasm-detection
  - turn-taking
  - real-time
  - pipecat
  - npc
  - dialogue
---

# SpellSpeak Tone · RC4

When several AI characters share one conversation, as in a game, an interactive story or any other multi-character voice experience, each of them needs a structured reading of every line: how the speaker sounds, what the line does to each person present, and whether it leaves a question open for someone else to answer. The language model voicing a character could produce that reading, but only through extra output tokens, training or tool calls. That adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene.

SpellSpeak Tone treats the reading as multi-task classification by a separate small model. One pass over a line predicts the speaker's emotion, the social act directed at each person present with a hostility probability per person, the move the line makes in the conversation (does it ask, answer, pass on a rumour, say it does not know, hold back, or close the exchange), and whether the line is sarcastic. The application uses the tags for faces, feelings and who speaks next. Its constraints are millisecond inference on a CPU, robustness to unstructured user input, and rare false alarms.

[Examples and source](https://github.com/spellspeak/models/tree/main/tone)

## What is new in RC4

- **A sarcasm output, with its probability.** Every line now also says whether it is sarcastic: `sarcasm: {sarcastic, probability}`. Sarcastic means the line means something other than, usually the opposite of, what its words say: mock thanks, mock praise, mock agreement, ironic understatement, whether hostile, friendly or about the situation. On game dialogue in settings it never saw, it finds 73% of sarcastic lines and is right 86% of the time it says so (F1 0.79; two frontier labellers agree with each other at 0.91). It calls 1.6% of sincere everyday lines sarcastic.
- **The probability is calibrated** (error 0.03), so you can show it, or use your own threshold instead of the model's.
- **Everything else is rc3's.** Every rc3 tag, intensity, confidence and move is identical on 3,754 test lines. The sarcasm head reads the same pass: the same speed, 0.6 MB more.

| | |
|---|---|
| **Released** | 2026-10-13 · rc4 (package `spellspeak-tone-rc4.1`) |
| **What it does** | Reads one line of dialogue and tags the speaker's emotion, the social act toward each person present, the line's move in the conversation, and whether it is sarcastic |
| **What changed from rc3** | A small sarcasm head on rc3's encoder, in the same pass. rc3's outputs are unchanged. Contract `line-tags-0.3`: one optional field per line, so code written for rc3 runs unchanged |
| **Size** | 27.9M parameters in the graph (rc3's and 0.15M for the sarcasm head) · 111.7 MB ONNX in full precision (fp32), 56.0 MB with the weights in 16 bits (`model_fp16.onnx`) |
| **Speed** | p95 per line on 4 CPU threads (Apple M1 Max): 9.7 ms for a scene of 8 people, rc3 9.6 ms timed side by side. On 1 thread: 28.0 ms. The 16-bit file takes about the same time |
| **Runtime** | ONNX Runtime (1.24 or later) and tokenizers, on CPU. A Python reference runtime ships with it |
| **Files** | `model.opt.onnx` (the graph to run), `model.onnx` (the same graph unoptimized), `model_fp16.onnx` (the graph to run with its weights in 16 bits), `tokenizer.json` and `config.json`, with the reference runtime (`runtime/`), `example.py` and `requirements.txt`. `MANIFEST.json` lists every file with its size and sha256 |
| **Licence** | Apache-2.0 |

## Quick start

```bash
pip install -U huggingface_hub
hf download spellspeak/tone --revision rc4 --local-dir spellspeak-tone
cd spellspeak-tone
pip install -r requirements.txt
python example.py
```

The example puts three characters and the player in a room. The player asks everyone a question, the characters answer in different ways, and three more lines follow:

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
Wren to player: 'Oh, brilliant. You lost the key. Again.'
    move other (0.72) · emotion contemptuous · acts: player insult · sarcastic (0.97)
```

The small download leaves out the two full-precision graphs and runs the 16-bit file. It prints the same tags:

```bash
hf download spellspeak/tone --revision rc4 --local-dir spellspeak-tone-small --exclude model.onnx --exclude model.opt.onnx
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
print(tags.emotion, tags.acts["Mara"].act, tags.sarcasm)  # sarcastic=True with its probability, after bad news
```

## Input and output

- **Input:** the line, the line before it, who speaks (the player or a character), who it is said to (or the room), and everyone present (tested up to 8 people; 160 tokens at most). Who it is said to and the line before are optional, and help: see the table below. Sarcasm is mostly read from the line before.
- **Per line:** an emotion (neutral, happy, amused, angry, sad, afraid, surprised, disgusted, contemptuous) with intensity (low, medium, high) and a confidence. Whether the line is only a listening sound such as "mm-hm" (backchannel). The **move**, with a confidence. **Sarcasm**: `sarcastic` (true or false) and `probability`, the calibrated chance the line is sarcastic.
- **Per person:** an act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and a confidence.
- **The moves.** asks: wants a reply or an action. answers: gives what was asked for, or offers information. hedges: offers something second-hand or unsure. doesnt_know: says it does not know. withholds: declines, deflects or dodges. closes: winds the exchange down and wants no reply. other: anything else.
- **Hostile** means insult, threat, accusation, or demand at high intensity. A tag is hostile when the hostility score reaches 0.675.
- **Sarcastic** is decided at the model's threshold, set so that at most 2% of sincere everyday lines are called sarcastic. The act and the emotion already say how hostile a sarcastic line is.
- **Confidence** is the chance the tag is right (calibrated). For a hostile tag it is the chance the line is hostile toward that person.

## Performance (held-out test sets, committee labels)

### Sarcasm

900 lines of game dialogue in six settings that no training line uses (263 sarcastic: sarcasm in twelve kinds, sincere look-alikes with the same words, and a speaker's two lines in a row), and 1,781 everyday lines (900 lines of natural player speech and 881 of game dialogue, 34 of them sarcastic):

| Measure | rc4 |
|---|---|
| F1, game dialogue in unseen settings (900 lines) | 0.793 (0.755 to 0.827; precision 0.862, recall 0.734) |
| Sincere everyday lines called sarcastic (1,747) | 1.55% (1.1% to 2.2%) |
| Calibration error of the probability (2,681 lines) | 0.028 |

For scale, two frontier labellers agree with each other at 0.905 F1 on the same 900 lines. It finds sarcasm after a setback ("Oh, wonderful. Another storm.") and about the situation best, friendly teasing sarcasm least.

On sitcom and Reddit sarcasm, labelled by what each writer meant, it is precise but finds little: 4% of the sitcom lines and 9% of the Reddit lines their sources call sarcastic, with 0.7% and 3.4% of their sincere lines called sarcastic.

### The emotion, the acts and the move

The same as rc3, tag for tag:

| Measure | rc4 (and rc3) |
|---|---|
| Act macro-F1, main test (1,905 lines) | 0.661 (0.630 to 0.689) |
| Emotion macro-F1, main test | 0.649 |
| Natural player speech (900 lines): act F1, emotion F1 | 0.781, 0.687 |
| Game settings never seen in training (900 lines): act F1 | 0.771 |
| Harmless lines called hostile: prose-style, player speech | 1.4%, 2.3% |
| Hostile lines caught: main test, player speech | 76%, 84% |
| Sarcastic lines hostile toward someone, caught (141 pairs in unseen settings) | 73% |
| Move macro-F1 (824 lines) | 0.816 (0.785 to 0.845) |
| Answered or still open (454 lines) | 83.0% |
| Asks or not (824 lines) | 96.0% |
| Calibration error: act tags, emotion, move | 0.07, 0.05, 0.05 |

For scale, two frontier labellers agree with each other at 0.766 act F1, 0.709 emotion F1 and 0.845 move F1.

### With and without the optional inputs

The same test lines, scored again without who a line is said to, without the line before, and without either, against the same labels:

| Measure | As given | Without `to` | Without the line before | Without either |
|---|---|---|---|---|
| Sarcasm F1, unseen settings | 0.793 | 0.790 | 0.472 | 0.426 |
| Sincere everyday lines called sarcastic | 1.55% | 1.20% | 0.29% | 0.23% |
| Act macro-F1, main test | 0.661 | 0.564 | 0.656 | 0.552 |
| Emotion macro-F1, main test | 0.649 | 0.649 | 0.640 | 0.636 |
| Harmless lines called hostile, prose | 1.4% | 1.5% | 1.3% | 1.8% |
| Harmless lines called hostile, player speech | 2.3% | 3.9% | 2.9% | 5.7% |
| Hostile lines caught, main test | 76% | 77% | 76% | 77% |
| Move macro-F1 | 0.816 | 0.805 | 0.722 | 0.683 |
| Answered or still open | 83.0% | 80.0% | 66.1% | 60.1% |

- **Send the line before.** Without it, sarcasm is found less than half as often (it stays precise), and the move is weaker.
- **Send who a line is said to when you know it.** Without it, more harmless player lines are called hostile.

### The 16-bit file

The same 5,204 test lines, and the 2,681 sarcasm test lines, tagged by `model_fp16.onnx` and by full precision, in the same four columns:

| | As given | Without `to` | Without the line before | Without either |
|---|---|---|---|---|
| Lines with every tag the same as full precision | 100% | 99.98% (one act toward one person differs) | 100% | 99.96% (two lines differ) |
| The sarcasm decision the same | 100% | 100% | 100% | 100% |

Every measure in the tables above is the same with the 16-bit file. It computes in 32 bits, so it saves the download and the disk, not time or memory (247 MB resident against 201 MB).

## How it was made

- **Model:** MiniLM-L6 (`sentence-transformers/all-MiniLM-L6-v2` at 1110a24, Apache-2.0) with six small heads. For the move, trainable copies of its top two layers read its fourth layer's output, and a small head reads them. The sarcasm head (148,610 parameters) reads the encoder's last layer, which stays as rc3 trained it.
- **Distillation:** the emotion and the acts from three Ettin-1B teachers (`jhu-clsp/ettin-encoder-1b`, MIT) over 374,534 lines, plus 20,286 lines labelled directly. The move from rc2's three move teachers over 113,201 lines, plus 3,296 labelled training lines.
- **Sarcasm:** trained on 4,000 lines labelled by the committee (1,137 sarcastic): our game dialogue's sarcasm in twelve kinds with its sincere look-alikes, a speaker's two lines in a row, and everyday lines. The threshold was chosen on dev lines, and its probability curve fitted on them.
- **Labels:** the majority vote of a committee of three large language models.
- **Lines:** our own game dialogue, Project Gutenberg dialogue, GoEmotions (Apache-2.0), Civil Comments (CC0), and lines written for this project by Qwen3.8-27B. Sitcom and Reddit sarcasm was used only as a test.
- **Calibration:** the hostility threshold was matched on a player-speech dev set; the act, emotion, move and sarcasm curves were fitted on dev.
- **The 16-bit file:** full precision's graph with every weight tensor of 1,024 values or more stored in 16 bits and turned back into 32 bits by the graph itself, so the same runtime and calibration serve both files.

## Use and limits

- **Use it** for character reactions and turn-taking in multi-character conversations: faces, feeling meters, moods, and who speaks next. **Do not use it** for moderation, safety decisions or judging real people.
- **English only.** It reads one previous line.
- **It misses sarcasm.** It misses about one sarcastic line in four in game dialogue, most friendly teasing sarcasm, and most sitcom and Reddit sarcasm. Without the line before, it finds less than half as much.
- **It misses other things.** It misses about one in four hostile sarcastic lines, and gets "answered or still open" wrong about one time in six.
- **Rare emotions are weaker than in rc2**, disgust and fear most. **The move on lines between characters is weaker than in rc2** (0.633 against 0.754).
- **It has only been tested in game settings.** Its test lines are committee-labelled generated and game dialogue, not logs from real players or from other multi-character voice experiences.

The numbers come from the training repository's report for this release, `2026-10-13-linecls-r10-sarcasm-output.md` (at commit 2cf51c7). The full-precision files were packaged from git tag `spellspeak-tone-rc4` (commit 78d74e8), and this release was packaged from git tag `spellspeak-tone-rc4.1`. That repository is private.
