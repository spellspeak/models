# SpellSpeak Glyph: changelog

The report for each release is in the training repo (`spellspeak/model-training`) under `reports/`.

## rc2 (2026-11-25)

Characters can now be given a voice as a short list of keywords, and they sound like it: internal release `spellspeak-glyph-rc2`, git tag of the same name in the actor's own training repository; packaged for Hugging Face as `spellspeak-glyph-rc2.1` with the same model files and public tag `rc2`. The model was trained again with 12,110 more lines written for characters described by keywords.

- **Voices:** characters with different keywords are told apart from their lines 20.1% of the time, against 10.5% for rc1 (chance 2.3%). A pet phrase is used 15 times in 15 when given.
- **Length:** terse characters average 5.1 words a reply, chatty ones 16.9; with no length keyword, 13.4, about rc1's length.
- **Scores:** 78.9% on GameBench's ten tests, against rc1's 79.2%. Group scenes better beyond chance (92% against 90%), no test worse beyond chance. Trades 64% against 67%.
- **Speed and memory:** the same as rc1's file timed in the same run (87 against 88 ms to the first word, 2.15 GB of GPU memory).
- **Example:** Tomas now has a keyword voice, and the first question is asked again in a second voice.
- **Package:** the card is at [releases/rc2/README.md](releases/rc2/README.md).

Reports `2026-11-24-voice-stage-v5.md`, `2026-11-25-actor-rc2.md`.

## rc1.1 (2026-11-09)

The same model files as rc1, packaged as `spellspeak-glyph-rc1.3`, public tag `rc1.1`.

- **Name:** the Hugging Face repo is now `jptaylor/spellspeak-glyph-2b`. The card and `example.py` use it. The old name redirects.
- **Card:** it says what the 2B in the name covers, and why Hugging Face lists 5B.
- **Package:** the card is at [releases/rc1.1/README.md](releases/rc1.1/README.md).

## rc1 (2026-11-09)

The first release of the 2B size, as an alpha: internal release `spellspeak-glyph-rc1`, git tag of the same name, packaged for Hugging Face as `spellspeak-glyph-rc1.2` with the same model files and public tag `rc1`.

- **What it is:** Google's Gemma 4 E2B instruct model with a LoRA merged in, trained on synthetic scenes on generated worlds.
- **Scores:** 79.2% on average over GameBench's ten tests, against 57.5% for the untouched model with a long prompt.
- **Package:** the card is at [releases/rc1/README.md](releases/rc1/README.md).

Reports `2026-11-08-gemma-ship-files.md`, `2026-10-14-gamebench-v0.1.md`, `2026-10-14-gemma-host-memory.md`, `2026-11-08-actor-package.md`.
