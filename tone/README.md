# SpellSpeak Tone

AI characters in real-time, multi-party conversation need a structured reading of each utterance to update their expressions and relationships. The language model voicing a character could produce it, but only through extra output tokens, training or tool calls. That adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene.

SpellSpeak Tone treats the reading as multi-task classification by a separate small model. One pass over an utterance predicts the speaker's emotion and the social act directed at each person present, with a hostility probability per person. It is built for millisecond inference on a CPU, unstructured user input, and rare false hostility. It was trained on dialogue from games and fiction and on natural user speech. It is not for moderation or for judging real people.

- **In:** the line, the line before it, who speaks, who it is to, everyone present (up to 8 people).
- **Out, per line:** an emotion with intensity and confidence, and whether the line is only a listening sound.
- **Out, per person:** a social act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and confidence.
- **Size and speed:** 23.6M parameters, 94 MB ONNX, 5 to 7 ms per line on four CPU threads.
- **Runtime:** ONNX Runtime on CPU. A Python reference runtime ships with each release.

## Releases

| Release | Date | Card | Internal name |
|---|---|---|---|
| [rc1](releases/rc1/) | 2026-10-08 | [MODEL_CARD.md](releases/rc1/MODEL_CARD.md) | `spellspeak-tone-rc1` in `spellspeak/model-training` (git tag of the same name; code name `linecls`) |

Weights for a release are on Hugging Face once uploaded; the release's `manifest.yaml` lists every file with its size and sha256. Until then the files are in the team's R2 bucket at the keys the manifest gives.

## Try it

The release folder holds the Python reference runtime (`runtime/`: input and output types, the classifier, calibration, the hostility decision and the input rendering) and an example. Put the four model files from the weights (`model.opt.onnx`, `model.onnx`, `tokenizer.json`, `config.json`) in the same folder, then:

```bash
cd tone/releases/rc1
uv run example.py
```

The runtime is for inference and for building on the model: it shows exactly how a line and its scene become the model's input, and how raw scores become tags and confidences. Training code and data stay in `spellspeak/model-training`.

[examples/table/](examples/table/) is a Pipecat voice bot with Tone in it: sit down with one of four characters, every line tagged, a heart that carries over. [CHANGELOG.md](CHANGELOG.md) has the revision history. Licence: Apache-2.0 (base model `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0).
