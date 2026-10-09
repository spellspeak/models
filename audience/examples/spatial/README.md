# Who is it for? Spatial facts in the mix

A top-down room you can rearrange. Drag the player and the people around, turn them, type a line, and see who SpellSpeak Audience thinks it is for. The scores update as you drag.

The example shows how an application that tracks where people stand, such as a game or a VR scene, feeds the model what it knows about the room. It has positions and facings in its own units. The model reads plain facts on each person's card: how far away they are (near, mid, far), whether the player is looking at them, whether they are in the player's group, and who followed, asked or spoke last. The runtime's `bands` function (`releases/rc1/runtime/harness/addressee/bands.py`) turns one into the other. `scene.py` here does the rest of the work the application would do:

- **Earshot.** Anyone beyond earshot is left out of the request, so the line can never be for them.
- **Objects.** A person within 1.5 m of an object gets `near: <phrase>` on their card. "The one by the fire" means whoever is standing by the fire now.
- **Text only.** The same scene with no facts, as an application without positions would send it. Tick it to see what the facts change. In the tavern, "Hello." goes to Wren, whom you face, with the facts and to the whole group without them.

## Run

The model files (`encoder.onnx`, `head.onnx`, `tokenizer.json`, `config.json`) are fetched from [Hugging Face](https://huggingface.co/spellspeak/audience) the first time, unless they are already in `audience/releases/rc1/` beside the runtime.

```bash
cd audience/examples/spatial
uv run server.py              # http://127.0.0.1:8768
```

Without the model files the page still runs on the rules baseline and says why the model is missing.

## On the page

- **The room.** Drag people, objects and the player. Drag the small dot to turn someone, or scroll over them. The dashed rings are the near, mid and earshot distances. The blue wedge is the player's gaze. Each person fills with blue by how likely the line is for them.
- **Who it is for.** The model's reading and a bar per person, plus `unclear` and `whole group`. With both engines ticked, the rules baseline sits under the model for comparison.
- **What the app knows.** The facts for each person. The group comes from a simple circle rule (within 2.5 m, in front of the player, facing them) unless you set it by hand. Follows, asked and spoke last are yours to set.
- **Conversation so far.** Earlier lines, oldest first.
- **Heatmap.** Pick a person and colour the floor by how likely the line is for them if they stood there. It is the quickest way to see the facts at work, and to tune the band edges for your own scenes.
- **What the model reads.** The exact input text for this scene.

## Files

| | |
|---|---|
| `scenes.yaml` | the cards (what the player can see of each person) and two rooms: a tavern and a space station |
| `scene.py` | a scene to a request: positions to facts, earshot, objects, text only |
| `server.py` | a small local web server: the rules and the model, the heatmap. Standard library plus the runtime |
| `index.html` | the page |

`AUDIENCE_DIR` points at another release folder (runtime and model files). `AUDIENCE_THREADS` sets the model's CPU threads (default 4). `PORT` changes the port.
