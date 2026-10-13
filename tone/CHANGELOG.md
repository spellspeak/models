# SpellSpeak Tone: changelog

Revisions are numbered as in the training repo (`spellspeak/model-training`, `plans/tone/PLAN.md`). The report for each is in that repo under `reports/`.

## rc4 (2026-10-13)

Revision r10: the sarcasm output. Each line also says whether it is sarcastic, with a calibrated probability, from a small head on rc3's encoder in the same pass. rc3's outputs are unchanged, so code written for rc3 runs as before. The contract becomes `line-tags-0.3`, which adds the optional `sarcasm` field and changes nothing from 0.2. Internal release `spellspeak-tone-rc4`, git tag of the same name; packaged for Hugging Face as `spellspeak-tone-rc4.1` with the same model files, the 16-bit file and public tag `rc4`.

- **Sarcasm:** labelled by the committee on 8,538 lines. On held-out game dialogue, F1 0.79 (precision 0.86, recall 0.73), against 0.91 for two of the labellers with each other: a 0.855 target that is not met. Sincere everyday lines called sarcastic 1.55%; calibration error 0.028. On sitcom and Reddit sarcasm it finds little (recall 4% and 9%) and is mostly right when it does.
- **Measured with and without the optional inputs:** without the line before, sarcasm F1 falls to 0.47; without who a line is for, 0.79.
- **Tried and not shipped:** heads on richer layers of the same pass (no better), and a head with its own trainable top layer (two points better on test, about a millisecond slower per line).
- **The same:** every rc3 tag on 3,754 test lines, the speed (9.7 ms for 8 people on four threads), and the 16-bit option (56.0 MB, the same tags and sarcasm decisions).
- **Package:** the card is in [releases/rc4/README.md](releases/rc4/README.md). The examples now run rc4 and show the sarcasm field: a badge with its probability at the table, and in the garage a bar beside the log for you and for Nova. Nova's voice also answers sarcasm in kind: a sigh at a jab when she likes you, sarcasm back when she doesn't, a laugh at teasing, and her tags now follow the mood's intensity.

Report `2026-10-13-linecls-r10-sarcasm-output.md`.

## rc3 (2026-10-13)

Revision r9: sarcasm. The encoder was trained again with sarcasm in twelve kinds (aimed at the listener, about the situation, about oneself, between friends) and sincere lines that use the same words, written by Qwen3.8-27B and labelled by the committee, and the move head was rebuilt on it. Sitcom and Reddit sarcasm sets were used only as tests, because none is licensed for training. Internal release `spellspeak-tone-rc3`, git tag of the same name; packaged for Hugging Face as `spellspeak-tone-rc3.1` with the same model files, the 16-bit file and public tag `rc3`.

- **Sarcasm:** on held-out game dialogue, hostile sarcastic lines caught 52% to 73%, sarcasm read at face value 14% to 6%, sincere look-alikes called hostile 5.5% to 3.3%.
- **Lines in a row:** a short insult or tease after one of the same is read as such; meter scenes 26 of 27 (rc2: 24). The hostility threshold is 0.675, matched to rc2's rate of harmless player lines called hostile.
- **Worse than rc2:** emotion macro-F1 0.677 to 0.649 (mostly disgust and fear), the move between characters 0.754 to 0.633, and without who a line is for, harmless player lines called hostile 1.9% to 3.9%.
- **The same:** size, speed (9.6 ms for 8 people on four threads) and the 16-bit file (55.7 MB, the same tags on 99.96% or more of the test lines).
- **Package:** the card is in [releases/rc3/README.md](releases/rc3/README.md). The examples now run rc3.

Reports `2026-10-13-linecls-r9-sarcasm.md`, `2026-10-13-linecls-r9-sarcasm-test.md`.

## rc2.1 (2026-10-09)

A smaller file beside full precision, for developers who want the smaller download. `model_fp16.onnx` is rc2's model with its weights stored in 16 bits. rc2's full-precision files are unchanged, byte for byte, and stay the default and the reference for any further training. Internal release `spellspeak-tone-rc2.2`, git tag of the same name, packaged once for Hugging Face with public tag `rc2.1`.

- **The 16-bit file:** 55.7 MB against 111.1 MB. The same tags as full precision on all but one line in a column, no scorecard number moved beyond noise, and calibration error within 0.0012. It computes in 32 bits: 10.0 ms against 9.9 for 8 people on four threads, and no memory saved.
- **Measured with and without the optional inputs:** in all four columns (as given, without who a line is for, without the line before, without either), on 5,204 test lines.
- **Tried and not shipped:** 8-bit and 4-bit weights, which changed tags or moved scorecard numbers beyond noise, and computing in 16 bits, which was slower on a CPU.
- **Runtime and example:** `LineClassifier(folder, precision="fp16")` and `example.py --fp16`. Without them, everything runs as in rc2.
- **Package:** the card is in [releases/rc2.1/README.md](releases/rc2.1/README.md).

Report `2026-10-09-linecls-precision.md`.

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
