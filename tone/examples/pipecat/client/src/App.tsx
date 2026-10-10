import { PipecatClient, RTVIEvent } from "@pipecat-ai/client-js"
import {
  PipecatClientProvider,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react"
import { DailyTransport } from "@pipecat-ai/daily-transport"
import { LogOut } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { CAST } from "@/cast"
import { Boot } from "@/components/boot"
import { CastAudio } from "@/components/cast-audio"
import { CharacterCard } from "@/components/character"
import { Log } from "@/components/log"
import { PixelButton } from "@/components/panel"
import { Prompt } from "@/components/prompt"
import { Scan } from "@/components/scan"
import { Timing } from "@/components/timing"
import { useRoom } from "@/store"
import type { ServerMessage } from "@/types"

/**
 * Where a session starts: the Pipecat dev runner's /start (`cd server && uv run bot.py -t daily`).
 * It makes a Daily room, starts the bot in it, and answers with the room's URL and a token.
 */
const START_URL = import.meta.env.VITE_BOT_START_URL || "http://localhost:7860/start"

/** RTVI events into the room's store: the bot's server messages, and your speech. */
function RoomSync() {
  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback((data: unknown) => {
      const m = data as ServerMessage
      if (m && typeof m === "object" && "type" in m) useRoom.getState().receive(m)
    }, [])
  )
  useRTVIClientEvent(
    RTVIEvent.UserTranscript,
    useCallback((data: { text: string; final: boolean }) => {
      if (data.text.trim()) useRoom.getState().hear(data.text, data.final)
    }, [])
  )
  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, useCallback(() => useRoom.getState().setUserSpeaking(true), []))
  useRTVIClientEvent(RTVIEvent.UserStoppedSpeaking, useCallback(() => useRoom.getState().setUserSpeaking(false), []))
  useRTVIClientEvent(RTVIEvent.Connected, useCallback(() => useRoom.getState().reset(), []))
  return null
}

/** Time in the garage, as T+mm:ss. */
function Clock() {
  const [start] = useState(() => Date.now())
  const [now, setNow] = useState(start)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  const s = Math.floor((now - start) / 1000)
  return (
    <span className="tabular-nums">
      t+{String(Math.floor(s / 60)).padStart(2, "0")}:{String(s % 60).padStart(2, "0")}
    </span>
  )
}

function TopBar({ onLeave }: { onLeave: () => void }) {
  const engine = useRoom((s) => s.engine)
  const tone = useRoom((s) => s.toneRelease)
  return (
    <header className="flex h-9 shrink-0 items-center gap-5 text-[11px] font-bold tracking-[0.18em] uppercase">
      <span className="bg-agent px-2 py-1 text-background">spellspeak // tone</span>
      <span className="hidden text-muted-foreground sm:inline">the garage · after hours</span>
      <span className="ml-auto hidden items-center gap-2 text-muted-foreground md:flex">
        <span className="text-agent">audience {engine?.engine === "rules" ? "rules" : (engine?.release ?? "…")}</span>
        <span>·</span>
        <span className="text-active">tone {tone ?? "…"}</span>
      </span>
      <span className="flex items-center gap-2 text-active">
        <span className="animate-blink block size-2 bg-active" aria-hidden />
        live <Clock />
      </span>
      <PixelButton onClick={onLeave} color="var(--color-inactive)" title="End the session">
        <LogOut className="size-3.5" aria-hidden />
        leave
      </PixelButton>
    </header>
  )
}

/** The game: the cast on the left, the log, the scan, the timing and the prompt on the right. */
function Game({ onLeave }: { onLeave: () => void }) {
  return (
    <div className="scanlines flex min-h-svh flex-col gap-3 p-3 lg:h-svh">
      <TopBar onLeave={onLeave} />
      <main className="flex min-h-0 flex-1 flex-col gap-5 lg:flex-row">
        <div className="flex shrink-0 flex-col items-center gap-5 lg:w-[min(512px,42vw)]">
          {CAST.map((c) => (
            <CharacterCard key={c.id} c={c} />
          ))}
        </div>
        <div className="flex min-h-[36rem] min-w-0 flex-1 flex-col gap-3 lg:min-h-0">
          <Log />
          <Scan />
          <Timing />
          <Prompt />
        </div>
      </main>
      <CastAudio />
    </div>
  )
}

function Session({ onConnect, onDisconnect, error }: { onConnect: () => void; onDisconnect: () => void; error: string | null }) {
  const state = usePipecatClientTransportState()
  return (
    <>
      {state === "ready" ? <Game onLeave={onDisconnect} /> : <Boot onConnect={onConnect} error={error} />}
      <RoomSync />
    </>
  )
}

export default function App() {
  const [client, setClient] = useState<PipecatClient | null>(null)
  const [error, setError] = useState<string | null>(null)
  const starting = useRef(false) // one session at a time, however often "walk in" is pressed

  useEffect(() => {
    const c = new PipecatClient({ transport: new DailyTransport(), enableMic: true, enableCam: false })
    setClient(c)
    return () => {
      void c.disconnect().catch(() => {})
      setClient(null)
    }
  }, [])

  const connect = useCallback(async () => {
    if (!client || starting.current) return
    starting.current = true
    setError(null)
    try {
      await client.startBotAndConnect({
        endpoint: START_URL,
        requestData: { transport: "daily", createDailyRoom: true },
      })
    } catch (err) {
      setError(`couldn't start the session: ${err instanceof Error ? err.message : String(err)}`)
      await client.disconnect().catch(() => {})
    } finally {
      starting.current = false
    }
  }, [client])

  const disconnect = useCallback(async () => {
    if (!client) return
    await client.disconnect().catch(() => {})
  }, [client])

  if (!client) return null
  return (
    <PipecatClientProvider client={client}>
      <Session onConnect={() => void connect()} onDisconnect={() => void disconnect()} error={error} />
    </PipecatClientProvider>
  )
}
