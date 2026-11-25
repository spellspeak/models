# SpellSpeak Glyph 2B

SpellSpeak Glyph writes what a game character says next: one line of dialogue, in the character's voice, from what that character knows. It is built to ship inside a game and run on the player's machine. Glyph is the 2B size. [SpellSpeak Sigil 4B](../sigil/) is the larger one.

The game decides what is true and gives the model one character's view. The model writes the line. Actions, emotions and voice stay with the game.

**This is an alpha.** It has been measured on NVIDIA GPUs in the cloud, not on players' machines.

The Q5_K_M file is 2.91 GB. On one NVIDIA L4 with five characters it used 2.15 GB of GPU memory, and the first word came in 87 ms for a new character and 39 ms for a follow-up (medians, rc2).

## Releases

| Release | Date | What changed | Card | Hugging Face |
|---|---|---|---|---|
| rc1 | 2026-11-09 | First release | [releases/rc1](releases/rc1/README.md) | [jptaylor/spellspeak-glyph-2b](https://huggingface.co/jptaylor/spellspeak-glyph-2b/tree/rc1) |
| rc1.1 | 2026-11-09 | The same model files. The repo has its full name, and the card says what 2B covers | [releases/rc1.1](releases/rc1.1/README.md) | [jptaylor/spellspeak-glyph-2b](https://huggingface.co/jptaylor/spellspeak-glyph-2b/tree/rc1.1) |
| rc2 | 2026-11-25 | Voices from keywords: characters told apart about twice as often, length set by a keyword | [releases/rc2](releases/rc2/README.md) | [jptaylor/spellspeak-glyph-2b](https://huggingface.co/jptaylor/spellspeak-glyph-2b/tree/rc2) |

## What changed in rc2, and why

- **Voices from keywords.** A character's voice can be a short list of keywords, such as `gruff, dockside, terse, calls people "mate"`. Characters with different keywords are told apart from their lines 20.1% of the time, against 10.5% for rc1 (chance 2.3%).
- **Length follows a keyword, not the model.** Terse characters average 5.1 words a reply and chatty ones 16.9. With no length keyword a reply is about rc1's length.
- **The game scores hold.** 78.9% on GameBench against rc1's 79.2%. Group scenes improved beyond chance, and no test fell beyond chance.
- **Why:** game writers describe characters in a few words. rc1 often gave different characters the same line.

## How it scores

On the ten tests of GameBench, our benchmark for game dialogue (5,526 scenes), rc2 averages 78.9%. Google's untouched Gemma 4 model of the same size averages 57.5% at full precision with a long hand-written prompt. On the hand-written core scenes alone it passes 66%. The [card](releases/rc2/README.md) has every test, the voice keywords and the limits.

## Try it

```bash
cd releases/rc2
uv run --locked example.py
```

It needs `llama-server` from llama.cpp build b11146 or later on your PATH, and downloads the Q5_K_M file once from Hugging Face.

Weights: [jptaylor/spellspeak-glyph-2b](https://huggingface.co/jptaylor/spellspeak-glyph-2b) (rc2, rc1.1, rc1).

Licence: Apache-2.0, as is the base model, Google's Gemma 4.
