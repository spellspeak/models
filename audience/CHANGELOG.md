# SpellSpeak Audience: changelog

Revisions are numbered as in the training repo (`spellspeak/model-training`, `plans/addressee/`). The report for each is in that repo under `reports/`.

## rc1, packaged for Hugging Face (2026-10-08)

The same model files as rc1, packaged again as `spellspeak-audience-rc1.2` (an intermediate `rc1.1` was never published), so the answers are unchanged: 120 of 120 checked requests are identical. The runtime's comments no longer point at internal plans or use an insult as an example. The card is now the release folder's `README.md`: the Hugging Face header, a quick start, and an intro written for voice agents in general. The example fetches the model files from Hugging Face when they are not beside it, and so does the spatial example. `MANIFEST.json`, the release's own file list, replaces `manifest.yaml`. A demo on Hugging Face is in [space/](space/).

## rc1 (2026-10-08)

Revision r2 packaged as the first release candidate and the baseline later work is compared against. Internal release `spellspeak-audience-rc1`, git tag of the same name. The model's code name in the training repo is `addr` (the addressee model). Card in [releases/rc1/README.md](releases/rc1/README.md).

## Revisions before rc1 (both 2026-10-08)

- **r2:** simple lines. "Hello." and "Who are you?" go to the person the player is looking at, else the person they were talking with, else the one person nearby, else the whole group. They are never unclear. A thank-you or a follow-up stays with the conversation partner. Lines with consequences keep the old rule: unclear unless the signals agree. 12,730 new scenes of greetings, simple questions, openers said right after a conversation and lines with consequences, with top-ups of very short insults and of group lines said after a conversation. 91.6% of answers wholly right on the test split (rules baseline 86.4%), simple lines 91.7%. Report `2026-10-08-addr-r2-simple-lines.md`.
- **r1:** the first model. Person cards with open features, a labelling guide whose rules of evidence are also code, about 22,000 scenes built by code with known answers, a committee of three large language models checking the labels, and two architectures compared. The one with cached cards was chosen for speed. Positions become plain spatial facts through a bands function. A scene demo lets you drag people around a room. 89.5% of answers wholly right on its test split (rules baseline 86.7%). Report `2026-10-08-addr-first-models.md`.
