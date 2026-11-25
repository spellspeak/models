# SpellSpeak Sigil: changelog

The report for each release is in the training repo (`spellspeak/model-training`) under `reports/`.

## rc2 (2026-11-25)

Characters can now be given a voice as a short list of keywords, and they sound like it: internal release `spellspeak-sigil-rc2`, git tag of the same name in the actor's own training repository; packaged for Hugging Face as `spellspeak-sigil-rc2.2` with the same model files and public tag `rc2`. The model was trained again with 12,110 more lines written for characters described by keywords.

- **Voices:** characters with different keywords are told apart from their lines 21.4% of the time, against 12.4% for rc1 (chance 2.3%). A pet phrase is used 15 times in 15 when given.
- **Length:** terse characters average 5.0 words a reply, chatty ones 16.8; with no length keyword, 13.4, against rc1's 14.3.
- **Scores:** 81.8% on GameBench's ten tests at Q4_K_M, against rc1's 81.7%, and 80.6% at Q5_K_M, against 82.1%. At Q4_K_M, group scenes better beyond chance (90% against 87%) and big numbers worse (51% against 66%). rc1's 66% was the outlier its card warned about: a second training of rc1's recipe scored 50%.
- **Speed and memory:** the same as rc1's file timed in the same run (151 against 148 ms to the first word, 3.72 GB of GPU memory at Q4_K_M).
- **Example:** Tomas now has a keyword voice, and the first question is asked again in a second voice.
- **Package:** the card is at [releases/rc2/README.md](releases/rc2/README.md).

Reports `2026-11-24-voice-stage-v5.md`, `2026-11-25-actor-rc2.md`.

## rc1.1 (2026-11-09)

The same model files as rc1, packaged as `spellspeak-sigil-rc1.3`, public tag `rc1.1`.

- **Name:** the Hugging Face repo is now `jptaylor/spellspeak-sigil-4b`. The card and `example.py` use it. The old name redirects.
- **Card:** it says what the 4B in the name covers, and why Hugging Face lists 8B.
- **Package:** the card is at [releases/rc1.1/README.md](releases/rc1.1/README.md).

## rc1 (2026-11-09)

The first release of the 4B size, as an alpha: internal release `spellspeak-sigil-rc1`, git tag of the same name, packaged for Hugging Face as `spellspeak-sigil-rc1.2` with the same model files and public tag `rc1`.

- **What it is:** Google's Gemma 4 E4B instruct model with a LoRA merged in, trained on synthetic scenes on generated worlds.
- **Scores:** 81.7% on average over GameBench's ten tests, against 70.1% for the untouched model with a long prompt.
- **Package:** the card is at [releases/rc1/README.md](releases/rc1/README.md).

Reports `2026-11-08-gemma-ship-files.md`, `2026-10-14-gamebench-v0.1.md`, `2026-10-14-gemma-host-memory.md`, `2026-11-08-actor-package.md`.
