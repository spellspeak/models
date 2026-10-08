---
title: SpellSpeak Audience
emoji: 🗣️
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: 6.28.0
python_version: "3.12"
app_file: app.py
pinned: false
license: apache-2.0
models:
  - spellspeak/audience
short_description: Who is a line for when several characters are listening?
---

# SpellSpeak Audience demo

Try [SpellSpeak Audience](https://huggingface.co/spellspeak/audience) in the browser. Pick a room, choose where the player looks and who they were just talking with, and type a line. The model answers twice: with the spatial facts a game would send, and from the words alone.

- `app.py`: the demo, in Gradio.
- `scene.py` and `scenes.yaml`: the rooms, from the [spatial example](https://github.com/spellspeak/models/tree/main/audience/examples/spatial) in spellspeak/models. Positions become the facts the model reads through the runtime's `bands` function.
- `release/`: the model release the demo runs (rc1), as published: the reference runtime, the model files and `MANIFEST.json`. It is copied in when the Space is published, so it is not in git.

To run it on your own machine, put a release folder beside `app.py` as `release/` (or point `AUDIENCE_DIR` at one), then:

```bash
pip install gradio==6.28.0 -r requirements.txt
python app.py
```
