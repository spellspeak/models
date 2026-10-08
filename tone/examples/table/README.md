# At the table

A Pipecat voice bot with the SpellSpeak Tone slotted in. Four characters live at a kitchen table; you
sit down with one of them at a time. OpenAI speaks for whoever you picked, in their own Deepgram voice, and
Tone reads every line, yours and theirs. The client shows the character's voice as it plays, their
heart (how they feel about you), how their last line sounded and what it did to you, and what your last
line did to them. Hearts carry over between sessions, in your browser, and the character is told how they
feel about you when you sit down again.

The cascade is the usual one: Deepgram speech-to-text, OpenAI, Deepgram text-to-speech, over WebRTC
through the Pipecat dev runner. Pipecat 1.12.

```
transport in → Deepgram STT → Tone (you) → user context → OpenAI
    → sentences → Tone (them) → Deepgram TTS → transport out → assistant context
```

- **Who you are with.** The client picks a character before connecting and, once the bot is ready, sends
  a `pick` message with their id and every heart it remembers. The bot sets that character's prompt and
  voice, seeds their heart, and has them say hello.
- **Tone.** It sits in the pipeline twice (`server/bot.py`, `LineTagger`): after speech-to-text for
  your lines and after the LLM for theirs. Each frame is passed on first, and the model runs off the event
  loop, so speech never waits for a tag. Each tagged line goes to the client as a server message.
- **Hearts.** `server/hearts.py` is a small meter for the example: your acts toward a character move their
  heart by the act and its intensity when Tone is at least half sure. The framework's feeling
  meters do the real job later.
- **The voice meter** is Pipecat's `VoiceVisualizer` from the React client package, on the bot's track.
- **Colour.** A character's colour marks identity only: their name, their border when they speak, their
  voice. Every meter and badge that reads a line is coloured by sentiment (`client/src/sentiment.ts`):
  red for hostile, amber for cold, grey for neutral, green for warm. Hearts take the same scale by level.

## Run

Tone's model files (`model.opt.onnx`, `tokenizer.json`, `config.json`) go in
`tone/releases/rc1/` beside the runtime, from the release's weights.

```bash
cd server
cp .env.example .env          # DEEPGRAM_API_KEY, OPENAI_API_KEY
uv run bot.py -t webrtc       # the dev runner on http://localhost:7860
```

```bash
cd client
npm install
npm run dev                   # http://localhost:5173
```

Pick someone, connect, allow the microphone, and say hello. You can also type a line in the box under
the transcript; it goes through the same pipeline from the user context on, so it is tagged like anything
you say. Hang up and the cards show where you left each heart.

## Files

| | |
|---|---|
| `characters.json` | the four: name, role, a line of character, Deepgram voice, colour. Read by the bot and the client |
| `server/bot.py` | the pipeline, the pick message, the character prompt, the two Tone taggers |
| `server/hearts.py` | the example's heart meter |
| `client/` | Vite, React, Tailwind, lucide icons, the Pipecat web client over WebRTC |
