"""The session's Pipecat services, built from `Settings`. Deepgram for both ends: Flux hears the
user (and decides when their turn ends), Aura-2 speaks for each character on their own track."""

from __future__ import annotations

from collections.abc import Sequence

from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_stop import ExternalUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.utils.time import time_now_iso8601

from config import (
    DEEPGRAM_STT_MODEL,
    LLM_REASONING_EFFORT,
    LLM_TOKENS,
    MIN_WORDS_TO_INTERRUPT,
    Character,
    Settings,
)


def llm(settings: Settings, system_prompt: str) -> OpenAILLMService:
    """One character's LLM, with their prompt as its system prompt. A reasoning model (Luna, the
    default) is told not to reason first; an older one (OPENAI_MODEL=gpt-4o-mini) has no such
    setting."""
    reasoning = not settings.openai_model.startswith(("gpt-3", "gpt-4"))
    return OpenAILLMService(
        api_key=settings.openai_api_key,
        settings=OpenAILLMService.Settings(
            model=settings.openai_model,
            system_instruction=system_prompt,
            max_completion_tokens=LLM_TOKENS,
            extra={"reasoning_effort": LLM_REASONING_EFFORT} if reasoning else {},
        ),
    )


class FluxSTTService(DeepgramFluxSTTService):
    """Deepgram Flux, with its running transcript of each turn passed on as interim
    transcriptions, as other STT services do. The turn's start strategy counts their words,
    Audience reads along with them, and the client shows them.

    Flux reports that transcript only as an event (`on_update`), so each is pushed here, in order,
    as it arrives. A turn opens on one of those updates, and the interruption it sends clears the
    user aggregator's queue. A short turn's last update and its end can arrive together, so the
    turn's final transcript and its end are kept through interruptions: they'd be lost otherwise,
    and the turn left open with nothing said."""

    async def _handle_update(self, transcript: str) -> None:
        if transcript:
            frame = InterimTranscriptionFrame(transcript, self._user_id, time_now_iso8601())
            await self.push_frame(frame)
        await super()._handle_update(transcript)

    async def push_frame(
        self, frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM
    ) -> None:
        if isinstance(frame, (TranscriptionFrame, ProposedUserStoppedSpeakingFrame)):
            frame.interruptible = False
        await super().push_frame(frame, direction)


def stt(settings: Settings, cast: Sequence[Character]) -> FluxSTTService:
    """Deepgram Flux, listening out for the characters' names, aliases and the words people use
    about them (`keyterms` in characters.json: their role, what they wear, what's beside them)."""
    terms = [t for c in cast for t in (c.name, *c.aliases, *c.keyterms)]
    keyterms = list(dict.fromkeys(terms))  # each once, in order
    return FluxSTTService(
        api_key=settings.deepgram_api_key,
        settings=FluxSTTService.Settings(model=DEEPGRAM_STT_MODEL, keyterm=keyterms),
    )


def turn_strategies() -> UserTurnStrategies:
    """The user's turns, with Flux (`stt`) deciding when each ends. While anyone is talking it
    takes a couple of words to take the floor, so a laugh or an "mm" doesn't stop the room; when
    they're quiet, one word does."""
    return UserTurnStrategies(
        start=[MinWordsUserTurnStartStrategy(min_words=MIN_WORDS_TO_INTERRUPT)],
        stop=[ExternalUserTurnStopStrategy()],
    )


class CharacterTTS(DeepgramTTSService):
    """Deepgram's TTS, for a character's own worker. Deepgram's service holds back the next line
    until it hears that the bot stopped speaking; here the output transport is in the room, so
    that never reaches a character's worker, and their second line would wait for good. The floor
    already decides when each line plays, so the TTS voices each line as soon as it's written."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._pause_frame_processing = False


def tts(settings: Settings, character: Character) -> CharacterTTS:
    """A character's own voice. Its audio goes to the transport destination named after them:
    their own audio track in the room, so several of them can speak at once."""
    return CharacterTTS(
        api_key=settings.deepgram_api_key,
        settings=CharacterTTS.Settings(voice=character.voice),
        transport_destination=character.id,
    )
