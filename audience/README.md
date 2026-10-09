# SpellSpeak Audience

When several AI characters listen to the same person, as in a game, an interactive story or any other multi-character voice experience, the application has to know who each line is for before any character answers or reacts. A name or a description often settles it. But much of what people say names nobody: "Hello.", "Who are you?", "You lied to me.". And once the characters talk among themselves, the application also has to know who each character's line is for, to know who speaks next. Asking the language model behind each character to work it out means reading every character's context for every line. That adds latency, the characters can disagree, and a wrong guess is heard at once.

SpellSpeak Audience treats the question as classification by a separate small model. One pass reads the line, who said it, a card for each person who might be addressed (what the speaker can see of them) and, when the application knows it, where each one stands. It returns how likely the line is to be for each character, whether the evidence leaves it unclear, and whether the line is for the whole group. It scores and the application decides. It is built for millisecond inference on a CPU, typed or transcribed speech, and an honest "unclear": a character can ask "Who, me?" instead of taking offence at a line that may not have been meant for them.

**Try it in your browser:** [the demo on Hugging Face](https://huggingface.co/spaces/spellspeak/audience-demo). Weights: [spellspeak/audience](https://huggingface.co/spellspeak/audience), tags `rc2.1`, `rc2` and `rc1`.

The runtime calls the human in the conversation the player. Everyone who might be addressed gets a card. When a character speaks, the player is one of them.

- **In:** the line and the line before it, and who said it: the player or a character; a card per person who might be addressed (up to 8): a label, aliases and open `key: value` features; optionally, per person and from the speaker's place, how far away they are, whether the speaker is looking at them, whether they are in the speaker's group, and who spoke to whom.
- **Out, per person:** the probability that the line is for them.
- **Out, per line:** `unclear` (it could be for several people, so nobody should take it personally yet) and `to_group` (it is for everyone the speaker is talking with, or for everyone who can hear a question to the room).
- **Size and speed:** about 33M parameters. Full precision is 131.7 MB in two graphs. From rc2.1 there is also a 16-bit copy of 66.0 MB with the same answers. About 6 ms per line on four CPU threads. Each person's card is encoded once and cached.
- **Runtime:** ONNX Runtime on CPU. A Python reference runtime ships with each release. It includes the function that turns positions and facings into the facts the model reads, and an instant rules baseline.

## Releases

| Release | Date | Card | Weights | Internal name |
|---|---|---|---|---|
| [rc2.1](releases/rc2.1/) | 2026-10-09 | [README.md](releases/rc2.1/README.md) | [spellspeak/audience](https://huggingface.co/spellspeak/audience), tag `rc2.1` | `spellspeak-audience-rc2.2` in `spellspeak/model-training` (git tag of the same name; code name `addr`, revision r3) |
| [rc2](releases/rc2/) | 2026-10-09 | [README.md](releases/rc2/README.md) | [spellspeak/audience](https://huggingface.co/spellspeak/audience), tag `rc2` | `spellspeak-audience-rc2.1` in `spellspeak/model-training` (git tag of the same name; code name `addr`, revision r3) |
| [rc1](releases/rc1/) | 2026-10-08 | [README.md](releases/rc1/README.md) | [spellspeak/audience](https://huggingface.co/spellspeak/audience), tag `rc1` | `spellspeak-audience-rc1.2` in `spellspeak/model-training` (git tag of the same name; code name `addr`, revision r2) |

A release folder here holds everything in the release except the model files. Its `MANIFEST.json` lists every file, model files included, with its size and sha256, so a download can be checked against what was tested. The card is the folder's `README.md`, the same file that is the model card on Hugging Face.

### What changed in rc2.1, and why

rc2.1 adds a 16-bit copy of rc2's model beside the full-precision files, so a download can be half the size, for example where an application ships the model to a browser or a phone. Full precision is unchanged, byte for byte. It stays the default and the reference: keep it for any further training.

- **Half the download, the same answers.** `encoder_fp16.onnx` and `head_fp16.onnx` hold the same weights in 16 bits: 66.0 MB against 131.7 MB.
  - Their answers read as full precision's on 99.92% of the test lines, with the spatial facts and without them. The other two lines only change which of several tied people is on top.
  - No scorecard item is worse, and confidently wrong answers stay at 0.69% and 0.45%.
- **The same memory and speed.** The weights become 32-bit when they load, so the model uses what full precision uses (364 MB against 370 MB resident) and runs as fast.
- **Ask for it.** Use `load_classifier(folder, precision="fp16")` or `python example.py --fp16`. Without that, everything reads full precision, as before.

Lower precisions were tried too, and none ships:
- int8 weights (36 MB) change the top person among tied people and one calibration item;
- 4-bit weights (24 MB) change about one answer in ten;
- whole-graph dynamic int8 breaks the model.

rc2's changes, questions to the room and lines said by characters, are in the [CHANGELOG](CHANGELOG.md).

## Try it

The release folder holds the Python reference runtime (`runtime/`: the person card and request types, the input rendering, the rules of evidence, the rules baseline, the classifier and the positions-to-facts function) and an example. The first time, the example fetches from Hugging Face the model files its precision needs, unless they are already in the folder. Full precision needs `encoder.onnx` and `head.onnx`, and `--fp16` needs `encoder_fp16.onnx` and `head_fp16.onnx`. Both need `tokenizer.json` and `config.json`.

```bash
cd audience/releases/rc2.1
uv run example.py            # full precision, the default
uv run example.py --fp16     # the 16-bit files: half the download
```

The example puts a barkeep, an elf mercenary and an old sailor in a room, with the player facing the elf. It asks who four of the player's lines are for, with and without the spatial facts. Then the barkeep speaks, after the player asked him where the mill key is:

```
'You in the red hat, another round.'   with facts  tomas (0.99)
'You in the red hat, another round.'   text only   tomas (0.97)
'Hello.'                               with facts  wren (0.99)
'Hello.'                               text only   the whole group (0.99)
'You lied to me.'                      with facts  wren (0.98)
'You lied to me.'                      text only   unclear (1.00): a 'Who, me?' moment
'Who knows where the mill key is?'     with facts  the whole group (0.99)
'Who knows where the mill key is?'     text only   the whole group (1.00)
Tomas: 'No idea, sorry.'               text only   player (1.00)
Tomas: 'Wren, were you there?'         text only   wren (1.00)
```

With `--fp16` it prints the same lines.

The runtime is for inference and for building on the model. It shows exactly how a line, the cards and the facts become the model's input, and how the scores come back. Training code and data stay in `spellspeak/model-training`.

[space/](space/) is the demo on Hugging Face, in Gradio. It and the two examples below still run rc1. [examples/spatial/](examples/spatial/) is a room you can rearrange: drag people around, type a line, and see who it is for, with and without the spatial facts, and as a heatmap over the floor. [examples/pipecat/](examples/pipecat/) is a Pipecat voice bot on Daily with four characters in a garage, each in their own voice: Audience reads who each of your turns is for, and one answers, a few answer in turn, everyone answers at once, or everyone it might have been for asks "Who, me?". [CHANGELOG.md](CHANGELOG.md) has the revision history. Licence: Apache-2.0 (base model `jhu-clsp/ettin-encoder-32m`, MIT).
