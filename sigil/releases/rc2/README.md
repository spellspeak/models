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

# SpellSpeak Sigil 4B · RC2 (alpha)

SpellSpeak Sigil writes what a game character says next: one line of dialogue, in the character's voice, from what that character knows. It is small enough to ship inside a game and run on the player's machine.

The game decides what is true. It gives the model a description of one character, what that character knows and believes, and the conversation so far. The model answers in character, says it does not know when it should not, keeps the character's secrets, and stays inside the world.

**This is an alpha.** It has been measured on NVIDIA GPUs in the cloud, not on players' machines. Read the limits below.

Sigil is the 4B size. [SpellSpeak Glyph 2B](https://huggingface.co/jptaylor/spellspeak-glyph-2b) is the smaller one.

[Examples and source](https://github.com/spellspeak/models/tree/main/sigil)

## New in RC2: voices from keywords

Give a character a short list of keywords, and the line sounds like that person: `gruff, dockside, terse, calls people "mate"`. RC1 often gave different characters the same line.

- **Characters sound different.** Asked the same thing, 43 characters with different keywords were told apart from their lines 21.4% of the time, against 12.4% for RC1 (chance is 2.3%).
- **Length follows the keyword, and only the keyword.** A terse character averages 5.0 words a reply, a chatty one 16.8. With no length keyword, a reply runs 13.4 words, against RC1's 14.3. Replies are shorter on every GameBench test.
- **A pet phrase is used when given.** 15 of 15 characters given one used it.
- **The facts hold.** On the keyword test, 91.1% of replies pass every fact check, against 92.5% for RC1. That difference is within chance.

## What it does, and what it leaves to the game

- **It writes one line of speech.** Plain text, ready for speech synthesis. No markup, emotes or stage directions.
- **The game keeps the facts.** Lore in the prompt is reliable. The model never decides what happened.
- **It only proposes.** If a character agrees to a trade, the game commits it. The model has no tools and does not reason out loud.
- **One model can play every character.** Each character's context stays in its own session.

## Files

| File | Size | Use |
|---|---:|---|
| `gguf/spellspeak-sigil-4b-Q4_K_M.gguf` | 4.40 GB | The one to ship |
| `gguf/spellspeak-sigil-4b-Q5_K_M.gguf` | 4.82 GB | Better at group scenes and trades, weaker at letting secrets go |
| `model.safetensors` and its config | 15.88 GB | Full precision, for further training and for converting to other runtimes |

A file's size is not its memory. See "Speed and memory".

The 4B in the name follows the base model, Gemma 4 E4B, and counts its core text model: about 4.0 billion parameters. Hugging Face lists 8B because it counts everything in `model.safetensors`, including the word embedding tables (3.49B) and the audio and vision parts (0.48B).

## Try it

```bash
hf download jptaylor/spellspeak-sigil-4b --revision rc2 --exclude "model.safetensors" --local-dir spellspeak-sigil-4b
cd spellspeak-sigil-4b
pip install -r requirements.txt
python example.py
```

It needs `llama-server` from llama.cpp build b11146 or later. Output, on CPU with llama.cpp b11146. The wording can change a little between machines: RC1's files gave a different ending to one line in a second cloud container.

```
A question it can answer
  Voice: gruff, dockside, terse, calls people "mate"
  Player: What's a mug of ale cost here?
  Tomas: Two coppers, mate.

A question it cannot answer
  Voice: gruff, dockside, terse, calls people "mate"
  Player: Who is the king's secret heir?
  Tomas: Don't know, mate. I pour ale, I don't read minds.

Something from outside its world
  Voice: gruff, dockside, terse, calls people "mate"
  Player: Can I pay with my phone?
  Tomas: Phone? Mate, I take coppers, not magic glass.

The first question, another voice
  Voice: warm, folksy, chatty
  Player: What's a mug of ale cost here?
  Tomas: Two coppers a mug, friend. Same as always, no haggling.
```

To serve it yourself, use the options the example uses:

```bash
llama-server -m gguf/spellspeak-sigil-4b-Q4_K_M.gguf -c 4096 -np 1 -ngl all --lazy-mode on
```

`--lazy-mode on` reads Gemma's per-layer table from the file a row at a time instead of holding about 1.6 GB of it in memory. If you embed llama.cpp, set `lazy_mode = LLAMA_LAZY_MODE_ON` in `llama_model_params`. We confirmed that the option engages on a cloud machine. The saving has not been measured on a player's machine, and other runtimes may not have this option.

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

Other words are read as ordinary English, but training did not cover them and they are not measured here. Region is the weakest keyword: on pairs of characters that differ only in region, a large language model judge picked the right line 5 times in 15. It shows mostly in what people are called.

## How it scores

These are the ten tests of GameBench, our benchmark for game dialogue: 5,526 scenes, each passed or failed by a large language model judge, or by a check for tests with a fixed answer. Each number is one run of one file, greedy.

"Untouched" is Google's Gemma 4 E4B instruct model, at full precision, with a long hand-written prompt. Sigil uses the files above and a standard prompt.

| Test (scenes) | Sigil 4B RC2, Q4_K_M | Sigil 4B RC2, Q5_K_M | Sigil 4B RC1, Q4_K_M | Untouched Gemma 4 E4B |
|---|---:|---:|---:|---:|
| Core scenes (309) | 66% (205) | 67% (206) | 69% (213) | 72% (223) |
| Unseen worlds (1,000) | 86% (864) | 87% (874) | 85% (847) | 72% (715) |
| Story and setting (103) | 71% (73) | 65% (67) | 66% (68) | 66% (68) |
| Questions in a group (1,500) | 97% (1,453) | 97% (1,458) | 97% (1,449) | 74% (1,103) |
| Group scenes (1,360) | 90% (1,224) | 92% (1,247) | 87% (1,181) | 62% (841) |
| Trades (576) | 77% (441) | 81% (467) | 75% (433) | 92% (530) |
| Big numbers (232) | 51% (119) | 46% (107) | 66% (153) | 12% (28) |
| Keeps secrets (246) | 91% (225) | 91% (224) | 89% (220) | 89% (218) |
| Lets secrets go (164) | 99% (163) | 93% (153) | 97% (159) | 85% (140) |
| Under fire (36) | 89% (32) | 86% (31) | 86% (31) | 78% (28) |
| **Average of the ten** | **81.8%** | **80.6%** | **81.7%** | **70.1%** |

Core scenes, story and setting, and under fire are hand-written. The other seven are generated on worlds held out of training, but the kinds of scene they test are in the training data, so read them as how well that training took.

At Q4_K_M, RC2 and RC1 differ beyond chance on two tests: group scenes, where RC2 is better, and big numbers, where RC1 is. RC1's 66% on big numbers was high against every other reading of this size: a second training of RC1's recipe scored 50%, and RC1's card said to treat it with care. RC2's 51% is in line with the rest. At Q5_K_M, RC2 and RC1 differ beyond chance on no test.

Untouched Gemma 4 E4B does better on core scenes and trades, at full precision and with a long prompt. Sigil's advantage is the rest of the table at a file that fits in a game.

In whole conversations of ten turns, a large language model judge, reading blind, preferred RC2 in 48 of 100 and RC1 in 38, with 14 ties. On single lines it found them level for liveliness: RC2 the livelier in 35 pairs of 100, RC1 in 37.

## Speed and memory

Measured on one NVIDIA L4 in the cloud, llama.cpp b11146, every layer on the GPU, five characters at once, one run.

| | Q4_K_M | Q5_K_M |
|---|---:|---:|
| File | 4.40 GB | 4.82 GB |
| GPU memory | 3.72 GB | 4.14 GB |
| First word, new character (median) | 151 ms | 157 ms |
| First word, follow-up line (median) | 74 ms | 76 ms |

RC1's Q4_K_M file, timed in the same run, took 148 and 72 ms and held the same memory. RC1's card showed 134 and 54 ms from an earlier run: timings move from run to run on cloud machines, so compare files timed together.

## Limits

- **Not tested on players' machines.** Consumer GPUs and CPUs are not measured.
- **Numbers are hard for it.** It passes 51% of the big-numbers test. Have the game say prices and sums when they matter.
- **Core scenes are the honest number.** At 66%, about one line in three on hand-written scenes has a fault the judge can name.
- **Voice keywords are a style, not a guarantee.** Region shows in about a third of pairs, and a stock phrase can still cross characters.
- **In long conversations it stays brief**, about six words a reply, as RC1 did.
- **English only.** Every number here is text only.
- **The judge is a language model.** One pass, with its own blind spots.
- **Training run to training run, results vary.** This recipe was trained once at this size. RC1's recipe, trained twice, averaged 81.7% and 78.8%.
- **It can be pushed out of character.** It is not a safety system, so filter what players type and what it says as your game requires.

## How it was made

It is Google's Gemma 4 E4B instruct model with a LoRA merged in, trained on synthetic scenes on generated worlds, written by a larger teacher model and checked by rule. RC2 adds 12,110 lines written for characters described by voice keywords: conversations, single replies, and pairs of characters that differ only in region. No player data was used. The base is [`google/gemma-4-E4B-it`](https://huggingface.co/google/gemma-4-E4B-it) at revision `ee0ef6023621cff504d758262d4e04895a5af4a2`.

## Licence

Apache-2.0, as is the base model.

The numbers come from the training repository's reports for this release: `2026-11-24-voice-stage-v5.md` and `2026-11-25-actor-rc2.md`, at commit `36cc363`. The model files were packaged from git tag `spellspeak-sigil-rc2` (commit `e498da6`). That repository is private.
