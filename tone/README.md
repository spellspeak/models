# SpellSpeak Tone

AI characters in real-time, multi-party conversation need a structured reading of each utterance to update their expressions and relationships. The language model voicing a character could produce it, but only through extra output tokens, training or tool calls. That adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene.

SpellSpeak Tone treats the reading as multi-task classification by a separate small model. One pass over an utterance predicts the speaker's emotion and the social act directed at each person present, with a hostility probability per person. From rc2 the same pass also says what move the line makes in the conversation: does it ask, answer, pass on a rumour, say it does not know, hold back, or close the exchange. From rc4 it also says whether the line is sarcastic. It is built for millisecond inference on a CPU, unstructured user input, and rare false hostility. It was trained on dialogue from games and fiction and on natural user speech. It is not for moderation or for judging real people.

- **In:** the line, the line before it, who speaks, who it is to, everyone present (up to 8 people). Who it is to and the line before are optional, but each helps: see the card.
- **Out, per line:** an emotion with intensity and confidence, and whether the line is only a listening sound. From rc2, the move (asks, answers, hedges, doesnt_know, withholds, closes, other) with a confidence. From rc4, whether the line is sarcastic, with a calibrated probability.
- **Out, per person:** a social act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and confidence.
- **Size and speed:** rc4, rc3 and rc2 are 27.9M parameters, 111 to 112 MB ONNX, 7 to 10 ms per line on four CPU threads. From rc2.1 each release also comes as a 56 MB file with its weights in 16 bits, with the same tags and the same speed. rc1 is 23.6M, 94 MB, 5 to 7 ms.
- **Runtime:** ONNX Runtime on CPU. A Python reference runtime ships with each release.

## Releases

| Release | Date | Card | Internal name |
|---|---|---|---|
| [rc4](releases/rc4/) | 2026-10-13 | [README.md](releases/rc4/README.md) | `spellspeak-tone-rc4.1` in `spellspeak/model-training`: the model files of git tag `spellspeak-tone-rc4` plus the 16-bit file |
| [rc3](releases/rc3/) | 2026-10-13 | [README.md](releases/rc3/README.md) | `spellspeak-tone-rc3.1` in `spellspeak/model-training`: the model files of git tag `spellspeak-tone-rc3` plus the 16-bit file |
| [rc2.1](releases/rc2.1/) | 2026-10-09 | [README.md](releases/rc2.1/README.md) | `spellspeak-tone-rc2.2` in `spellspeak/model-training` (git tag of the same name): rc2's model files plus the 16-bit file |
| [rc2](releases/rc2/) | 2026-10-09 | [README.md](releases/rc2/README.md) | `spellspeak-tone-rc2.1` in `spellspeak/model-training`: the model files of git tag `spellspeak-tone-rc2`, packaged for Hugging Face |
| [rc1](releases/rc1/) | 2026-10-08 | [MODEL_CARD.md](releases/rc1/MODEL_CARD.md) | `spellspeak-tone-rc1` in `spellspeak/model-training` (git tag of the same name; code name `linecls`) |

Weights: [spellspeak/tone](https://huggingface.co/spellspeak/tone), rc4 at tag `rc4`, rc3 at tag `rc3`, rc2.1 at tag `rc2.1` and rc2 at tag `rc2` (rc1 was not uploaded). The release's manifest (`MANIFEST.json`, or `manifest.yaml` for rc1) lists every file with its size and sha256.

## What changed in rc4, and why

rc3 read sarcasm into its acts and emotions, but a game could not ask whether a line was sarcastic. rc4 answers that on every line, with a probability.

- **The sarcasm output.** `sarcasm: {sarcastic, probability}` on every line. On held-out game dialogue it finds 73% of sarcastic lines and is right 86% of the time it says so (F1 0.79). It calls 1.6% of sincere everyday lines sarcastic. The probability is calibrated, so a game can show it or use its own threshold.
- **Nothing else moved.** Every rc3 tag is identical, at the same speed and 0.6 MB more. Code written for rc3 runs unchanged: the contract is `line-tags-0.3`, which adds one optional field.
- **Send the line before.** Sarcasm is read from it: without it, the model finds less than half as much.

## Try it

Each release folder holds the Python reference runtime (`runtime/`: input and output types, the classifier, calibration, the hostility decision and the input rendering) and an example. The example fetches the model files from Hugging Face when they are not beside it: the four full-precision files (`model.opt.onnx`, `model.onnx`, `tokenizer.json`, `config.json`), or with `--fp16` only the small download, `model_fp16.onnx` with the tokenizer and the config (about 56 MB):

```bash
cd tone/releases/rc4
uv run example.py           # full precision
uv run example.py --fp16    # the 16-bit file: the same tags
```

In your own code, `LineClassifier(folder)` loads full precision and `LineClassifier(folder, precision="fp16")` the 16-bit file.

The runtime is for inference and for building on the model: it shows exactly how a line and its scene become the model's input, and how raw scores become tags and confidences. Training code and data stay in `spellspeak/model-training`.

[examples/pipecat/](examples/pipecat/) is a Pipecat voice bot dressed as a retro terminal game: talk to Nova in a garage after hours, Audience rc2.1 decides who each line is for, Tone rc4 reads every line, yours and hers, and her feelings, face and Eleven v4 voice move with it, with Tone's time for every line on screen. [examples/table/](examples/table/) is a smaller one on rc4: sit down with one of four characters, every line tagged, a heart that carries over. It reads the emotion and acts, not the move. Both show how sarcastic a line is, with its probability, and in the garage Nova answers sarcasm in her own voice. [CHANGELOG.md](CHANGELOG.md) has the revision history. Licence: Apache-2.0 (base model `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0).
