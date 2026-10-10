# The garage, after hours

A Pipecat voice bot with SpellSpeak Tone reading every line, yours and the character's, and moving
how the character feels about you. A retro terminal game: walk into the garage, talk to Nova, the
courier, and watch her face, her voice and her feelings move with what you say.

- **Your line** is read by Audience (who it's for) and then by Tone (how it sounds, and what it does
  to each person in the room), before anyone answers. "You're the best rider in the city" is
  praise: Nova warms to you. "Get lost, Nova" dismisses her: she cools.
- **Her reaction** plays over her face, big: when a line moves how she feels, a heart slams in with
  how far (whole and green up, cracked and red down); and whenever her feelings move or a new mood
  comes over her, the face flashes and bursts pixels in her mood's colour (green warm, amber cold,
  red hostile, grey neither), a hostile mood shakes the portrait, a warm one makes it hop.
- **Her face** is her mood, one of Tone's nine emotions: her reaction to what you just said, what
  she expresses in her own line as she says it, or, at rest, how she feels about you.
- **Her voice** carries the same mood: each line opens with an audio tag (`[angry]`, `[happy]`,
  `[sarcastically]`…) that Eleven v4 Turbo performs rather than says.
- **Her feelings** sit under her face, a row for each person she feels something about (you, for
  now), with a trend of where it's been.
- **The scan** shows the latest line as the models read it; **the timing panel** shows Tone's time
  for every line, in ms on the CPU, with the last, the average and the slowest.

Nothing carries over: every session starts from the feelings in `characters.json`.

Pipecat 1.12 workers on Daily, Deepgram Flux (speech to text, and when your turn ends), OpenAI
(gpt-6-luna, reasoning off) for the character, ElevenLabs Eleven v4 Turbo for the voice, and
Audience rc2.1 and Tone rc2.1 on the CPU (16-bit files). The client is Vite + React + Motion + the
Pipecat web client.

## Run

Keys go in `.env` here, beside `server/` and `client/` (`.env.example` lists them):
`OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY` and `DAILY_API_KEY` (the dev runner
makes a Daily room per session with it).

The models' files are read from `audience/releases/rc2.1/` and `tone/releases/rc2.1/` when they're
there. In a git checkout they aren't, so the bot downloads them once from Hugging Face
(`spellspeak/audience` and `spellspeak/tone`, revision `rc2.1`, about 120 MB together) when it starts.

```bash
cd server
uv run bot.py -t daily        # the dev runner: /start on http://localhost:7860
```

```bash
cd client
npm install
npm run dev                   # http://localhost:5173
```

Press **walk in** (or Enter), allow the microphone, and talk, or type a line at the prompt.
`BOT_LOG_LEVEL=DEBUG` logs what was said; INFO keeps to the decisions, with a line for every Tone
reading and the feelings it moved.

## The cast

Who's in the garage is `present` in `characters.json`. Only Nova is, for now. Bruno, Atlas and Kai
are written up there too (cards, voices, how they feel about everyone, how they take things), ready
for when they join: mark them present, give them mood sheets, and the bot routes, reads and moves
feelings for all of them. With others present, each character's prompt gains the rules for sharing
the floor (`server/prompts/group.md`), and their feelings grid a row for each of the others.

## Faces

Each character's nine faces, one per Tone emotion, go in `client/src/assets/portraits/<id>/` as
`<id>-<mood>.webp`. The client doesn't read those: it reads one mood sheet per character, which a
script makes from them:

```bash
cd client
uv run --with pillow python scripts/sheets.py
```

The faces are pixel art drawn at 256 px and scaled up; the script samples each back to 256 px,
lays the nine out 3 × 3 in Tone's order (neutral, happy, amused / angry, sad, afraid / surprised,
disgusted, contemptuous), gives the sheet one palette, and writes `client/src/assets/moods/<id>.webp`
(Nova's: 768 px, 437 KB). The title screen loads and decodes every sheet before you can walk in,
so a change of mood is only a move to another cell of an image already in memory, faded in: nothing
to fetch, nothing to decode, no flicker. A character without a sheet shows their portrait
(`client/src/assets/portraits/<id>.webp`) for every mood.

## How it works

```
room   transport → Flux → Hearing → user aggregator → Router → CastBridge → FloorGate → transport → FloorEar
nova   a CharacterWorker: OpenAI with her prompt → Mood → Eleven v4 Turbo
```

The room is Audience's garage demo (`audience/examples/pipecat`): the same turn-taking, routing,
floor and per-character Daily tracks. What's new is Tone, the feelings, and what they do to the
character:

- **Reading** (`server/tone.py`). One Tone read per line, about 10 ms on the CPU: the line, the line
  before it, who says it, who it's to (Audience's answer for yours, you for hers), and everyone
  else present by name. Tone answers with the speaker's emotion and an act toward each person
  (praise, thanks, tease, insult, threat…), each with an intensity and a confidence.
- **Feelings** (`server/feelings.py`). An act toward someone moves that person's feeling about the
  speaker, by the act (`EFFECTS`: an insult costs 10, praise gives 8, at medium intensity), its
  intensity, and how the person takes things (`warms` and `hurts` in `characters.json`: Nova is
  quicker to cool than to warm). Only acts Tone is at least half sure of count. Your own feelings
  aren't kept.
- **Moods**. A reaction shows on a face for three lines (`MOOD_LINES`): `REACTIONS` maps each act to
  a mood, and each character can react their own way (`reactions` in `characters.json`: threaten
  Nova and she's contemptuous, not afraid). What a character says, if Tone is sure of its emotion,
  shows on their face as they say it, until someone else speaks; an emotion that goes against the
  mood they were voiced in (anger in a line voiced `[happy]`) needs Tone surer still, since a teasing
  "keep talking like that and I might…" can read as a threat. At rest, a face shows how they feel
  about you. A character's next line is voiced as their reaction, or their mood at rest: never
  their own last line, which would keep them in whatever mood they last sounded.
- **Apologies** only win back what the speaker has cost them, so "Sorry, I crashed your bike"
  moves nothing.
- **Answering as they feel** (`server/director.py`, `server/cast.py`). Before a character writes a
  line, they're told how they feel about everyone and why they're in the mood they're in, and the
  line goes to the TTS opening with their mood's audio tag (`VOICE_TAGS` in `server/config.py`).
  `Mood`, between the LLM's text and the TTS, adds it; the LLM's own brackets never reach the TTS.
- **Typed lines** go to the bot as a `say` message and straight in as a finished turn, about 100 ms
  from Enter to Tone's reading. (RTVI's own send-text interrupts the bot and drains the pipeline
  first, which held a typed line up.)
- **The client** (`client/`) is told everything over RTVI server messages: `cast` (with the
  starting feelings and faces), `audience`, `tone` (each reading, its time, the feelings it moved,
  and every face), `turn` (with the line's voice tag), `voices` and `line`.

## Notes

- **Eleven v4 Turbo on Pipecat 1.12.** Pipecat's `ElevenLabsDialogueTTSService` uses ElevenLabs'
  multi-context Text-to-Dialogue WebSocket, which serves `eleven_v4_turbo` (about 100 ms to first
  audio). Pipecat 1.12 still expects a v3 model there and logs a warning for each voice at start-up;
  it works all the same, and Pipecat's next release makes v4 Turbo its default.
- **Audio tags** are free text in brackets, performed rather than said. Tried on one line, `[angry]`
  and `[shouts]` came out loudest, `[sad]` and `[nervously]` quietest, and none was spoken.
  ElevenLabs reports the tag among the words it voiced, so the floor takes it out of what was heard
  of a line cut short.
- **The voices** are ElevenLabs' premade ones, so the example runs on any account: Laura (Nova),
  Charlie (Bruno, Australian), Brian (Atlas) and Lily (Kai). Change `voice` in `characters.json`.
- **What Tone sees.** A backhanded line may not read as an act toward anyone, and moves nothing; a
  plain one does.
- **Motion** honours reduced motion: no flash, burst, shake or typing, only fades.

## Files

| | |
|---|---|
| `characters.json` | the cast: who's present, name, role, what you can see of them (their Audience card), what they know best, words for Flux, ElevenLabs voice, how they feel about everyone at the start, how they take things, colour. Read by the bot and the client |
| `server/bot.py` | the pipeline, the workers, and the `say` message for typed lines |
| `server/tone.py` | Tone's request and reading |
| `server/feelings.py` | the feelings, reactions and moods, the note each character is given, their voice tag |
| `server/audience.py` | Audience's request and reading, and the plan |
| `server/runtimes.py` | both models' runtimes in one process, and their model files |
| `server/director.py` | takes, the user's turns, Tone on every line, and the processors that hear and steer |
| `server/floor.py` | when each line plays, on whose track |
| `server/cast.py` | the characters' prompts and their worker, with the voice tag |
| `server/room.py` | the transcript, each character's view of it, and the notes |
| `server/prompts/` | the shared prompt, the rules for a group, and a persona each |
| `client/scripts/sheets.py` | each character's nine faces into one mood sheet |
| `client/src/components/character.tsx` | the character card: portrait, mood stamp, feelings grid, mood map |
| `client/src/components/fx.tsx` | the pulse: flash and burst in the mood's colour, and the heart |
| `client/src/components/` | also the sprite, the log, the scan, the timing, the prompt and the title screen |
