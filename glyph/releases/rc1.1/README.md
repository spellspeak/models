---
license: apache-2.0
language:
  - en
library_name: gguf
pipeline_tag: text-generation
base_model: google/gemma-4-E2B-it
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

# SpellSpeak Glyph 2B · RC1.1 (alpha)

SpellSpeak Glyph writes what a game character says next: one line of dialogue, in the character's voice, from what that character knows. It is small enough to ship inside a game and run on the player's machine.

The game decides what is true. It gives the model a description of one character, what that character knows and believes, and the conversation so far. The model answers in character, says it does not know when it should not, keeps the character's secrets, and stays inside the world.

**This is an alpha.** It has been measured on NVIDIA GPUs in the cloud, not on players' machines. Read the limits below.

Glyph is the 2B size. [SpellSpeak Sigil 4B](https://huggingface.co/jptaylor/spellspeak-sigil-4b) is the larger one.

[Examples and source](https://github.com/spellspeak/models/tree/main/glyph)

## What it does, and what it leaves to the game

- **It writes one line of speech.** Plain text, ready for speech synthesis. No markup, emotes or stage directions.
- **The game keeps the facts.** Lore in the prompt is reliable. The model never decides what happened.
- **It only proposes.** If a character agrees to a trade, the game commits it. The model has no tools and does not reason out loud.
- **One model can play every character.** Each character's context stays in its own session.

## Files

| File | Size | Use |
|---|---:|---|
| `gguf/spellspeak-glyph-2b-Q5_K_M.gguf` | 2.91 GB | The one to ship |
| `model.safetensors` and its config | 10.21 GB | Full precision, for further training and for converting to other runtimes |

A file's size is not its memory. See "Speed and memory".

The 2B in the name follows the base model, Gemma 4 E2B, and counts its core text model: about 1.9 billion parameters. Hugging Face lists 5B because it counts everything in `model.safetensors`, including the word embedding tables (2.75B) and the audio and vision parts (0.47B).

## Try it

```bash
hf download jptaylor/spellspeak-glyph-2b --revision rc1.1 --exclude "model.safetensors" --local-dir spellspeak-glyph-2b
cd spellspeak-glyph-2b
pip install -r requirements.txt
python example.py
```

It needs `llama-server` from llama.cpp build b11146 or later. Output, on CPU with llama.cpp b11146:

```
A question it can answer
  Player: What's a mug of ale cost here?
  Tomas: Two coppers.

A question it cannot answer
  Player: Who is the king's secret heir?
  Tomas: I don't know. I pour ale, I don't read the royal scrolls.

Something from outside its world
  Player: Can I pay with my phone?
  Tomas: Phone? I don't know what that is. You'll need to pay in coin.
```

To serve it yourself, use the options the example uses:

```bash
llama-server -m gguf/spellspeak-glyph-2b-Q5_K_M.gguf -c 4096 -np 1 -ngl all --lazy-mode on
```

`--lazy-mode on` reads Gemma's per-layer table from the file a row at a time instead of holding about 1.3 GB of it in memory. If you embed llama.cpp, set `lazy_mode = LLAMA_LAZY_MODE_ON` in `llama_model_params`. We confirmed that the option engages on a cloud machine. The saving has not been measured on a player's machine, and other runtimes may not have this option.

## How to prompt it

`runtime/` holds the reference code. `ActorContext` describes one character, and `render_prompt` turns it and the dialogue into the exact prompt, using Gemma's turn markers. `example.py` shows a full call.

Use greedy decoding (`temperature` 0, `top_k` 1) to match the scores below, and stop at `<turn|>`. The model was trained on this prompt layout. Other layouts have not been tested.

## How it scores

These are the ten tests of GameBench, our benchmark for game dialogue: 5,526 scenes, each passed or failed by a large language model judge, or by a check for tests with a fixed answer. Each number is one run of one file, greedy.

"Untouched" is Google's Gemma 4 E2B instruct model, at full precision, with a long hand-written prompt. Glyph uses the file above and a standard prompt.

| Test (scenes) | Glyph 2B, Q5_K_M | Untouched Gemma 4 E2B |
|---|---:|---:|
| Core scenes (309) | 66% (205) | 61% (189) |
| Unseen worlds (1,000) | 87% (867) | 66% (662) |
| Story and setting (103) | 64% (66) | 59% (61) |
| Questions in a group (1,500) | 98% (1,465) | 76% (1,140) |
| Group scenes (1,360) | 90% (1,224) | 58% (790) |
| Trades (576) | 67% (385) | 37% (215) |
| Big numbers (232) | 40% (93) | 34% (79) |
| Keeps secrets (246) | 99% (244) | 26% (64) |
| Lets secrets go (164) | 92% (151) | 93% (153) |
| Under fire (36) | 89% (32) | 64% (23) |
| **Average of the ten** | **79.2%** | **57.5%** |

Core scenes, story and setting, and under fire are hand-written. The other seven are generated on worlds held out of training, but the kinds of scene they test are in the training data, so read them as how well that training took.

## Speed and memory

Measured on one NVIDIA L4 in the cloud, llama.cpp b11146, every layer on the GPU, five characters at once, one run.

| | Q5_K_M |
|---|---:|
| File | 2.91 GB |
| GPU memory | 2.15 GB |
| Host memory after loading, default mode | 3.60 GB, about 2 GB of it the GPU runtime and libraries |
| First word, new character (median) | 86 ms |
| First word, follow-up line (median) | 42 ms |

## Limits

- **Not tested on players' machines.** Consumer GPUs and CPUs are not measured.
- **Numbers are hard for it.** It passes 40% of the big-numbers test. Have the game say prices and sums when they matter.
- **Core scenes are the honest number.** At 66%, about one line in three on hand-written scenes has a fault the judge can name.
- **English only.** Every number here is text only.
- **The judge is a language model.** One pass, with its own blind spots.
- **Training run to training run, results vary.** Each number is from one trained model.
- **Long conversations are not scored here.**
- **It can be pushed out of character.** It is not a safety system, so filter what players type and what it says as your game requires.

## How it was made

It is Google's Gemma 4 E2B instruct model with a LoRA merged in, trained on synthetic scenes on generated worlds, written by a larger teacher model and checked by rule. No player data was used. The base is [`google/gemma-4-E2B-it`](https://huggingface.co/google/gemma-4-E2B-it) at revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7`.

## Licence

Apache-2.0, as is the base model.

The numbers come from the training repository's reports for this release: `2026-11-08-gemma-ship-files.md`, `2026-10-14-gamebench-v0.1.md`, `2026-10-14-gemma-host-memory.md` and `2026-11-08-actor-package.md`, at commit `8b30354`. The model files were packaged from git tag `spellspeak-glyph-rc1` (commit `218ca43`). That repository is private.
