# SpellSpeak Sigil: changelog

The report for each release is in the training repo (`spellspeak/model-training`) under `reports/`.

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
