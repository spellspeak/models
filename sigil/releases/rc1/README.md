---
license: apache-2.0
language:
  - en
library_name: gguf
pipeline_tag: text-generation
base_model: google/gemma-4-E4B-it
tags:
  - gguf
  - llama.cpp
  - gemma4
  - npc
  - dialogue
  - games
  - roleplay
  - voice-agents
  - conversational-ai
---

# SpellSpeak Sigil 4B · RC1 (alpha)

SpellSpeak Sigil writes what a game character says next: one line of dialogue, in the character's voice, from what that character knows. It is small enough to ship inside a game and run on the player's machine.

The game decides what is true. It gives the model a description of one character, what that character knows and believes, and the conversation so far. The model answers in character, says it does not know when it should not, keeps the character's secrets, and stays inside the world.

**This is an alpha.** It has been measured on NVIDIA GPUs in the cloud, not on players' machines. Read the limits below.

Sigil is the 4B size. [SpellSpeak Glyph 2B](https://huggingface.co/jptaylor/glyph-2b) is the smaller one.

[Examples and source](https://github.com/spellspeak/models/tree/main/sigil)

## What it does, and what it leaves to the game

- **It writes one line of speech.** Plain text, ready for speech synthesis. No markup, emotes or stage directions.
- **The game keeps the facts.** Lore in the prompt is reliable. The model never decides what happened.
- **It only proposes.** If a character agrees to a trade, the game commits it. The model has no tools and does not reason out loud.
- **One model can play every character.** Each character's context stays in its own session.

## Files

| File | Size | Use |
|---|---:|---|
| `gguf/spellspeak-sigil-4b-Q4_K_M.gguf` | 4.40 GB | The one to ship |
| `gguf/spellspeak-sigil-4b-Q5_K_M.gguf` | 4.82 GB | Better in group scenes, weaker on big numbers |
| `model.safetensors` and its config | 15.88 GB | Full precision, for further training and for converting to other runtimes |

A file's size is not its memory. See "Speed and memory".

## Try it

```bash
hf download jptaylor/sigil-4b --revision rc1 --exclude "model.safetensors" --local-dir sigil-4b
cd sigil-4b
pip install -r requirements.txt
python example.py
```

It needs `llama-server` from llama.cpp build b11146 or later. Output, on CPU with llama.cpp b11146. The wording can change a little between machines: the same files gave a different ending to the last line in a second cloud container.

```
A question it can answer
  Player: What's a mug of ale cost here?
  Tomas: Two coppers.

A question it cannot answer
  Player: Who is the king's secret heir?
  Tomas: I don't know. I pour ale, I don't read minds.

Something from outside its world
  Player: Can I pay with my phone?
  Tomas: Phone? I don't know what that is. We take coin, or you can leave.
```

To serve it yourself, use the options the example uses:

```bash
llama-server -m gguf/spellspeak-sigil-4b-Q4_K_M.gguf -c 4096 -np 1 -ngl all --lazy-mode on
```

`--lazy-mode on` reads Gemma's per-layer table from the file a row at a time instead of holding about 1.6 GB of it in memory. If you embed llama.cpp, set `lazy_mode = LLAMA_LAZY_MODE_ON` in `llama_model_params`. We confirmed that the option engages on a cloud machine. The saving has not been measured on a player's machine, and other runtimes may not have this option.

## How to prompt it

`runtime/` holds the reference code. `ActorContext` describes one character, and `render_prompt` turns it and the dialogue into the exact prompt, using Gemma's turn markers. `example.py` shows a full call.

Use greedy decoding (`temperature` 0, `top_k` 1) to match the scores below, and stop at `<turn|>`. The model was trained on this prompt layout. Other layouts have not been tested.

## How it scores

These are the ten tests of GameBench, our benchmark for game dialogue: 5,526 scenes, each passed or failed by a large language model judge, or by a check for tests with a fixed answer. Each number is one run of one file, greedy.

"Untouched" is Google's Gemma 4 E4B instruct model, at full precision, with a long hand-written prompt. Sigil uses the files above and a standard prompt.

| Test (scenes) | Sigil 4B, Q4_K_M | Sigil 4B, Q5_K_M | Untouched Gemma 4 E4B |
|---|---:|---:|---:|
| Core scenes (309) | 69% (213) | 69% (214) | 72% (223) |
| Unseen worlds (1,000) | 85% (847) | 87% (869) | 72% (715) |
| Story and setting (103) | 66% (68) | 71% (73) | 66% (68) |
| Questions in a group (1,500) | 97% (1,449) | 96% (1,446) | 74% (1,103) |
| Group scenes (1,360) | 87% (1,181) | 92% (1,249) | 62% (841) |
| Trades (576) | 75% (433) | 80% (460) | 92% (530) |
| Big numbers (232) | 66% (153) | 48% (112) | 12% (28) |
| Keeps secrets (246) | 89% (220) | 92% (227) | 89% (218) |
| Lets secrets go (164) | 97% (159) | 94% (154) | 85% (140) |
| Under fire (36) | 86% (31) | 92% (33) | 78% (28) |
| **Average of the ten** | **81.7%** | **82.1%** | **70.1%** |

Core scenes, story and setting, and under fire are hand-written. The other seven are generated on worlds held out of training, but the kinds of scene they test are in the training data, so read them as how well that training took.

Untouched Gemma 4 E4B does better on core scenes and trades, at full precision and with a long prompt. Sigil's advantage is the rest of the table at a file that fits in a game.

Q4_K_M's big-numbers score looks high against every other reading of this size. Treat it with care.

## Speed and memory

Measured on one NVIDIA L4 in the cloud, llama.cpp b11146, every layer on the GPU, five characters at once, one run.

| | Q4_K_M | Q5_K_M |
|---|---:|---:|
| File | 4.40 GB | 4.82 GB |
| GPU memory | 3.72 GB | 4.15 GB |
| First word, new character (median) | 134 ms | 144 ms |
| First word, follow-up line (median) | 54 ms | 59 ms |

## Limits

- **Not tested on players' machines.** Consumer GPUs and CPUs are not measured.
- **Numbers are hard for it.** Have the game say prices and sums when they matter.
- **Core scenes are the honest number.** At 69%, about one line in three on hand-written scenes has a fault the judge can name.
- **English only.** Every number here is text only.
- **The judge is a language model.** One pass, with its own blind spots.
- **Training run to training run, results vary.** A second training of this model averaged 78.8% at Q4_K_M, against 81.7% for this one.
- **Long conversations are not scored here.**
- **It can be pushed out of character.** It is not a safety system, so filter what players type and what it says as your game requires.

## How it was made

It is Google's Gemma 4 E4B instruct model with a LoRA merged in, trained on synthetic scenes on generated worlds, written by a larger teacher model and checked by rule. No player data was used. The base is [`google/gemma-4-E4B-it`](https://huggingface.co/google/gemma-4-E4B-it) at revision `ee0ef6023621cff504d758262d4e04895a5af4a2`.

## Licence

Apache-2.0, as is the base model.

The numbers come from the training repository's reports for this release: `2026-11-08-gemma-ship-files.md`, `2026-10-14-gamebench-v0.1.md`, `2026-10-14-gemma-host-memory.md` and `2026-11-08-actor-package.md`, at commit `8b30354`. The model files were packaged from git tag `spellspeak-sigil-rc1` (commit `5dde8cf`). That repository is private.
