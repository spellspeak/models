# SpellSpeak Audience: changelog

Revisions are numbered as in the training repo (`spellspeak/model-training`, `plans/addressee/`). The report for each is in that repo under `reports/`.

## rc2 (2026-10-09)

Revision r3 packaged as the second release candidate: `spellspeak-audience-rc2.1`, git tag of the same name. The model was trained at git tag `spellspeak-audience-rc2`; its first package carried an earlier card and was never published. Card in [releases/rc2/README.md](releases/rc2/README.md).

- **r3: the group conversation.** Questions to the room ("Who knows where the mill key is?", "Anyone seen my horse?") go to everyone who can hear them, whoever the speaker is looking at. A character may speak: the player is then one of the people the line can be said to, and a character's line that picks no one out goes to the one it was answering. When a line has both group words and room words, the group words win. New inputs, `addressee-tt-0.6`. The runtime still builds rc1's inputs byte for byte, so it runs rc1's model files unchanged. 7,731 new scenes: questions to the room, lines said by characters, corrections, and short lines with consequences that carry spatial facts. The people of every training line come in a new order in every batch.
- **Measured with and without spatial facts.** Spatial facts are optional, so every number is measured twice on the same lines, with the facts and with every fact removed, each against its own answer. On the main test 95.2% of answers are wholly right with the facts and 96.6% without (rc1 89.9% and 94.2%). Questions to the room with the speaker facing one person: 63 of 63 in both columns (rc1 27% and 84%). Lines said by characters: 97.2% and 97.9% (rc1 86.5% and 89.6%).
- **Test labels voted again.** One member of the three-model labelling committee was replaced during testing, and the test lines were voted again: 57 of 2,719 majorities changed, and every scorecard item moved by 0.4 points or less. The card uses the new votes.
- **The runtime's comments** no longer point at internal plans.

Reports `2026-10-09-addr-r3.md` and `2026-10-09-addr-r3-setup.md`.

## rc1, packaged for Hugging Face (2026-10-08)

The same model files as rc1, packaged again as `spellspeak-audience-rc1.2` (an intermediate `rc1.1` was never published), so the answers are unchanged: 120 of 120 checked requests are identical. The runtime's comments no longer point at internal plans or use an insult as an example. The card is now the release folder's `README.md`: the Hugging Face header, a quick start, and an intro written for voice agents in general. The example fetches the model files from Hugging Face when they are not beside it, and so does the spatial example. `MANIFEST.json`, the release's own file list, replaces `manifest.yaml`. A demo on Hugging Face is in [space/](space/).

## rc1 (2026-10-08)

Revision r2 packaged as the first release candidate and the baseline later work is compared against. Internal release `spellspeak-audience-rc1`, git tag of the same name. The model's code name in the training repo is `addr` (the addressee model). Card in [releases/rc1/README.md](releases/rc1/README.md).

## Revisions before rc1 (both 2026-10-08)

- **r2:** simple lines. "Hello." and "Who are you?" go to the person the player is looking at, else the person they were talking with, else the one person nearby, else the whole group. They are never unclear. A thank-you or a follow-up stays with the conversation partner. Lines with consequences keep the old rule: unclear unless the signals agree. 12,730 new scenes of greetings, simple questions, openers said right after a conversation and lines with consequences, with top-ups of very short insults and of group lines said after a conversation. 91.6% of answers wholly right on the test split (rules baseline 86.4%), simple lines 91.7%. Report `2026-10-08-addr-r2-simple-lines.md`.
- **r1:** the first model. Person cards with open features, a labelling guide whose rules of evidence are also code, about 22,000 scenes built by code with known answers, a committee of three large language models checking the labels, and two architectures compared. The one with cached cards was chosen for speed. Positions become plain spatial facts through a bands function. A scene demo lets you drag people around a room. 89.5% of answers wholly right on its test split (rules baseline 86.7%). Report `2026-10-08-addr-first-models.md`.
