# SpellSpeak Tone: changelog

Revisions are numbered as in the training repo (`spellspeak/model-training`, `plans/tone/PLAN.md`). The report for each is in that repo under `reports/`.

## rc2 (2026-10-09)

Revision r8: the move. One more output per line says what kind of move it makes in a conversation: asks, answers, hedges, doesnt_know, withholds, closes or other. A group conversation uses it to pick who speaks next. The contract becomes `line-tags-0.2`, which adds `exchange` and changes nothing from 0.1.

- **How:** labels from the committee on 4,992 lines, with a guide of fourteen hard edges. Three Ettin-1B teachers labelled 113,201 more lines. The move comes from trainable copies of the encoder's top two layers and a small head. rc1's encoder and heads were frozen, so every rc1 output is unchanged, checked on 3,754 test lines.
- **Numbers:** move macro-F1 0.812 against the labellers' 0.845. Asks or not 95.3%. Answered or still open 82.6%, against a 90% target that is not met. 9.7 ms for 8 people on four threads.
- **Optional inputs:** every number is also scored without who a line is for and without the line before. Without who it is for, act macro-F1 falls from 0.678 to 0.571, because insults reach bystanders. Without the line before, the move's macro-F1 falls from 0.812 to 0.740.
- **Package:** internal release `spellspeak-tone-rc2`, git tag of the same name. Repackaged for Hugging Face as `spellspeak-tone-rc2.1` with the same model files and public tag `rc2`. The card is in [releases/rc2/README.md](releases/rc2/README.md). Report `2026-10-09-linecls-r8-exchange.md`.

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
