"""The session's Pipecat services, built from `Settings`. Deepgram for both ends: Flux hears the
user (and decides when their turn ends), Aura-2 speaks for every agent."""

from __future__ import annotations

from collections.abc import Sequence

from pipecat.frames.frames import InterimTranscriptionFrame
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.utils.time import time_now_iso8601

from config import DEEPGRAM_STT_MODEL, LLM_TEMPERATURE, LLM_TOKENS, Agent, Settings


def llm(settings: Settings, system_prompt: str) -> OpenAILLMService:
    """One agent's LLM, with the agent's prompt as its system prompt."""
    return OpenAILLMService(
        api_key=settings.openai_api_key,
        settings=OpenAILLMService.Settings(
            model=settings.openai_model,
            system_instruction=system_prompt,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_TOKENS,
        ),
    )


class FluxSTTService(DeepgramFluxSTTService):
    """Deepgram Flux, with its running transcript of each turn passed on as interim
    transcriptions, as other STT services do: Audience reads along with them, and the client
    shows them. (Flux reports that transcript only as an `on_update` event.)"""

    async def _handle_update(self, transcript: str) -> None:
        if transcript:
            frame = InterimTranscriptionFrame(transcript, self._user_id, time_now_iso8601())
            await self.push_frame(frame)
        await super()._handle_update(transcript)


def stt(settings: Settings, cast: Sequence[Agent]) -> FluxSTTService:
    """Deepgram Flux, listening out for the agents' names and aliases. It also decides when the
    user's turn ends: it recommends its own turn strategies to the user aggregator."""
    keyterms = [c.name for c in cast] + [a for c in cast for a in c.aliases]
    return FluxSTTService(
        api_key=settings.deepgram_api_key,
        settings=FluxSTTService.Settings(model=DEEPGRAM_STT_MODEL, keyterm=keyterms),
    )


def tts(settings: Settings, voice: str) -> DeepgramTTSService:
    """One TTS for every agent: the bridge switches its voice to whoever is speaking (Deepgram
    reconnects for a new voice, between lines)."""
    return DeepgramTTSService(
        api_key=settings.deepgram_api_key,
        settings=DeepgramTTSService.Settings(voice=voice),
    )
