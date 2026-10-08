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

import { BY_ID } from "@/cast"
import { CharacterPanel } from "@/components/character-panel"
import { ConnectScreen } from "@/components/connect-screen"
import { Transcript } from "@/components/transcript"
import { useTable } from "@/store"
import type { LineMessage } from "@/types"

/** The dev runner's WebRTC offer endpoint. A direct offer starts a session. */
const OFFER_URL = import.meta.env.VITE_BOT_OFFER_URL || "http://localhost:7860/api/offer"

const STATUS: Record<string, { label: string; tone: string }> = {
  idle: { label: "session idle", tone: "text-muted-foreground" },
  starting: { label: "session starting", tone: "text-tool" },
  live: { label: "session live", tone: "text-active" },
  error: { label: "session error", tone: "text-inactive" },
}

/** RTVI events into the table's store: the bot's tagged lines, and your speech. */
function TableSync() {
  const table = useTable
  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback((data: unknown) => {
      const m = data as LineMessage
      if (m && m.type === "line") table.getState().receive(m)
    }, [])
  )
  useRTVIClientEvent(
    RTVIEvent.UserTranscript,
    useCallback((data: { text: string; final: boolean }) => {
      if (data.text.trim()) table.getState().hear(data.text, data.final)
    }, [])
  )
  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, useCallback(() => table.getState().setUserSpeaking(true), []))
  useRTVIClientEvent(RTVIEvent.UserStoppedSpeaking, useCallback(() => table.getState().setUserSpeaking(false), []))
  useRTVIClientEvent(RTVIEvent.BotStartedSpeaking, useCallback(() => table.getState().setBotSpeaking(true), []))
  useRTVIClientEvent(RTVIEvent.BotStoppedSpeaking, useCallback(() => table.getState().setBotSpeaking(false), []))
  useRTVIClientEvent(RTVIEvent.Connected, useCallback(() => table.getState().reset(), []))
  return null
}

/** Once the bot is ready: who you picked, and every heart as this browser remembers them. */
function Pick() {
  const client = usePipecatClient()
  useRTVIClientEvent(
    RTVIEvent.BotReady,
    useCallback(() => {
      const { picked, hearts } = useTable.getState()
      if (client && picked) client.sendClientMessage("pick", { character: picked, hearts })
    }, [client])
  )
  return null
}

/** Type a line instead of saying it: it goes through the same pipeline from the user context on. */
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
  const picked = useTable((s) => s.picked)
  const who = picked ? BY_ID[picked] : null

  return (
    <div className="flex h-svh flex-col gap-4 p-4 text-[13px] leading-[1.6]">
      <header className="flex h-9 shrink-0 items-center justify-between">
        <h1 className="flex items-center gap-2.5 text-base">
          <span className="font-medium text-agent">spellspeak tone</span>
          <span className="text-muted-foreground/60">/</span>
          <span className="text-muted-foreground/70">at the table</span>
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

      {!live && <ConnectScreen onConnect={onConnect} onDisconnect={onDisconnect} error={error} />}
      <main className={`grid min-h-0 flex-1 grid-cols-[1.2fr_1fr] gap-4 ${live ? "" : "hidden"}`}>
        <div className="flex min-h-0 min-w-0 flex-col">
          {who && <CharacterPanel character={who} />}
        </div>
        <div className="flex min-h-0 min-w-0 flex-col gap-4">
          <Transcript />
          <TextLine />
        </div>
      </main>

      <footer className="flex h-6 shrink-0 items-center text-[13px] font-medium">
        <span className={status.tone}>
          <span className="mr-1.5">▸▸</span>
          {status.label}
        </span>
      </footer>

      <PipecatClientAudio />
      <TableSync />
      <Pick />
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
