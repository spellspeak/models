import { PipecatClient, RTVIEvent } from "@pipecat-ai/client-js"
import {
  PipecatClientAudio,
  PipecatClientProvider,
  usePipecatClient,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react"
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport"
import { useCallback, useEffect, useState } from "react"

import { CAST } from "@/cast"
import { ConnectScreen } from "@/components/connect-screen"
import { Reading } from "@/components/reading"
import { Scene } from "@/components/scene"
import { Seat } from "@/components/seat"
import { Transcript } from "@/components/transcript"
import { useRoom } from "@/store"
import type { ServerMessage } from "@/types"

/** The dev runner's WebRTC offer endpoint. A direct offer starts a session. */
const OFFER_URL = import.meta.env.VITE_BOT_OFFER_URL || "http://localhost:7860/api/offer"

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
      if (client && looking) client.sendClientMessage("look", { agent: looking })
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
      className="flex h-9 shrink-0 items-center gap-2 border border-border px-3"
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

function Session({
  onConnect,
  onDisconnect,
  error,
}: {
  onConnect: () => void
  onDisconnect: () => void
  error: string | null
}) {
  const state = usePipecatClientTransportState()
  const live = state === "ready"
  const phase =
    error || state === "error"
      ? "error"
      : live
        ? "live"
        : state === "disconnected" || state === "initialized"
          ? "idle"
          : "starting"
  const status = STATUS[phase]

  return (
    <div className="flex min-h-svh flex-col gap-5 p-3 text-[13px] leading-[1.6] sm:p-4">
      <header className="mx-auto flex min-h-9 w-full max-w-[1440px] shrink-0 items-center justify-between gap-3">
        <h1 className="flex flex-wrap items-center gap-x-2.5 text-sm sm:text-base">
          <span className="font-medium text-agent">Neon Yard</span>
          <span className="text-muted-foreground/60">/</span>
          <span className="font-medium text-agent">spellspeak audience</span>
        </h1>
        {live && (
          <button
            type="button"
            onClick={onDisconnect}
            className="border border-inactive/60 px-4 py-2 text-[13px] leading-none tracking-wider text-inactive uppercase transition-colors hover:bg-inactive/10"
          >
            Hang up
          </button>
        )}
      </header>

      {!live && <ConnectScreen onConnect={onConnect} error={error} />}
      <main className={`mx-auto grid w-full max-w-[1440px] flex-1 items-start gap-6 lg:grid-cols-[1.3fr_1fr] ${live ? "" : "hidden"}`}>
        <div className="min-w-0 space-y-6">
          <Scene />
          <div className="grid min-w-0 grid-cols-1 gap-5 sm:grid-cols-2">
            {CAST.map((c) => (
              <Seat key={c.id} agent={c} />
            ))}
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-5 lg:sticky lg:top-4">
          <Reading />
          <Transcript />
          <TextLine />
        </div>
      </main>

      <footer className="mx-auto flex h-6 w-full max-w-[1440px] shrink-0 items-center text-[13px] font-medium">
        <span className={status.tone}>
          <span className="mr-1.5">▸▸</span>
          {status.label}
        </span>
      </footer>

      <PipecatClientAudio />
      <RoomSync />
    </div>
  )
}

export default function App() {
  const [client, setClient] = useState<PipecatClient | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const c = new PipecatClient({
      transport: new SmallWebRTCTransport({ webrtcRequestParams: { endpoint: OFFER_URL } }),
      enableMic: true,
      enableCam: false,
    })
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
      await client.connect()
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
