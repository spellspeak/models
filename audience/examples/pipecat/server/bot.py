"""Four agents in one bot, and SpellSpeak Audience deciding which of them each user turn is for.

    uv run bot.py -t webrtc          # the Pipecat dev runner, on http://localhost:7860

Five workers share one runner and its bus (`director.py` has the details):

    room                  transport → Deepgram Flux → Hearing → user aggregator → Router → CastBridge
                          → Deepgram TTS → transport → Playback → assistant aggregator
    maya, theo, juno, otto  an agent each: OpenAI with their prompt, active only on their turns

At the start of each answer, Audience reads who the user's turn was for (`audience.py`): one agent,
everyone, or unclear. The director hands the turn to that agent with the whole conversation (or to
everyone in turn, or has the likeliest ask "Who, me?"), and the bridge switches the TTS to their
voice. Deepgram does both ends: Flux hears the user and decides when their turn ends, and Aura-2
speaks for every agent. The client can say who the user is looking at (`look`), which Audience reads too. The session
ends when the client leaves.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading

from loguru import logger
from pipecat.frames.frames import InputAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    AssistantTurnStoppedMessage,
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

import services
from audience import Audience
from cast import AgentWorker, prompt
from config import ROOM, Settings, load_cast
from director import CastBridge, Director

CAST = load_cast()

_audience: Audience | None = None
_audience_lock = threading.Lock()


def shared_audience(settings: Settings) -> Audience:
    """Audience, loaded once per process and shared by every session (its cards don't change).
    The dev runner loads it at startup, so a first download never holds up a session."""
    global _audience
    with _audience_lock:
        if _audience is not None:
            return _audience
        _audience = Audience(
            CAST, engine=settings.audience_engine, threads=settings.audience_threads
        )
    return _audience


TRANSPORT_PARAMS = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    settings = Settings.from_env()
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    audience = await asyncio.to_thread(shared_audience, settings)
    director = Director(CAST, audience)

    context = LLMContext()
    aggregators = LLMContextAggregatorPair(
        # No turn strategies here: Flux recommends its own, so it decides when the user's turn ends.
        context,
        user_params=LLMUserAggregatorParams(),
    )
    bridge = CastBridge(
        director,
        voice=CAST[0].voice,
        bus=runner.bus,
        worker_name=ROOM,
        exclude_frames=(InputAudioRawFrame,),  # the microphone's audio stays in the room
        name="CastBridge",
    )
    pipeline = Pipeline(
        [
            transport.input(),
            services.stt(settings, CAST),
            director.hearing(),
            aggregators.user(),
            director.router(),
            bridge,
            services.tts(settings, CAST[0].voice),
            transport.output(),
            director.playback(),
            aggregators.assistant(),
        ]
    )
    room = PipelineWorker(
        pipeline,
        name=ROOM,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )
    director.worker = room

    @aggregators.assistant().event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(aggregator, message: AssistantTurnStoppedMessage):
        director.spawn(director.line_spoken(message.content, message.interrupted), "line")

    # Everyone says hello once the client is listening and every worker has started.
    ready: set[str] = set()

    async def ready_for(what: str) -> None:
        ready.add(what)
        if ready == {"client", "workers"}:
            await director.welcome()

    @room.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await ready_for("client")

    @room.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        """`look`: who the user is looking at ({"agent": id}, or null for nobody)."""
        if message.type == "look" and isinstance(message.data, dict):
            agent = message.data.get("agent")
            await director.look(str(agent) if agent else None)

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

    # However the room ends, the agents go with it.
    @room.event_handler("on_pipeline_finished")
    async def on_pipeline_finished(worker, frame):
        await runner.cancel()

    logger.info(
        f"Session: {', '.join(c.name for c in CAST)} on {settings.openai_model}; "
        f"Audience {audience.release} ({audience.engine})"
    )
    try:
        await runner.add_workers(
            *(AgentWorker(c, services.llm(settings, prompt(c, CAST))) for c in CAST),
            room,
        )
        await runner.run()
    finally:
        await director.close()
        logger.info("Session: ended")


async def bot(runner_args: RunnerArguments) -> None:
    """The dev runner's entry point: one session per client."""
    if not getattr(getattr(runner_args, "cli_args", None), "verbose", 0):
        logger.remove()
        logger.add(sys.stderr, level=os.getenv("BOT_LOG_LEVEL", "INFO").upper())
    transport = await create_transport(runner_args, TRANSPORT_PARAMS)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    # The runner loads dotenv with override=True; explicitly set variables must win.
    configured = dict(os.environ)
    from pipecat.runner.run import main

    os.environ.update(configured)
    settings = Settings.from_env()  # a missing key fails now, not when the first client connects
    shared_audience(settings)  # the model (downloaded the first time) before anyone connects
    main()
