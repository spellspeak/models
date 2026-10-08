# Neon Yard: four agents, one bot

A Pipecat voice bot with SpellSpeak Audience as its front door. Four characters stand in **Neon
Yard**, a cyberpunk station service plaza beneath an elevated transit line: Maya
(biohacker), Theo (street mechanic), Juno (courier) and Otto (a humanoid cyborg data broker). Each has their own LLM
and their own Deepgram voice, and all of them hear everything. When a user turn ends, Audience reads
who it was for before anyone answers, and the bot hands the turn to that agent:

- **One of them**, named or described ("Theo, can you fix this robot?", "you beside the hoverbike,
  how fast does it go?"): that agent answers. If Audience isn't sure, whoever you were talking to answers.
- **Everyone** ("Hello, everyone!"): they answer across the yard, likeliest first, each one told
  what the others said.
- **Unclear** (a line like "You lied to me." with nobody named): the likeliest agent asks whether you
  meant them ("Who, me?") instead of taking offence.
- **Who you're looking at.** Each character has a **look** button, and Audience reads who you're facing
  the way a game reads gaze, so a vague line can be settled by where you're looking.

Pipecat 1.12 workers, Deepgram Flux speech-to-text (which also decides when your turn ends), OpenAI
for each agent, and one Deepgram Aura-2 TTS that switches voice per agent, over WebRTC through the Pipecat dev runner. The client is Vite + React + the
Pipecat web client.

## Run

Audience's model files (`encoder.onnx`, `head.onnx`, `tokenizer.json`, `config.json`) are read from
`audience/releases/rc1/` when they're there. In a git checkout they aren't, so the bot downloads them
once from Hugging Face (`spellspeak/audience`, revision `rc1`) when it starts. The repo is private
for now: set `HF_TOKEN` (in this `.env` or the repo's own) or run `hf auth login`. If the model can't
be loaded, the bot routes with the runtime's rules baseline (it says so in the log and on screen),
which handles names and descriptions but not vague lines.

```bash
cp .env.example .env          # OPENAI_API_KEY, DEEPGRAM_API_KEY
cd server
uv run bot.py -t webrtc       # the dev runner on http://localhost:7860
```

```bash
cd client
npm install
npm run dev                   # http://localhost:5173
```

Enter the yard, allow the microphone, and they each say hello. Talk to one of them, to everyone,
or to nobody in particular, or type a line in the box under the conversation. The panel on the right
shows Audience's reading as you speak, and who your last turn went to.

## The scene

The scene asset is `client/public/neon-yard.png`, a 2048 × 2048 stylized anime and manga
cel illustration with angular, expressive faces and high-contrast cel shadows. Charcoal blue
and plum architecture carries flashes of neon colour, while the cast's distinct silhouettes and
clothing stand out. A wider camera view looks diagonally across a continuous station service plaza
beneath an elevated train, with visible paving and generous space between the four standing
characters. They face the camera at uneven depths, with distinct poses and activities beside their
own landmarks: Maya scans her plants, Theo works at his bench, Juno carries her helmet by her bike,
and Otto consults his tablet. Juno is the only human in a coat; Otto's mechanical body is exposed.

| Character | Appearance | Landmark |
|---|---|---|
| Maya | Long red braid, round safety glasses, lime-green sleeveless biotech suit with black panels and utility belt, handheld scanner | Glass tank with luminous green plants |
| Theo | Broad man with short dark hair and beard, black work tank top, orange work overalls tied at the waist, oversized silver cybernetic arm, wrench | Orange repair bench with a dismantled robot head |
| Juno | Short purple hair, yellow raincoat, motorcycle helmet | Magenta hoverbike |
| Otto | Human-height humanoid cyborg, small partial human face, short silver-white hair, one human eye and one amber optic; exposed metal cranial, jaw and neck structures, mechanical torso, both metal arms and legs; dark chassis with cyan armor panels, small glowing data tablet | Cyan vending machine |

Try "you in the lime-green suit, what are you growing?", "the mechanic with the silver arm, can you fix
this?", "you beside the hoverbike, where's the next delivery?", or "the cyborg data broker by the vending machine,
what have you heard?". The same descriptions and landmarks live in `characters.json` and are passed
to Audience as text feature cards. The image provides visual context for the person using
the demo; Audience does not perform live image recognition. The **look** controls supply explicit
gaze cues.

Edited with the built-in imagegen tool using the previous anime scene and
`output/imagegen/neon-yard-prompt-v8.txt`. The generated 1254 × 1254 source is upscaled
to the 2048 × 2048 demo asset.

## How it works

```
room                    transport → Deepgram Flux → Hearing → user aggregator → Router → CastBridge
                        → Deepgram TTS → transport → Playback → assistant aggregator
maya, theo, juno, otto  an AgentWorker each: OpenAI with their prompt, active only on their turn
```

- **Routing** (`server/audience.py`). The user aggregator's `LLMContextFrame` (a finished turn)
  never reaches an LLM directly: the `Router` takes it out of the stream, and the director asks
  Audience who it was for. Then `plan_route` decides: `unclear` at least 0.5 → the likeliest agent
  checks; `to_group` at least 0.5 → everyone, in turn; otherwise the likeliest agent, or whoever you
  spoke with last if even they are below 0.35. The floors are in `server/config.py`.
- **What Audience is given.** The line; a card per agent built from `characters.json` (name,
  aliases, role and what you can see of them, including their nearby landmark); the last four
  lines with who each was for; and spatial facts. Everyone is near and in the group, `in_view` is
  who you're looking at, `last_spoke_with_you` is who your last line was for, and `asked_you` marks
  an agent whose last line was a question. One read takes a few milliseconds on the CPU, off the
  event loop. It also reads your partial transcripts as you speak, for the client to show.
- **The agents** (`server/cast.py`). Each is an `LLMWorker`. The director activates the one whose
  turn it is with their view of the whole conversation (their own lines as replies, everyone else's
  as `[User] …` or `[Theo] …`, and a note for the moment: a group answer, a "Who, me?"). Everyone
  else is deactivated.
- **One voice at a time** (`server/director.py`). `CastBridge` brings the agents' lines in off the
  bus and switches the TTS to the speaker's voice just before each line (Deepgram reconnects for
  a new voice, so a change of speaker costs a moment). In a group answer, each
  agent waits for the one before to finish playing. Speaking cuts in and drops whoever was still to
  come.
- **The client is told everything** over RTVI server messages: `cast`, `audience` (each reading;
  for a whole turn, with its `route`), `turn`, `speaker` and `line`. It sends `look` with the agent
  you're facing.

## Files

| | |
|---|---|
| `characters.json` | the four: name, aliases, role, what you can see of them, topics, Aura-2 voice, colour. Read by the bot and the client |
| `server/bot.py` | the pipeline, the workers, the `look` message |
| `server/audience.py` | the transcript, Audience's request, and the route |
| `server/director.py` | who has the floor, and the processors that hear and steer |
| `server/cast.py` | the agents' prompts and their worker |
| `server/prompts/` | the shared prompt and a persona each |
| `client/public/neon-yard.png` | the 2048 × 2048 anime cyberpunk scene, aligned with the cast's feature cards |
| `client/` | Vite, React, Tailwind, lucide icons, the Pipecat web client over WebRTC |
