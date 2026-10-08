# SpellSpeak Audience

When several AI characters listen to the same person, as in a game, an interactive story or any other multi-character voice experience, the application has to know who each line is for before any character answers or reacts. A name or a description often settles it. But much of what people say names nobody: "Hello.", "Who are you?", "You lied to me.". Asking the language model behind each character to work it out means reading every character's context for every line. That adds latency, the characters can disagree, and a wrong guess is heard at once.

SpellSpeak Audience treats the question as classification by a separate small model. One pass reads the line, a card for each character present (what the speaker can see of them) and, when the application knows it, where each one stands. It returns how likely the line is to be for each character, whether the evidence leaves it unclear, and whether the line is for the whole group. It scores and the application decides. It is built for millisecond inference on a CPU, typed or transcribed speech, and an honest "unclear": a character can ask "Who, me?" instead of taking offence at a line that may not have been meant for them.

**Try it in your browser:** [the demo on Hugging Face](https://huggingface.co/spaces/spellspeak/audience-demo). Weights: [spellspeak/audience](https://huggingface.co/spellspeak/audience).

The runtime calls the person speaking the player. Everyone who might be addressed gets a card.

- **In:** the player's line and the line before it; a card per person present (up to 8): a label, aliases and open `key: value` features; optionally, per person, how far away they are, whether the player is looking at them, whether they are in the player's group, and who spoke to whom.
- **Out, per person:** the probability that the line is for them.
- **Out, per line:** `unclear` (it could be for several people, so nobody should take it personally yet) and `to_group` (it is for everyone the player is talking with).
- **Size and speed:** about 33M parameters, 135 MB ONNX in two graphs, 6 to 7 ms per line on four CPU threads. Each person's card is encoded once and cached.
- **Runtime:** ONNX Runtime on CPU. A Python reference runtime ships with each release. It includes the function that turns positions and facings into the facts the model reads, and an instant rules baseline.

## Releases

| Release | Date | Card | Weights | Internal name |
|---|---|---|---|---|
| [rc1](releases/rc1/) | 2026-10-08 | [README.md](releases/rc1/README.md) | [spellspeak/audience](https://huggingface.co/spellspeak/audience), tag `rc1` | `spellspeak-audience-rc1.2` in `spellspeak/model-training` (git tag of the same name; code name `addr`, revision r2) |

A release folder here holds everything in the release except the model files. Its `MANIFEST.json` lists every file, model files included, with its size and sha256, so a download can be checked against what was tested. The card is the folder's `README.md`, the same file that is the model card on Hugging Face.

## Try it

The release folder holds the Python reference runtime (`runtime/`: the person card and request types, the input rendering, the rules of evidence, the rules baseline, the classifier and the positions-to-facts function) and an example. The example fetches the four model files (`encoder.onnx`, `head.onnx`, `tokenizer.json`, `config.json`) from Hugging Face the first time, unless they are already in the folder:

```bash
cd audience/releases/rc1
uv run example.py
```

The example puts a barkeep, an elf mercenary and an old sailor in a room, with the player facing the elf. It asks who three lines are for, with and without the spatial facts:

```
'You in the red hat, another round.'   with facts  tomas (0.99)
'You in the red hat, another round.'   text only   tomas (1.00)
'Hello.'                               with facts  wren (0.99)
'Hello.'                               text only   the whole group (0.99)
'You lied to me.'                      with facts  wren (0.96)
'You lied to me.'                      text only   unclear (0.99): a 'Who, me?' moment
```

The runtime is for inference and for building on the model. It shows exactly how a line, the cards and the facts become the model's input, and how the scores come back. Training code and data stay in `spellspeak/model-training`.

[space/](space/) is the demo on Hugging Face, in Gradio. [examples/spatial/](examples/spatial/) is a room you can rearrange: drag people around, type a line, and see who it is for, with and without the spatial facts, and as a heatmap over the floor. [examples/pipecat/](examples/pipecat/) puts it in front of a Pipecat voice bot with four agents: it reads who each turn is for and hands it to them (or to everyone, or has one ask "Who, me?"). [CHANGELOG.md](CHANGELOG.md) has the revision history. Licence: Apache-2.0 (base model `jhu-clsp/ettin-encoder-32m`, MIT).
