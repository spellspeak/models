"""A garage after hours, where characters feel something about you and about one another.
SpellSpeak Audience decides who each of your turns is for, and SpellSpeak Tone reads every line,
yours and theirs, and moves those feelings. Who's here is `present` in characters.json (Nova, for
now).

    uv run bot.py -t daily          # the dev runner: /start on http://localhost:7860

The room, and a worker per character, share one runner and its bus:

    room        transport → Flux → Hearing → user aggregator → Router → CastBridge → FloorGate
                → transport → FloorEar
    character   a CharacterWorker each: OpenAI with their prompt → Eleven v4 Turbo in their voice,
                with an audio tag for their mood

Each character's voice plays on its own Daily audio track, so they can talk at once. Audience reads
every turn (`audience.py`), Tone every line (`tone.py`), feelings and faces move with what Tone
reads (`feelings.py`), the director plays out the plan (`director.py`), and the floor decides when
each line plays (`floor.py`). The session ends when the client leaves; nothing carries over.
"""

from __future__ import annotations

import asyncio
import os
import threading
import uuid

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMUserAggregator,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.daily.transport import DailyParams
from pipecat.workers.runner import WorkerRunner

import services
from audience import Audience
from cast import CharacterWorker, prompt
from config import ROOM, Settings, configure_logging, load_cast, require
from director import Director
from floor import CastBridge
from tone import Tone

CAST = load_cast()

_models: tuple[Audience, Tone] | None = None
_models_lock = threading.Lock()


def shared_models(settings: Settings) -> tuple[Audience, Tone]:
    """Audience and Tone, loaded once per process and shared by every session (neither keeps
    anything of a session). The dev runner loads them at startup, so a first download never holds
    up a session."""
    global _models
    with _models_lock:
        if _models is None:
            audience = Audience(CAST, engine=settings.audience_engine, threads=settings.threads)
            _models = (audience, Tone(CAST, threads=settings.threads))
        return _models


TRANSPORT_PARAMS = {
    # A custom audio track per character, named by their id; no default microphone track.
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_out_destinations=[c.id for c in CAST],
        microphone_out_enabled=False,
        camera_out_enabled=False,
    ),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    settings = Settings.from_env()
    ids = [c.id for c in CAST]
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    audience, tone = await asyncio.to_thread(shared_models, settings)
    director = Director(CAST, audience, tone)

    user = LLMUserAggregator(
        LLMContext(),
        params=LLMUserAggregatorParams(
            # Not for turns (Flux decides those): the director hears from it when the user's
            # voice starts and stops, so that no line starts over them.
            vad_analyzer=SileroVADAnalyzer(),
            user_turn_strategies=services.turn_strategies(),
        ),
    )
    pipeline = Pipeline(
        [
            transport.input(),
            services.stt(settings, CAST),
            director.hearing(),
            user,
            director.router(),
            CastBridge(ids, bus=runner.bus, worker_name=ROOM),
            director.floor.gate(),
            transport.output(),
            director.floor.ear(),
        ]
    )
    room = PipelineWorker(
        pipeline,
        name=ROOM,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )
    director.worker = room

    # The client is told who's here once it's listening and every worker has started. Nobody
    # speaks until the user does.
    ready: set[str] = set()

    async def ready_for(what: str) -> None:
        ready.add(what)
        if ready == {"client", "workers"}:
            await director.send_cast()

    @room.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await ready_for("client")

    @room.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        """`say`: a line the user typed ({"text": …})."""
        if message.type == "say" and isinstance(message.data, dict):
            await director.say(str(message.data.get("text", "")))

    @runner.event_handler("on_ready")
    async def on_ready(runner):
        await ready_for("workers")

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Session: client connected")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Session: client left")
        await runner.cancel()

    # However the room ends, the characters go with it: they'd otherwise keep their LLM and TTS
    # connections open for good.
    @room.event_handler("on_pipeline_finished")
    async def on_pipeline_finished(worker, frame):
        await runner.cancel()

    logger.info(
        f"Session: {', '.join(c.name for c in CAST)} on {settings.openai_model}; "
        f"Audience {audience.release} ({audience.engine}), Tone {tone.release}"
    )
    try:
        await runner.add_workers(
            *(
                CharacterWorker(
                    c, services.llm(settings, prompt(c, CAST)), services.tts(settings, c)
                )
                for c in CAST
            ),
            room,
        )
        await runner.run()
    finally:
        await director.close()
        logger.info("Session: ended")


async def bot(runner_args: RunnerArguments) -> None:
    """The entry point (the dev runner's): one session per client. Every log line of the session
    carries its id."""
    configure_logging(verbose=bool(getattr(getattr(runner_args, "cli_args", None), "verbose", 0)))
    session = (getattr(runner_args, "session_id", None) or uuid.uuid4().hex)[:8]
    with logger.contextualize(session=session):
        transport = await create_transport(runner_args, TRANSPORT_PARAMS)
        await run_bot(transport, runner_args)


if __name__ == "__main__":
    # The runner loads dotenv with override=True; explicitly set variables must win.
    configured = dict(os.environ)
    from pipecat.runner.run import main

    os.environ.update(configured)
    settings = Settings.from_env()  # a missing key fails now, not when the first client connects
    require("DAILY_API_KEY")  # the dev runner makes a Daily room per session with it
    shared_models(settings)  # the models (downloaded the first time) before anyone connects
    main()
