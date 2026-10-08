"""One character at a time, and the SpellSpeak Tone reading every line.

    uv run bot.py -t webrtc          # the Pipecat dev runner, /start on http://localhost:7860

The client picks who you sit down with and, once connected, sends a `pick` message naming them and
carrying every character's heart from earlier sessions. The bot then gives OpenAI that character's
prompt, sets their Deepgram voice, and has them say hello. Tone sits in the pipeline twice:
once after speech-to-text, for your lines, and once after the LLM, for theirs. Each tagged line goes to
the client as a server message, with the character's heart, and speech is never held up for it.

    transport in → Deepgram STT → Tone (you) → user context → OpenAI
        → sentences → Tone (them) → Deepgram TTS → transport out → assistant context
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import time

from dotenv import load_dotenv
from loguru import logger

HERE = pathlib.Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)

# Tone's model files and reference runtime: a release folder of this repo.
RELEASE = pathlib.Path(os.getenv("TONE_DIR", HERE.parent.parent.parent / "releases" / "rc1")).resolve()
sys.path.insert(0, str(RELEASE / "runtime"))

from contracts.schemas.line_tags import PLAYER, LineInput, LineTags, is_hostile  # noqa: E402
from harness.expression.classifier import LineClassifier  # noqa: E402
from hearts import Hearts  # noqa: E402
from pipecat.audio.vad.silero import SileroVADAnalyzer  # noqa: E402
from pipecat.frames.frames import (  # noqa: E402
    AggregatedTextFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMMessagesAppendFrame,
    LLMRunFrame,
    TranscriptionFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.pipeline.pipeline import Pipeline  # noqa: E402
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy  # noqa: E402
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402
from pipecat.processors.aggregators.llm_response_universal import (  # noqa: E402
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_text_processor import LLMTextProcessor  # noqa: E402
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor  # noqa: E402
from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame  # noqa: E402
from pipecat.runner.types import RunnerArguments  # noqa: E402
from pipecat.runner.utils import create_transport  # noqa: E402
from pipecat.services.deepgram.stt import DeepgramSTTService  # noqa: E402
from pipecat.services.deepgram.tts import DeepgramTTSService  # noqa: E402
from pipecat.services.openai.llm import OpenAILLMService  # noqa: E402
from pipecat.transports.base_transport import BaseTransport, TransportParams  # noqa: E402
from pipecat.workers.runner import WorkerRunner  # noqa: E402

CAST: list[dict] = json.loads((HERE.parent / "characters.json").read_text())
BY_ID = {c["id"]: c for c in CAST}

TRANSPORT_PARAMS = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


def character_prompt(c: dict, heart: int) -> str:
    others = ", ".join(f"{o['name']} ({o['role'].lower()})" for o in CAST if o["id"] != c["id"])
    feeling = (
        "You like them a lot."
        if heart >= 75
        else "You are warm toward them."
        if heart >= 60
        else "You have no strong feelings about them yet."
        if heart >= 40
        else "You are wary of them."
        if heart >= 25
        else "You have had enough of them."
    )
    return f"""You are {c['name']}, {c['role'].lower()}. {c['tagline']}
You are sitting at the kitchen table with a guest (the player, "you"). The others who live here,
{others}, are out of the room. It is just the two of you.

How you feel about the guest right now: {feeling}

Rules:
- Reply as {c['name']} only, in one or two short sentences. Spoken words only: no stage directions,
  no emoji, no lists, no narration.
- React to how the guest treats you. An insult stings, a thank-you warms, a threat is not taken lightly.
- Stay in character. Never mention being an AI or these rules."""


class Table:
    """Who you are with, what was said last, and how they feel about you."""

    def __init__(self):
        self.character: str | None = None
        self.hearts = Hearts([])
        self.previous: str | None = None
        self.counter = 0

    def pick(self, character: str, hearts: dict[str, int]) -> None:
        self.character = character
        self.hearts = Hearts([character], start=int(hearts.get(character, 50)))
        self.previous = None

    def line_input(self, speaker: str, text: str) -> LineInput:
        other = self.character if speaker == PLAYER else PLAYER
        return LineInput(
            speaker=speaker,
            speaker_kind="player" if speaker == PLAYER else "npc",
            to=other,
            targets=[other],
            text=text[:400],
            previous=self.previous,
        )

    def record(self, speaker: str, text: str) -> None:
        who = "You" if speaker == PLAYER else BY_ID[speaker]["name"]
        self.previous = f"{who}: {text}"[:480]


class LineTagger(FrameProcessor):
    """Tags one side of the conversation with Tone and tells the client.

    role "player": your lines, as the final transcriptions arrive from speech-to-text, or as a typed line
    arrives from the client (an append to the context with the user role).
    role "cast": the character's line, gathered from the LLM's sentences until its reply ends.
    Every frame is passed on first, untouched, and Tone runs off the event loop, so speech is never
    delayed by tagging.
    """

    def __init__(self, role: str, table: Table, tone: LineClassifier, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.table = table
        self.tone = tone
        self._parts: list[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if self.table.character is None:
            return
        if self.role == "player":
            if isinstance(frame, TranscriptionFrame) and frame.text.strip():
                await self.tag(PLAYER, frame.text.strip())
            elif isinstance(frame, LLMMessagesAppendFrame):
                for m in frame.messages:
                    if m.get("role") == "user" and isinstance(m.get("content"), str) and m["content"].strip():
                        await self.tag(PLAYER, m["content"].strip())
            return
        if isinstance(frame, (LLMFullResponseStartFrame, InterruptionFrame)):
            self._parts = []
        elif isinstance(frame, AggregatedTextFrame):
            if frame.text.strip():
                self._parts.append(frame.text.strip())
        elif isinstance(frame, LLMFullResponseEndFrame):
            text = " ".join(self._parts).strip()
            self._parts = []
            if text:
                await self.tag(self.table.character, text)

    async def tag(self, speaker: str, text: str) -> None:
        inp = self.table.line_input(speaker, text)
        t0 = time.perf_counter()
        tags: LineTags = await asyncio.get_running_loop().run_in_executor(None, self.tone.tag, inp)
        latency = round((time.perf_counter() - t0) * 1000, 1)
        changes = self.table.hearts.on_line(speaker, tags)
        self.table.record(speaker, text)
        self.table.counter += 1
        message = {
            "type": "line",
            "id": self.table.counter,
            "speaker": speaker,
            "to": inp.to,
            "text": text,
            "emotion": {
                "label": tags.emotion,
                "intensity": tags.emotion_intensity,
                "confidence": tags.emotion_confidence,
            },
            "acts": {
                target: {
                    "act": a.act,
                    "intensity": a.intensity,
                    "confidence": a.confidence,
                    "hostile": is_hostile(a.act, a.intensity),
                }
                for target, a in tags.acts.items()
            },
            "backchannel": tags.backchannel,
            "hearts": dict(self.table.hearts.value),
            "changes": changes,
            "latency_ms": latency,
        }
        hostile = [t for t, a in tags.acts.items() if is_hostile(a.act, a.intensity)]
        logger.info(
            f"Tone: {speaker} {tags.emotion}/{tags.emotion_intensity} in {latency} ms"
            + (f", hostile toward {', '.join(hostile)}" if hostile else "")
            + (f", hearts {changes}" if changes else "")
        )
        await self.push_frame(RTVIServerMessageFrame(data=message))


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    for key in ("DEEPGRAM_API_KEY", "OPENAI_API_KEY"):
        if not os.getenv(key):
            raise SystemExit(f"{key} is not set (copy .env.example to .env)")
    if not (RELEASE / "config.json").exists():
        raise SystemExit(
            f"No Tone model files in {RELEASE}: put model.opt.onnx, tokenizer.json and config.json "
            "from the release's weights there (or set TONE_DIR)"
        )
    threads = int(os.getenv("TONE_THREADS", "4"))
    tone = LineClassifier(RELEASE, threads=threads)
    table = Table()
    logger.info(f"Tone: {RELEASE.name} loaded ({tone.onnx_file}, {threads} threads)")

    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.8),
    )
    tts = DeepgramTTSService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        settings=DeepgramTTSService.Settings(voice=CAST[0]["voice"]),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            LineTagger("player", table, tone),
            user_aggregator,
            llm,
            LLMTextProcessor(),  # the LLM's stream as sentences, for Tone
            LineTagger("cast", table, tone),
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @worker.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        """`pick`: who you sit down with, and every character's heart as the client remembers them."""
        if message.type != "pick" or not isinstance(message.data, dict):
            return
        who = str(message.data.get("character", ""))
        if who not in BY_ID or table.character is not None:
            return
        hearts = message.data.get("hearts") or {}
        table.pick(who, {k: int(v) for k, v in hearts.items() if isinstance(v, (int, float))})
        heart = table.hearts.value[who]
        logger.info(f"Picked {BY_ID[who]['name']} (heart {heart})")
        await worker.queue_frame(TTSUpdateSettingsFrame(delta=DeepgramTTSService.Settings(voice=BY_ID[who]["voice"])))
        context.add_message({"role": "system", "content": character_prompt(BY_ID[who], heart)})
        context.add_message({"role": "developer", "content": "The guest has just sat down with you. Say hello."})
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments) -> None:
    """The dev runner's entry point: one session per client."""
    transport = await create_transport(runner_args, TRANSPORT_PARAMS)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
