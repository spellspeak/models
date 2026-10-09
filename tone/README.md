# SpellSpeak Tone

AI characters in real-time, multi-party conversation need a structured reading of each utterance to update their expressions and relationships. The language model voicing a character could produce it, but only through extra output tokens, training or tool calls. That adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene.

SpellSpeak Tone treats the reading as multi-task classification by a separate small model. One pass over an utterance predicts the speaker's emotion and the social act directed at each person present, with a hostility probability per person. From rc2 the same pass also says what move the line makes in the conversation: does it ask, answer, pass on a rumour, say it does not know, hold back, or close the exchange. It is built for millisecond inference on a CPU, unstructured user input, and rare false hostility. It was trained on dialogue from games and fiction and on natural user speech. It is not for moderation or for judging real people.

- **In:** the line, the line before it, who speaks, who it is to, everyone present (up to 8 people). Who it is to and the line before are optional, but each helps: see rc2's card.
- **Out, per line:** an emotion with intensity and confidence, and whether the line is only a listening sound. From rc2, the move (asks, answers, hedges, doesnt_know, withholds, closes, other) with a confidence.
- **Out, per person:** a social act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and confidence.
- **Size and speed:** rc2 is 27.9M parameters, 111 MB ONNX, 7 to 10 ms per line on four CPU threads. rc1 is 23.6M, 94 MB, 5 to 7 ms.
- **Runtime:** ONNX Runtime on CPU. A Python reference runtime ships with each release.

## Releases

| Release | Date | Card | Internal name |
|---|---|---|---|
| [rc2](releases/rc2/) | 2026-10-09 | [README.md](releases/rc2/README.md) | `spellspeak-tone-rc2.1` in `spellspeak/model-training`: the model files of git tag `spellspeak-tone-rc2`, packaged for Hugging Face |
| [rc1](releases/rc1/) | 2026-10-08 | [MODEL_CARD.md](releases/rc1/MODEL_CARD.md) | `spellspeak-tone-rc1` in `spellspeak/model-training` (git tag of the same name; code name `linecls`) |

Weights: [spellspeak/tone](https://huggingface.co/spellspeak/tone), rc2 at tag `rc2` (rc1 was not uploaded). The release's manifest (`MANIFEST.json`, or `manifest.yaml` for rc1) lists every file with its size and sha256.

## What changed in rc2, and why

Group conversations need to know who should speak next. When the player asks the room "Who knows where the mill key is?", each character can answer in its own words. Then the application should play the one who answers, maybe add the one who heard a rumour, and drop the "no idea" and the dodges. When two characters talk, the exchange should stop once a line closes it. rc2 gives every line its move for that.

- **The emotion and the acts are rc1's, unchanged.** The move comes from two extra encoder layers and a small head beside rc1's frozen encoder, in the same pass. It costs about 2 ms a line.
- **The move:** macro-F1 0.81 against the labellers' own agreement of 0.85. It is right on "asks or not" 95% of the time.
- **It misses its target on "answered or still open":** 83% on the right side against a 90% target. On characters' lines it is 86%. The labellers themselves agree on it about 89% of the time.
- **Who a line is for, and the line before, are optional.** rc2's card scores every number with and without each. Without who it is for, insults spread to bystanders. Without the line before, the move drops most.

## Try it

Each release folder holds the Python reference runtime (`runtime/`: input and output types, the classifier, calibration, the hostility decision and the input rendering) and an example. rc2's example fetches the four model files (`model.opt.onnx`, `model.onnx`, `tokenizer.json`, `config.json`) from Hugging Face when they are not beside it. Until the upload, put them in the folder yourself, then:

```bash
cd tone/releases/rc2
uv run example.py
```

The runtime is for inference and for building on the model: it shows exactly how a line and its scene become the model's input, and how raw scores become tags and confidences. Training code and data stay in `spellspeak/model-training`.

[examples/table/](examples/table/) is a Pipecat voice bot with Tone in it: sit down with one of four characters, every line tagged, a heart that carries over. It still runs rc1 (`TONE_DIR` defaults to `releases/rc1`). Its emotion and acts are the same in rc2, and it does not read the move yet. [CHANGELOG.md](CHANGELOG.md) has the revision history. Licence: Apache-2.0 (base model `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0).
