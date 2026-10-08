# SpellSpeak Tone · RC1

AI characters in real-time, multi-party conversation need a structured reading of each utterance to update their expressions and relationships. The language model voicing a character could produce it, but only through extra output tokens, training or tool calls, which adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene. SpellSpeak Tone instead treats the reading as multi-task classification by a separate small model: one pass over an utterance predicts the speaker's emotion and the social act directed at each person present, with a hostility probability per person. Its constraints are millisecond inference on a CPU, robustness to unstructured user input, and rare false hostility.

| | |
|---|---|
| **Released** | 2026-10-08 · `spellspeak-tone-rc1`, first released the same day as `spellspeak-listener-rc1` (internal code name `linecls`, revision r7) |
| **What it does** | Reads one line of game dialogue and tags the speaker's emotion and the social act toward each person in the scene |
| **Size** | 23.6M parameters · 94 MB ONNX (fp32) · about 184 MB in memory once loaded |
| **Speed** | p95 per line on 4 CPU threads (Apple M1 Max): 5.0 ms for 1 to 2 people, 5.6 ms for 4, 7.0 ms for 8. On 1 thread: 15 to 22 ms |
| **Runtime** | ONNX Runtime (1.24 or later) and tokenizers, on CPU. A Python reference runtime ships with it |
| **Files** | Weights: Hugging Face, not yet uploaded. File list and checksums: [manifest.yaml](manifest.yaml). Source: `spellspeak/model-training` at git tag `spellspeak-tone-rc1` (commit 1899ea2); R2 `models/linecls/releases/spellspeak-tone-rc1/` |
| **Licence** | Apache-2.0 |

## Input and output

- **Input:** the line, the line before it, who speaks, who it is to, and everyone present (tested up to 8 people; 160 tokens at most).
- **Per line:** an emotion (neutral, happy, amused, angry, sad, afraid, surprised, disgusted, contemptuous) with intensity (low, medium, high) and a confidence. Also whether the line is only a listening sound such as "mm-hm" (backchannel).
- **Per person:** an act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and a confidence.
- **Hostile** means insult, threat, accusation, or demand at high intensity. A tag is hostile when the hostility score reaches 0.775.
- **Confidence** is the chance the tag is right (calibrated). For a hostile tag it is the chance the line is hostile toward that person. For any other tag, the chance the act is right. For the emotion, the chance the emotion is right.

## Performance (held-out test sets, committee labels)

| Measure | Result |
|---|---|
| Act macro-F1, main test (1,905 lines) | 0.678 (95% interval 0.648 to 0.703) |
| Emotion macro-F1, main test | 0.677 |
| Natural player speech (900 lines): act F1, emotion F1 | 0.761, 0.711 |
| Game settings never seen in training (900 lines): act F1 | 0.784 |
| Harmless lines called hostile: prose-style, player speech | 1.1%, 1.7% |
| Hostile lines caught: main test, player speech | 72%, 78% |
| Sarcastic jabs caught (context test) | 9 of 30 |
| Calibration error: act tags, emotion | 0.08, 0.05 |
| For scale: two frontier labellers agree with each other at | 0.766 act F1, 0.709 emotion F1 |

## How it was made

- **Model:** MiniLM-L6 (`sentence-transformers/all-MiniLM-L6-v2` at 1110a24, Apache-2.0) with six small heads.
- **Distillation:** from three Ettin-1B teachers (`jhu-clsp/ettin-encoder-1b`, MIT) over 359,424 lines, plus 11,486 lines labelled directly.
- **Labels:** the majority vote of a committee of three large language models.
- **Lines:** our own game dialogue, Project Gutenberg dialogue, GoEmotions (Apache-2.0), Civil Comments (CC0), and lines written for this project by Qwen3.8-27B. The last include 95,000 of natural player speech and 48,000 aimed at sarcasm, doubling down and implied threats.
- **Calibration:** the threshold is matched so that it calls harmless player lines hostile no more often than the previous version. Calibration curves were fitted on the dev set.

## Use and limits

- **Use it** for NPC reactions in games: faces, feeling meters and moods. **Do not use it** for moderation, safety decisions or judging real people.
- **English only.** It reads one previous line. Older context is left to the feeling meters and the actor.
- **It misses things.** It misses about two in three sarcastic jabs and about one in four hostile lines. It calls some look-alikes hostile, such as "jk" and sincere replies to bad news.
- **Typos and speech-recognition errors** cost about 6 points of act F1.
- **It has not met real players yet.** It was tested on committee-labelled generated and hand-written lines, not real player logs.
- **Calibration** was fitted on our own dev sets. Refit it for a game whose players talk very differently.

Details: `reports/2026-10-08-linecls-r6-sarcasm.md` and `reports/2026-10-08-linecls-r7-calibration.md` in `spellspeak/model-training` at git tag `spellspeak-tone-rc1` (commit 1899ea2).
