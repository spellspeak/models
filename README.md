# spellspeak

Models for interactive, conversational AI.

They are small and fast, built to run beside a live conversation rather than in a data centre. Each one does one job well: reading how a line was said, working out who it was said to, or speaking as a character. They answer in milliseconds on a CPU or a modest GPU, so a game character, a companion, an assistant or a device can respond like a person in the room. They run locally, inside the application that uses them.

Each model has a folder here: what it does, a model card for every release, its licence, demos and examples. Weights live on Hugging Face. Every release has a manifest listing its files with checksums, so a download can be checked against what was tested.

| Model | What it does | Latest release | Weights |
|---|---|---|---|
| [SpellSpeak Tone](tone/) | Reads one line of dialogue and says how the speaker sounds and what the line does to each person present: an emotion, a social act, and how sure it is | [rc1](tone/releases/rc1/) · 2026-10-08 | Hugging Face, not yet uploaded |
| [SpellSpeak Audience](audience/) | Works out who a spoken or typed line is for when several AI characters are listening: one of them, the whole group, or unclear, so a character can ask "Who, me?" instead of taking offence | [rc1](audience/releases/rc1/) · 2026-10-08 | [spellspeak/audience](https://huggingface.co/spellspeak/audience) · [demo](https://huggingface.co/spaces/spellspeak/audience-demo) |

More models join this table as they reach a release candidate.

Training, data and benchmarks live in `spellspeak/model-training`. A release here is a copy of something that repo tagged. A model card carries only measured numbers and names the report and commit they come from.

Everything here is under the [Apache-2.0 licence](LICENSE) unless a model folder says otherwise.
