# SpellSpeak Sigil 4B

SpellSpeak Sigil writes what a game character says next: one line of dialogue, in the character's voice, from what that character knows. It is built to ship inside a game and run on the player's machine. Sigil is the 4B size. [SpellSpeak Glyph 2B](../glyph/) is the smaller one.

The game decides what is true and gives the model one character's view. The model writes the line. Actions, emotions and voice stay with the game.

**This is an alpha.** It has been measured on NVIDIA GPUs in the cloud, not on players' machines.

The Q4_K_M file is 4.40 GB. On one NVIDIA L4 with five characters it used 3.72 GB of GPU memory, and the first word came in 134 ms for a new character and 54 ms for a follow-up (medians).

## Releases

| Release | Date | What changed | Card | Hugging Face |
|---|---|---|---|---|
| rc1 | 2026-11-09 | First release | [releases/rc1](releases/rc1/README.md) | [jptaylor/spellspeak-sigil-4b](https://huggingface.co/jptaylor/spellspeak-sigil-4b/tree/rc1) |

## How it scores

On the ten tests of GameBench, our benchmark for game dialogue (5,526 scenes), rc1 averages 81.7%. Google's untouched Gemma 4 model of the same size averages 70.1% at full precision with a long hand-written prompt. On the hand-written core scenes alone it passes 69%. The [card](releases/rc1/README.md) has every test and the limits.

## Try it

```bash
cd releases/rc1
uv run --locked example.py
```

It needs `llama-server` from llama.cpp build b11146 or later on your PATH, and downloads the Q4_K_M file once from Hugging Face.

Weights: [jptaylor/spellspeak-sigil-4b](https://huggingface.co/jptaylor/spellspeak-sigil-4b) (rc1).

Licence: Apache-2.0, as is the base model, Google's Gemma 4.
