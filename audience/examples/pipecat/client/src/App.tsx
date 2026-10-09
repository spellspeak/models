import { PipecatClient, RTVIEvent } from "@pipecat-ai/client-js"
import {
  PipecatClientProvider,
  usePipecatClient,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react"
import { DailyTransport } from "@pipecat-ai/daily-transport"
import { useCallback, useEffect, useState } from "react"

import { CastAudio } from "@/components/cast-audio"
import { Readout } from "@/components/readout"
import { Blips, Scene, Strip } from "@/components/scene"
import { Transcript } from "@/components/transcript"
import { useRoom } from "@/store"
import type { ServerMessage } from "@/types"

/**
 * Where a session starts: the Pipecat dev runner's /start (`cd server && uv run bot.py -t daily`).
 * It makes a Daily room, starts the bot in it, and answers with the room's URL and a token.
 */
const START_URL = import.meta.env.VITE_BOT_START_URL || "http://localhost:7860/start"

const BUSY = ["initializing", "authenticating", "authenticated", "connecting", "disconnecting"]

const STATUS: Record<string, { label: string; tone: string }> = {
  idle: { label: "session idle", tone: "text-muted-foreground" },
  starting: { label: "session starting", tone: "text-tool" },
  live: { label: "session live", tone: "text-active" },
  error: { label: "session error", tone: "text-inactive" },
}

/** RTVI events into the room's store: the bot's server messages, and your speech. */
function RoomSync() {
  const client = usePipecatClient()
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
  // Who you were looking at before connecting carries into the session.
  useRTVIClientEvent(
    RTVIEvent.BotReady,
    useCallback(() => {
      const { looking } = useRoom.getState()
      if (client && looking) client.sendClientMessage("look", { character: looking })
    }, [client])
  )
  return null
}

/** Type a line instead of saying it: it's routed the same way. */
function TextLine() {
  const client = usePipecatClient()
  const [text, setText] = useState("")
  const send = async () => {
    const line = text.trim()
    if (!line || !client) return
    setText("")
    await client.sendText(line)
  }
  return (
    <form
      className="flex h-9 shrink-0 items-center gap-2 border border-border px-3 text-[12px]"
      onSubmit={(e) => {
        e.preventDefault()
        void send()
      }}
    >
      <span className="text-client">❯</span>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="or type a line and press return"
        className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground/50"
      />
    </form>
  )
}

/** Before a session: the scene at rest, and the way in. */
function Enter({ onConnect, error }: { onConnect: () => void; error: string | null }) {
  const state = usePipecatClientTransportState()
  const busy = BUSY.includes(state)
  return (
    <div className="absolute inset-0 flex items-end justify-center bg-black/55 p-6 pb-28">
      <div className="max-w-md space-y-4 border border-border bg-black/80 px-6 py-5 text-[12px] leading-[1.6]">
        <p className="text-[11px] tracking-widest text-agent uppercase">spellspeak audience · pipecat</p>
        <h2 className="text-lg text-foreground">Four in a garage, one of you.</h2>
        <p className="text-muted-foreground">
          Talk to one of them by name or by what you can see, to a couple of them, to everyone, or to
          nobody in particular. Audience works out who each turn is for before anyone answers. Click
          someone to look at them.
        </p>
        <p className="text-muted-foreground/70">
          try “bruno, can you fix my bike?” · “you in the orange suit…” · “hey, all of you!” · “oi, you!”
        </p>
        <button
          type="button"
          onClick={onConnect}
          disabled={busy}
          className="border border-active/60 px-5 py-2 leading-none tracking-wider text-active uppercase transition-colors hover:bg-active/10 disabled:opacity-60"
        >
          {busy ? "connecting…" : "walk in"}
        </button>
        {error && <p className="text-inactive">{error}</p>}
      </div>
    </div>
  )
}

function Session({ onConnect, onDisconnect, error }: { onConnect: () => void; onDisconnect: () => void; error: string | null }) {
  const state = usePipecatClientTransportState()
  const live = state === "ready"
  const phase =
    error || state === "error" ? "error" : live ? "live" : state === "disconnected" || state === "initialized" ? "idle" : "starting"
  const status = STATUS[phase]

  return (
    <div className="flex h-svh flex-col gap-3 p-3 text-[13px] leading-[1.6]">
      <main className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto lg:flex-row lg:overflow-visible">
        <Scene>
          {live ? (
            <>
              <Blips />
              <Strip />
            </>
          ) : (
            <Enter onConnect={onConnect} error={error} />
          )}
        </Scene>
        <aside className="flex min-h-[26rem] w-full shrink-0 flex-col gap-3 lg:min-h-0 lg:w-[360px]">
          <Readout />
          <Transcript />
          <TextLine />
        </aside>
      </main>

      <footer className="flex h-7 shrink-0 items-center justify-between text-[12px] font-medium">
        <span className={status.tone}>
          <span className="mr-1.5">▸▸</span>
          {status.label}
        </span>
        {live && (
          <button
            type="button"
            onClick={onDisconnect}
            className="border border-inactive/60 px-3 py-1.5 text-[12px] leading-none tracking-wider text-inactive uppercase transition-colors hover:bg-inactive/10"
          >
            Leave
          </button>
        )}
      </footer>

      <CastAudio />
      <RoomSync />
    </div>
  )
}

export default function App() {
  const [client, setClient] = useState<PipecatClient | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const c = new PipecatClient({ transport: new DailyTransport(), enableMic: true, enableCam: false })
    setClient(c)
    return () => {
      void c.disconnect().catch(() => {})
      setClient(null)
    }
  }, [])

  const connect = useCallback(async () => {
    if (!client) return
    setError(null)
    try {
      await client.startBotAndConnect({
        endpoint: START_URL,
        requestData: { transport: "daily", createDailyRoom: true },
      })
    } catch (err) {
      setError(`Failed to start session: ${err instanceof Error ? err.message : String(err)}`)
      await client.disconnect().catch(() => {})
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
