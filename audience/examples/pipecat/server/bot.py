"""Four characters in a neon garage, and SpellSpeak Audience deciding who each of your turns is for.

    uv run bot.py -t daily          # the dev runner: /start on http://localhost:7860

The room, and a worker per character, share one runner and its bus:

    room                     transport → Flux → Hearing → user aggregator → Router → CastBridge
                             → FloorGate → transport → FloorEar
    nova, bruno, atlas, kai  a CharacterWorker each: OpenAI with their prompt → Aura-2 in their voice

Each character's voice plays on its own Daily audio track (a transport destination each), so they
can talk at once: "hey, all of you!" gets everyone answering together, "oi, you!" gets everyone it
might have been for asking "Who, me?". Audience reads every turn (`audience.py`), the director
plays out the plan (`director.py`), and the floor decides when each line plays (`floor.py`). The
client can say who the user is looking at (`look`), which Audience reads as gaze. The session ends
when the client leaves.
"""

from __future__ import annotations

import asyncio
import os
import sys
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
from config import ROOM, Settings, load_cast, require
from director import Director
from floor import CastBridge

CAST = load_cast()

_audience: Audience | None = None
_audience_lock = threading.Lock()


def shared_audience(settings: Settings) -> Audience:
    """Audience, loaded once per process and shared by every session (its cards don't change).
    The dev runner loads it at startup, so a first download never holds up a session."""
    global _audience
    with _audience_lock:
        if _audience is None:
            _audience = Audience(
                CAST, engine=settings.audience_engine, threads=settings.audience_threads
            )
        return _audience


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
    audience = await asyncio.to_thread(shared_audience, settings)
    director = Director(CAST, audience)

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
        """`look`: who the user is looking at ({"character": id}, or null for nobody)."""
        if message.type == "look" and isinstance(message.data, dict):
            who = message.data.get("character")
            await director.look(str(who) if who else None)

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
        f"Audience {audience.release} ({audience.engine})"
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


_logging_configured = False


def configure_logging(*, verbose: bool) -> None:
    """Once per process: BOT_LOG_LEVEL (INFO by default; DEBUG adds what was said), with the
    session id on every line."""
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True
    logger.configure(extra={"session": "-"})
    if verbose:
        return
    logger.remove()
    logger.add(
        sys.stderr,
        level=os.getenv("BOT_LOG_LEVEL", "INFO").upper(),
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | "
            "<cyan>{extra[session]}</cyan> | {name}:{line} - <level>{message}</level>"
        ),
    )


if __name__ == "__main__":
    # The runner loads dotenv with override=True; explicitly set variables must win.
    configured = dict(os.environ)
    from pipecat.runner.run import main

    os.environ.update(configured)
    settings = Settings.from_env()  # a missing key fails now, not when the first client connects
    require("DAILY_API_KEY")  # the dev runner makes a Daily room per session with it
    shared_audience(settings)  # the model (downloaded the first time) before anyone connects
    main()
