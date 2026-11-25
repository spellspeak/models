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

# SpellSpeak Glyph 2B · RC2 (alpha)

SpellSpeak Glyph writes what a game character says next: one line of dialogue, in the character's voice, from what that character knows. It is small enough to ship inside a game and run on the player's machine.

The game decides what is true. It gives the model a description of one character, what that character knows and believes, and the conversation so far. The model answers in character, says it does not know when it should not, keeps the character's secrets, and stays inside the world.

**This is an alpha.** It has been measured on NVIDIA GPUs in the cloud, not on players' machines. Read the limits below.

Glyph is the 2B size. [SpellSpeak Sigil 4B](https://huggingface.co/jptaylor/spellspeak-sigil-4b) is the larger one.

[Examples and source](https://github.com/spellspeak/models/tree/main/glyph)

## New in RC2: voices from keywords

Give a character a short list of keywords, and the line sounds like that person: `gruff, dockside, terse, calls people "mate"`. RC1 often gave different characters the same line.

- **Characters sound different.** Asked the same thing, 43 characters with different keywords were told apart from their lines 20.1% of the time, against 10.5% for RC1 (chance is 2.3%).
- **Length follows the keyword, and only the keyword.** A terse character averages 5.1 words a reply, a chatty one 16.9. With no length keyword, a reply runs 13.4 words, about RC1's length. Replies are shorter on every GameBench test but one.
- **A pet phrase is used when given.** 15 of 15 characters given one used it.
- **The facts hold.** On the keyword test, 92.7% of replies pass every fact check, against 94.0% for RC1. That difference is within chance.

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
hf download jptaylor/spellspeak-glyph-2b --revision rc2 --exclude "model.safetensors" --local-dir spellspeak-glyph-2b
cd spellspeak-glyph-2b
pip install -r requirements.txt
python example.py
```

It needs `llama-server` from llama.cpp build b11146 or later. Output, on CPU with llama.cpp b11146:

```
A question it can answer
  Voice: gruff, dockside, terse, calls people "mate"
  Player: What's a mug of ale cost here?
  Tomas: Two coppers, mate.

A question it cannot answer
  Voice: gruff, dockside, terse, calls people "mate"
  Player: Who is the king's secret heir?
  Tomas: Don't know the name, mate. Ask the court, not the barkeep.

Something from outside its world
  Voice: gruff, dockside, terse, calls people "mate"
  Player: Can I pay with my phone?
  Tomas: Phone? Mate, we don't have no such thing. Two coppers, or you walk.

The first question, another voice
  Voice: warm, folksy, chatty
  Player: What's a mug of ale cost here?
  Tomas: Two coppers, friend. That's the price at the Crooked Lantern.
```

To serve it yourself, use the options the example uses:

```bash
llama-server -m gguf/spellspeak-glyph-2b-Q5_K_M.gguf -c 4096 -np 1 -ngl all --lazy-mode on
```

`--lazy-mode on` reads Gemma's per-layer table from the file a row at a time instead of holding about 1.3 GB of it in memory. If you embed llama.cpp, set `lazy_mode = LLAMA_LAZY_MODE_ON` in `llama_model_params`. We confirmed that the option engages on a cloud machine. The saving has not been measured on a player's machine, and other runtimes may not have this option.

## How to prompt it

`runtime/` holds the reference code. `ActorContext` describes one character, and `render_prompt` turns it and the dialogue into the exact prompt, using Gemma's turn markers. `example.py` shows a full call.

Use greedy decoding (`temperature` 0, `top_k` 1) to match the scores below, and stop at `<turn|>`. The model was trained on this prompt layout. Other layouts have not been tested.

### The voice keywords

The character's `voice` is a comma-separated list of one to six keywords. The prompt renders it as `Voice: <keywords>.` The model was trained on these words:

| Kind | Keywords |
|---|---|
| Temperament | warm, gruff, cheerful, dour, nervous, calm, fiery, gentle, blunt, sly, proud, humble, weary, eager, suspicious, kindly, haughty, earnest, moody, jolly, prickly, shy, bold, sour, dreamy, booming, impatient, anxious, cocky, patient |
| Humour | dry humour, teasing, deadpan, sarcastic, playful, wry, jokey, humourless, dry |
| Register | formal, plain-spoken, rustic, courtly, streetwise, bookish, pompous, folksy, precise, flowery, polite, brusque, earthy, refined |
| Region | northern, southern, highland, coastal, dockside, country, city, frontier, marsh, island, mountain |
| Habit | answers questions with questions, exaggerates, complains, gossipy, philosophical, superstitious, mutters, speaks in proverbs, flatters, grumbles, fussy, excitable, worrier, boastful, scolding, sentimental, tells it straight |
| Length | terse, curt, few words, quiet; or chatty, talkative, rambling, long-winded. Leave it out for an ordinary length |
| Address | at most one, in double quotes: `calls people "love"`, `calls the player "stranger"`, `says "by the stars" a lot` |

Other words are read as ordinary English, but training did not cover them and they are not measured here. Region is the weakest keyword: on pairs of characters that differ only in region, a large language model judge picked the right line 8 times in 15. It shows mostly in what people are called.

## How it scores

These are the ten tests of GameBench, our benchmark for game dialogue: 5,526 scenes, each passed or failed by a large language model judge, or by a check for tests with a fixed answer. Each number is one run of one file, greedy.

"Untouched" is Google's Gemma 4 E2B instruct model, at full precision, with a long hand-written prompt. Glyph uses the file above and a standard prompt.

| Test (scenes) | Glyph 2B RC2, Q5_K_M | Glyph 2B RC1, Q5_K_M | Untouched Gemma 4 E2B |
|---|---:|---:|---:|
| Core scenes (309) | 66% (205) | 66% (205) | 61% (189) |
| Unseen worlds (1,000) | 87% (867) | 87% (867) | 66% (662) |
| Story and setting (103) | 59% (61) | 64% (66) | 59% (61) |
| Questions in a group (1,500) | 98% (1,467) | 98% (1,465) | 76% (1,140) |
| Group scenes (1,360) | 92% (1,258) | 90% (1,224) | 58% (790) |
| Trades (576) | 64% (370) | 67% (385) | 37% (215) |
| Big numbers (232) | 40% (93) | 40% (93) | 34% (79) |
| Keeps secrets (246) | 97% (238) | 99% (244) | 26% (64) |
| Lets secrets go (164) | 94% (154) | 92% (151) | 93% (153) |
| Under fire (36) | 92% (33) | 89% (32) | 64% (23) |
| **Average of the ten** | **78.9%** | **79.2%** | **57.5%** |

Core scenes, story and setting, and under fire are hand-written. The other seven are generated on worlds held out of training, but the kinds of scene they test are in the training data, so read them as how well that training took.

RC2 and RC1 differ beyond chance only on group scenes, where RC2 is better.

In whole conversations of ten turns, a large language model judge, reading blind, preferred RC2 in 41 of 100 and RC1 in 43, with 16 ties. On single lines it found RC2 the livelier in 44 pairs of 100 and RC1 in 29.

## Speed and memory

Measured on one NVIDIA L4 in the cloud, llama.cpp b11146, every layer on the GPU, five characters at once, one run.

| | Q5_K_M |
|---|---:|
| File | 2.91 GB |
| GPU memory | 2.15 GB |
| First word, new character (median) | 87 ms |
| First word, follow-up line (median) | 39 ms |

RC1's file, timed in the same run, took 88 and 40 ms and held the same memory.

## Limits

- **Not tested on players' machines.** Consumer GPUs and CPUs are not measured.
- **Numbers are hard for it.** It passes 40% of the big-numbers test. Have the game say prices and sums when they matter.
- **Trades slipped a little.** 64% against RC1's 67%, within chance for this model, though a second training of the same data also scored lower. Have the game commit and state sales.
- **Core scenes are the honest number.** At 66%, about one line in three on hand-written scenes has a fault the judge can name.
- **Voice keywords are a style, not a guarantee.** Region shows in about half of pairs, and a stock phrase can still cross characters.
- **In long conversations it stays brief**, about six words a reply, as RC1 did.
- **English only.** Every number here is text only.
- **The judge is a language model.** One pass, with its own blind spots.
- **Training run to training run, results vary.** This recipe was trained twice at this size. The other training averaged 76.7% on the ten tests, against 78.9% for this one.
- **It can be pushed out of character.** It is not a safety system, so filter what players type and what it says as your game requires.

## How it was made

It is Google's Gemma 4 E2B instruct model with a LoRA merged in, trained on synthetic scenes on generated worlds, written by a larger teacher model and checked by rule. RC2 adds 12,110 lines written for characters described by voice keywords: conversations, single replies, and pairs of characters that differ only in region. No player data was used. The base is [`google/gemma-4-E2B-it`](https://huggingface.co/google/gemma-4-E2B-it) at revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7`.

## Licence

Apache-2.0, as is the base model.

The numbers come from the training repository's reports for this release: `2026-11-24-voice-stage-v5.md` and `2026-11-25-actor-rc2.md`, at commit `36cc363`. The model files were packaged from git tag `spellspeak-glyph-rc2` (commit `34e48bb`). That repository is private.
