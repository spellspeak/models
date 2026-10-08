# SpellSpeak Tone: changelog

Revisions are numbered as in the training repo (`spellspeak/model-training`, `plans/tone/PLAN.md`). The report for each is in that repo under `reports/`.

## rc1 (2026-10-08)

Revision r7 packaged as the first release candidate and the baseline later work is compared against. Internal release `spellspeak-tone-rc1`, git tag of the same name; the model's code name in the training repo is `linecls`. First released the same day as SpellSpeak Listener (`spellspeak-listener-rc1`, the same model files) and renamed because other SpellSpeak models listen too. Card in [releases/rc1/MODEL_CARD.md](releases/rc1/MODEL_CARD.md).

## Revisions before rc1 (all 2026-10-07 and 2026-10-08)

- **r7:** calibrated confidences. A hostile tag's confidence is the chance the line is hostile toward that person; any other tag's, the chance the act is right; the emotion's, the chance the emotion is right. Three curves fitted on the dev set, carried in the model's config. Decisions unchanged. Report `2026-10-08-linecls-r7-calibration.md`.
- **r6:** sarcasm, doubling down and implied threats. The committee labelled 4,000 targeted lines, the teachers were retrained and relabelled the pool. The hostility threshold (0.775) is matched so false hostility on player speech stays at the previous version's level. Confidences returned per act and per emotion. Report `2026-10-08-linecls-r6-sarcasm.md`.
- **r5:** 95,077 lines of natural player speech in nine registers join the pool, and a committee-labelled player-speech test set joins the scorecard. Report `2026-10-08-linecls-r5-player-speech.md`.
- **r4:** MiniLM-L6 chosen over the larger Ettin students for size and speed. Models compared on three seeds from here on, since seeds alone move act F1 by about 3 points. Report `2026-10-08-linecls-r4-l6.md`.
- **r3:** four larger students tried; Ettin-32M the most accurate inside 10 ms. Meters gain courage and reputation. Report `2026-10-08-linecls-r3.md`.
- **r2:** distilled from three fine-tuned Ettin-1B teachers over a 220,705-line pool in sixteen settings; a held-out-genre slice measures fit to new games. Report `2026-10-07-linecls-r2.md`.
- **r1:** first thin slice; committee of three large-language-model labellers, heads kept inside one ONNX graph, backchannel head added. Reports `2026-10-07-linecls-*.md`.
