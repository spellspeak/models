# SpellSpeak Sigil 4B

SpellSpeak Sigil writes what a game character says next: one line of dialogue, in the character's voice, from what that character knows. It is built to ship inside a game and run on the player's machine. Sigil is the 4B size. [SpellSpeak Glyph 2B](../glyph/) is the smaller one.

The game decides what is true and gives the model one character's view. The model writes the line. Actions, emotions and voice stay with the game.

**This is an alpha.** It has been measured on NVIDIA GPUs in the cloud, not on players' machines.

The Q4_K_M file is 4.40 GB. On one NVIDIA L4 with five characters it used 3.72 GB of GPU memory, and the first word came in 151 ms for a new character and 74 ms for a follow-up (medians, rc2; rc1's file in the same run took 148 and 72 ms).

## Releases

| Release | Date | What changed | Card | Hugging Face |
|---|---|---|---|---|
| rc1 | 2026-11-09 | First release | [releases/rc1](releases/rc1/README.md) | [jptaylor/spellspeak-sigil-4b](https://huggingface.co/jptaylor/spellspeak-sigil-4b/tree/rc1) |
| rc1.1 | 2026-11-09 | The same model files. The repo has its full name, and the card says what 4B covers | [releases/rc1.1](releases/rc1.1/README.md) | [jptaylor/spellspeak-sigil-4b](https://huggingface.co/jptaylor/spellspeak-sigil-4b/tree/rc1.1) |
| rc2 | 2026-11-25 | Voices from keywords: characters told apart about twice as often, length set by a keyword | [releases/rc2](releases/rc2/README.md) | [jptaylor/spellspeak-sigil-4b](https://huggingface.co/jptaylor/spellspeak-sigil-4b/tree/rc2) |

## What changed in rc2, and why

- **Voices from keywords.** A character's voice can be a short list of keywords, such as `gruff, dockside, terse, calls people "mate"`. Characters with different keywords are told apart from their lines 21.4% of the time, against 12.4% for rc1 (chance 2.3%).
- **Length follows a keyword, not the model.** Terse characters average 5.0 words a reply and chatty ones 16.8. With no length keyword a reply runs a little shorter than rc1's.
- **The game scores hold, but for big numbers.** 81.8% on GameBench against rc1's 81.7%. Group scenes improved beyond chance. Big numbers fell from 66% to 51%: rc1's figure was high against every other reading of this size, and a second training of rc1's recipe scored 50%.
- **Why:** game writers describe characters in a few words. rc1 often gave different characters the same line.

## How it scores

On the ten tests of GameBench, our benchmark for game dialogue (5,526 scenes), rc2 averages 81.8% at Q4_K_M and 80.6% at Q5_K_M. Google's untouched Gemma 4 model of the same size averages 70.1% at full precision with a long hand-written prompt. On the hand-written core scenes alone it passes 66%. The [card](releases/rc2/README.md) has every test, the voice keywords and the limits.

## Try it

```bash
cd releases/rc2
uv run --locked example.py
```

It needs `llama-server` from llama.cpp build b11146 or later on your PATH, and downloads the Q4_K_M file once from Hugging Face.

Weights: [jptaylor/spellspeak-sigil-4b](https://huggingface.co/jptaylor/spellspeak-sigil-4b) (rc2, rc1.1, rc1).

Licence: Apache-2.0, as is the base model, Google's Gemma 4.
