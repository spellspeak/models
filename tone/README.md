# SpellSpeak Tone

AI characters in real-time, multi-party conversation need a structured reading of each utterance to update their expressions and relationships. The language model voicing a character could produce it, but only through extra output tokens, training or tool calls. That adds latency to every turn, takes capacity from the dialogue, risks malformed output, and repeats the work for each character in the scene.

SpellSpeak Tone treats the reading as multi-task classification by a separate small model. One pass over an utterance predicts the speaker's emotion and the social act directed at each person present, with a hostility probability per person. From rc2 the same pass also says what move the line makes in the conversation: does it ask, answer, pass on a rumour, say it does not know, hold back, or close the exchange. It is built for millisecond inference on a CPU, unstructured user input, and rare false hostility. It was trained on dialogue from games and fiction and on natural user speech. It is not for moderation or for judging real people.

- **In:** the line, the line before it, who speaks, who it is to, everyone present (up to 8 people). Who it is to and the line before are optional, but each helps: see the card.
- **Out, per line:** an emotion with intensity and confidence, and whether the line is only a listening sound. From rc2, the move (asks, answers, hedges, doesnt_know, withholds, closes, other) with a confidence.
- **Out, per person:** a social act (insult, threat, accusation, tease, demand, dismiss, refusal, request, thanks, praise, apology, comfort, warning, none) with intensity and confidence.
- **Size and speed:** rc2 is 27.9M parameters, 111 MB ONNX, 7 to 10 ms per line on four CPU threads. From rc2.1 the same model also comes as a 56 MB file with its weights in 16 bits, with the same tags and the same speed. rc1 is 23.6M, 94 MB, 5 to 7 ms.
- **Runtime:** ONNX Runtime on CPU. A Python reference runtime ships with each release.

## Releases

| Release | Date | Card | Internal name |
|---|---|---|---|
| [rc2.1](releases/rc2.1/) | 2026-10-09 | [README.md](releases/rc2.1/README.md) | `spellspeak-tone-rc2.2` in `spellspeak/model-training` (git tag of the same name): rc2's model files plus the 16-bit file |
| [rc2](releases/rc2/) | 2026-10-09 | [README.md](releases/rc2/README.md) | `spellspeak-tone-rc2.1` in `spellspeak/model-training`: the model files of git tag `spellspeak-tone-rc2`, packaged for Hugging Face |
| [rc1](releases/rc1/) | 2026-10-08 | [MODEL_CARD.md](releases/rc1/MODEL_CARD.md) | `spellspeak-tone-rc1` in `spellspeak/model-training` (git tag of the same name; code name `linecls`) |

Weights: [spellspeak/tone](https://huggingface.co/spellspeak/tone), rc2.1 at tag `rc2.1` and rc2 at tag `rc2` (rc1 was not uploaded). The release's manifest (`MANIFEST.json`, or `manifest.yaml` for rc1) lists every file with its size and sha256.

## What changed in rc2.1, and why

A model that ships inside a game or an app should not make its users download more than they need. rc2.1 adds a 16-bit copy of rc2's model beside the full-precision files, so a developer can pick the smaller one.

- **Half the size, the same answers.** `model_fp16.onnx` stores rc2's weights in 16 bits: 55.7 MB against 111.1 MB. On 5,204 test lines, with and without the optional inputs, at most one line in a column gets a different tag, and no scorecard number moves beyond noise.
- **The same speed, and no memory saved.** It computes in 32 bits, so it runs as fast as full precision (10.0 against 9.9 ms for 8 people on four threads) and holds no less memory. What it saves is the download and the disk.
- **Full precision stays the default and the reference.** Its files are rc2's, byte for byte. Every number on the card is full precision's, and it is the file to keep for any further training.
- **Smaller still did not hold.** 8-bit and 4-bit weights changed tags or moved scorecard numbers beyond noise, so they were not shipped.

## Try it

Each release folder holds the Python reference runtime (`runtime/`: input and output types, the classifier, calibration, the hostility decision and the input rendering) and an example. rc2.1's example fetches the model files from Hugging Face when they are not beside it: the four full-precision files (`model.opt.onnx`, `model.onnx`, `tokenizer.json`, `config.json`), or with `--fp16` only the small download, `model_fp16.onnx` with the tokenizer and the config (about 56 MB):

```bash
cd tone/releases/rc2.1
uv run example.py           # full precision
uv run example.py --fp16    # the 16-bit file: the same output
```

In your own code, `LineClassifier(folder)` loads full precision and `LineClassifier(folder, precision="fp16")` the 16-bit file.

The runtime is for inference and for building on the model: it shows exactly how a line and its scene become the model's input, and how raw scores become tags and confidences. Training code and data stay in `spellspeak/model-training`.

[examples/pipecat/](examples/pipecat/) is a Pipecat voice bot dressed as a retro terminal game: talk to Nova in a garage after hours, Audience rc2.1 decides who each line is for, Tone rc2.1 reads every line, yours and hers, and her feelings, face and Eleven v4 voice move with it, with Tone's time for every line on screen. [examples/table/](examples/table/) is a smaller one: sit down with one of four characters, every line tagged, a heart that carries over. It still runs rc1 (`TONE_DIR` defaults to `releases/rc1`). Its emotion and acts are the same in rc2, and it does not read the move yet. [CHANGELOG.md](CHANGELOG.md) has the revision history. Licence: Apache-2.0 (base model `sentence-transformers/all-MiniLM-L6-v2`, Apache-2.0).
