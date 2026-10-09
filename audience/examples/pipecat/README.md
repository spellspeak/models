# Four in a garage

A Pipecat voice bot with SpellSpeak Audience deciding who each of your turns is for. Four characters
share a neon garage at night: Nova the courier beside her dirt bike, Bruno the engineer crouched
at a machine, Atlas the robot in the doorway behind him, and Kai the hacker at the screens. Each
has their own LLM and their own voice on their own Daily audio track, so several can talk at once.
Nobody speaks until you do. When your turn ends, Audience reads who it was for (a few ms on the
CPU) and the room answers:

- **One of them**, by name or by what you can see ("Bruno, can you fix my bike?", "you in the
  orange jumpsuit…"): they answer. A follow-up ("it keeps stalling") stays with them.
- **A couple of them** ("Nova and Kai, what's the plan?"): they answer in turn.
- **Someone, but it's another's area** ("Nova, who can fix my bike?"), or a message for another
  ("Nova, can you ask Bruno if he'll do me a deal?"): they say so, or pass it on, and Bruno
  answers.
- **Everyone** ("hey, all of you!"): a short line gets them all answering at once, in a few words;
  a longer one, in turn. A question only one of them should take ("who can help with my bike?")
  is answered by whoever knows it best (Bruno); the rest stay out of it.
- **Nobody in particular** ("oi, you!"): everyone it might have been for asks "Who, me?" at once.
- **Who you're looking at**: click someone in the scene (or their portrait) and Audience reads it
  as gaze, so a vague line can be settled by where you're looking.

The scene shows it as it happens: as you speak, a bar under each portrait gives Audience's chance
that you mean them; whoever you're addressing is outlined and stays lit while the rest of the
garage drops back into the dark; a portrait blinks a cursor while its character thinks and glows
while they speak.

Pipecat 1.12 workers on Daily, Deepgram Flux (speech to text, and when your turn ends), OpenAI
(gpt-6-luna, reasoning off) for each character, Deepgram Aura-2 voices. The client is Vite + React
+ the Pipecat web client.

## Run

Keys go in `.env` here, beside `server/` and `client/` (`.env.example` lists them):
`OPENAI_API_KEY`, `DEEPGRAM_API_KEY` and `DAILY_API_KEY` (the dev runner makes a Daily room per
session with it).

Audience's model files (`encoder.onnx`, `head.onnx`, `tokenizer.json`, `config.json`) are read from
`audience/releases/rc1/` when they're there. In a git checkout they aren't, so the bot downloads them
once from Hugging Face (`spellspeak/audience`, revision `rc1`) when it starts. The repo is private
for now: set `HF_TOKEN` (in this `.env` or the repo's own) or run `hf auth login`. If the model can't
be loaded, the bot routes with the runtime's rules baseline (it says so in the log and on screen),
which handles names and descriptions but not vague lines.

```bash
cd server
uv run bot.py -t daily        # the dev runner: /start on http://localhost:7860
```

```bash
cd client
npm install
npm run dev                   # http://localhost:5173
```

Press **walk in**, allow the microphone, and talk. You can also type a line in the box under the
conversation. `BOT_LOG_LEVEL=DEBUG` logs what was said; INFO keeps to the decisions.

## How it works

```
room                     transport → Flux → Hearing → user aggregator → Router → CastBridge
                         → FloorGate → transport → FloorEar
nova, bruno, atlas, kai  a CharacterWorker each: OpenAI with their prompt → Aura-2 in their voice
```

The turn-taking (takes as jobs, the floor, Flux turns) comes from an earlier Pipecat table demo
whose turns were routed by Jev; here Audience routes them. Audience reads only what you say, so
the characters don't talk among themselves or fill a silence, as they did there.

- **Routing** (`server/audience.py`). The user aggregator's finished turn never reaches an LLM
  directly: the `Router` takes it out of the stream and the director asks Audience who it was for.
  Audience is given the line; a card per character from `characters.json` (name, role, what you
  can see of them); the last four lines with who each was for (lines said in a chorus left out:
  they overlap, so none is "the line before"); and spatial facts: everyone near and in the
  conversation, `in_view` for whoever you're looking at, `last_spoke_with_you`, `asked_you`. `plan`
  turns the scores into what the room does; its floors are in `server/config.py`.
- **Who answers, among those asked** (`server/prompts/character.md`, `server/room.py`). Each
  character knows what they and the others know best (`topics` in `characters.json`). Asked with
  the others, they answer only what's theirs, or what asks each of them, and otherwise write
  `[silent]` (never voiced). Asked alone, they can pass the floor to someone else (a question
  that's really theirs, or a message for them) by ending their line with `[to Bruno]`: the tag is
  kept out of the TTS, and Bruno answers next. A line that opens by calling someone by name
  ("Bruno, go easy on them") passes it too. What's passed on can't be passed again.
- **A worker per character** (`server/cast.py`). Each line is a `speak` job carrying their view of
  the whole conversation (their lines as replies, everyone else's as `[User] …` or `[Kai] …`, and a
  note for the moment: answer in turn, answer at once, ask "Who, me?"). Their TTS sends its audio to
  a transport destination named after them: their own Daily track.
- **The floor** (`server/floor.py`). Holds each line until its turn: one in turn waits for the one
  before plus a beat, a chorus is staggered over a second. While you're speaking no line starts;
  a couple of words cut everyone off, so a laugh doesn't. A line cut short is recorded as far as
  it was heard.
- **Turn-taking** (`server/services.py`). Flux ends your turn from your words and your voice; the
  Silero VAD only tells the director when your voice starts and stops. A turn that carries on one
  nobody has answered yet is read as one.
- **The client** (`client/`) is told everything over RTVI server messages: `cast`, `audience` (each
  reading, partial while you speak, and for a whole turn its plan), `turn` (a character asked for a
  line), `voices` (whose audio is playing) and `line` (the transcript). It sends `look`.
  `components/cast-audio.tsx` plays each character's Daily track; `components/scene.tsx` draws the
  outlines and the strip.

## The scene

`client/src/assets/base.png` is the garage (2048 × 2048), and `client/src/assets/portraits/` the
four portraits (256 px). Each character's outline is a
polygon in the image's own coordinates (`client/src/scene-geometry.json`), drawn as SVG with the
same cropping as the image so the two line up at any size. They come from
`client/scripts/masks/polygons.py`: rough hand-traced outlines (`polys.py`), refined against the
image with OpenCV's GrabCut, grown a few pixels, cut where someone stands in front (Atlas is behind
Bruno), and simplified to straight edges:

```bash
cd client
uv run --with opencv-python-headless --with numpy python scripts/masks/polygons.py
```

## Notes

- Deepgram's TTS service holds back each line until it hears the bot stopped speaking. A
  character's TTS runs in its own worker, where the output transport (and so that signal) never
  is, so `CharacterTTS` turns that off; the floor already decides when each line plays.
- "Oi, you!" reads as several people fairly likely but none for sure (each 0.5 to 0.8). Two or more
  above `SURE_FLOOR` (0.85) are addressed and answer in turn; fewer than that, it's played as
  unclear.
- A card works in the words people say. Nova's said "orange flight suit": "the girl in the orange
  jumpsuit" scored her 0.38 against Atlas's 0.80 (just after he'd spoken). With "orange jumpsuit
  (a flight suit)" both phrasings score her 0.99. Atlas's eyes are "red", not "orange", so "you in
  the orange" is hers alone.
- gpt-6-luna reasons before it writes unless told not to: with `reasoning_effort` "none", a line
  starts in about 0.75 s (gpt-4o-mini: 0.6 s; Luna at its default: 1.6 s). It takes no
  temperature. `OPENAI_MODEL=gpt-4o-mini` in `.env` still works.

## Files

| | |
|---|---|
| `characters.json` | the four: name, role, what you can see of them (their Audience card), what they know best, words for Flux to listen out for, Aura-2 voice, colour. Read by the bot and the client |
| `server/bot.py` | the pipeline, the workers, the `look` message |
| `server/audience.py` | Audience's request and reading, and the plan |
| `server/director.py` | takes, the user's turns, and the processors that hear and steer |
| `server/floor.py` | when each line plays, on whose track |
| `server/cast.py` | the characters' prompts and their worker |
| `server/room.py` | the transcript, each character's view of it, and the notes |
| `server/prompts/` | the shared prompt and a persona each |
| `client/src/components/scene.tsx` | the scene, the outlines, the portrait strip |
| `client/scripts/masks/` | how the outlines were made |
| `client/` | Vite, React, Tailwind, the Pipecat web client over Daily |
