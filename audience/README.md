# SpellSpeak Audience

When several AI characters listen to the same person, as in a game, an interactive story or any other multi-character voice experience, the application has to know who each line is for before any character answers or reacts. A name or a description often settles it. But much of what people say names nobody: "Hello.", "Who are you?", "You lied to me.". And once the characters talk among themselves, the application also has to know who each character's line is for, to know who speaks next. Asking the language model behind each character to work it out means reading every character's context for every line. That adds latency, the characters can disagree, and a wrong guess is heard at once.

SpellSpeak Audience treats the question as classification by a separate small model. One pass reads the line, who said it, a card for each person who might be addressed (what the speaker can see of them) and, when the application knows it, where each one stands. It returns how likely the line is to be for each character, whether the evidence leaves it unclear, and whether the line is for the whole group. It scores and the application decides. It is built for millisecond inference on a CPU, typed or transcribed speech, and an honest "unclear": a character can ask "Who, me?" instead of taking offence at a line that may not have been meant for them.

**Try it in your browser:** [the demo on Hugging Face](https://huggingface.co/spaces/spellspeak/audience-demo). Weights: [spellspeak/audience](https://huggingface.co/spellspeak/audience).

The runtime calls the human in the conversation the player. Everyone who might be addressed gets a card. When a character speaks, the player is one of them.

- **In:** the line and the line before it, and who said it: the player or a character; a card per person who might be addressed (up to 8): a label, aliases and open `key: value` features; optionally, per person and from the speaker's place, how far away they are, whether the speaker is looking at them, whether they are in the speaker's group, and who spoke to whom.
- **Out, per person:** the probability that the line is for them.
- **Out, per line:** `unclear` (it could be for several people, so nobody should take it personally yet) and `to_group` (it is for everyone the speaker is talking with, or for everyone who can hear a question to the room).
- **Size and speed:** about 33M parameters, 135 MB ONNX in two graphs, about 6 ms per line on four CPU threads. Each person's card is encoded once and cached.
- **Runtime:** ONNX Runtime on CPU. A Python reference runtime ships with each release. It includes the function that turns positions and facings into the facts the model reads, and an instant rules baseline.

## Releases

| Release | Date | Card | Weights | Internal name |
|---|---|---|---|---|
| [rc2](releases/rc2/) | 2026-10-09 | [README.md](releases/rc2/README.md) | [spellspeak/audience](https://huggingface.co/spellspeak/audience), tag `rc2` | `spellspeak-audience-rc2.1` in `spellspeak/model-training` (git tag of the same name; code name `addr`, revision r3) |
| [rc1](releases/rc1/) | 2026-10-08 | [README.md](releases/rc1/README.md) | [spellspeak/audience](https://huggingface.co/spellspeak/audience), tag `rc1` | `spellspeak-audience-rc1.2` in `spellspeak/model-training` (git tag of the same name; code name `addr`, revision r2) |

A release folder here holds everything in the release except the model files. Its `MANIFEST.json` lists every file, model files included, with its size and sha256, so a download can be checked against what was tested. The card is the folder's `README.md`, the same file that is the model card on Hugging Face.

### What changed in rc2, and why

rc1 knew only the player as a speaker. In a group conversation that is not enough: the characters answer each other, and the application needs to know who each of their lines is for to pass the turn on. And a question asked of the room, "Who knows where the mill key is?", should reach everyone who can hear it, so whoever knows can answer.

- **Questions to the room** go to everyone who can hear them, whoever the speaker is looking at. With the speaker facing one person, rc2 gets all 63 test lines right, with the spatial facts and without them. rc1 sent most of them to the one person looked at: 27% right with the facts, 84% without.
- **Lines said by characters.** A request can name a character as the speaker. The player is then one of the people the line can be said to, with a card of what the characters see of them. A character's line goes to the one it was answering, unless its words pick someone else out. rc2 gets 97% of such test lines right with the facts and 98% without. rc1, which was never trained on them, gets 87% and 90%.
- **Player lines read as before.** Line by line on rc1's own test lines, rc2 is as good as rc1, with the facts and without them. Lines that should be unclear are caught more often: 92% with the facts and 95% without, from 88% and 92%.

Spatial facts are optional, so every number on the card is measured twice on the same lines: with the facts and with every fact removed. The rc2 runtime also runs rc1's model files unchanged.

## Try it

The release folder holds the Python reference runtime (`runtime/`: the person card and request types, the input rendering, the rules of evidence, the rules baseline, the classifier and the positions-to-facts function) and an example. The example fetches the four model files (`encoder.onnx`, `head.onnx`, `tokenizer.json`, `config.json`) from Hugging Face the first time, unless they are already in the folder:

```bash
cd audience/releases/rc2
uv run example.py
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

The runtime is for inference and for building on the model. It shows exactly how a line, the cards and the facts become the model's input, and how the scores come back. Training code and data stay in `spellspeak/model-training`.

[space/](space/) is the demo on Hugging Face, in Gradio. It and the two examples below still run rc1. [examples/spatial/](examples/spatial/) is a room you can rearrange: drag people around, type a line, and see who it is for, with and without the spatial facts, and as a heatmap over the floor. [examples/pipecat/](examples/pipecat/) is a Pipecat voice bot on Daily with four characters in a garage, each in their own voice: Audience reads who each of your turns is for, and one answers, a few answer in turn, everyone answers at once, or everyone it might have been for asks "Who, me?". [CHANGELOG.md](CHANGELOG.md) has the revision history. Licence: Apache-2.0 (base model `jhu-clsp/ettin-encoder-32m`, MIT).
