# SpellSpeak Glyph: changelog

The report for each release is in the training repo (`spellspeak/model-training`) under `reports/`.

## rc1 (2026-11-09)

The first release of the 2B size, as an alpha: internal release `spellspeak-glyph-rc1`, git tag of the same name, packaged for Hugging Face as `spellspeak-glyph-rc1.1` with the same model files and public tag `rc1`.

- **What it is:** Google's Gemma 4 E2B instruct model with a LoRA merged in, trained on synthetic scenes on generated worlds.
- **Scores:** 79.2% on average over GameBench's ten tests, against 57.5% for the untouched model with a long prompt.
- **Package:** the card is at [releases/rc1/README.md](releases/rc1/README.md).

Reports `2026-11-08-gemma-ship-files.md`, `2026-10-14-gamebench-v0.1.md`, `2026-10-14-gemma-host-memory.md`, `2026-11-08-actor-package.md`.
