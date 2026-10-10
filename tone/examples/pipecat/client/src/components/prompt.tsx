import { usePipecatClient, usePipecatClientMicControl } from "@pipecat-ai/client-react"
import { Mic, MicOff } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { useRoom } from "@/store"

/**
 * The command line: type a line and press return, or just talk. While you speak, what's heard so
 * far is written into it, as if typed. The microphone can be turned off here.
 */
export function Prompt() {
  const client = usePipecatClient()
  const { enableMic, isMicEnabled } = usePipecatClientMicControl()
  const speaking = useRoom((s) => s.userSpeaking)
  const heard = useRoom((s) => [...s.heardFinals, s.heardInterim].join(" ").trim())
  const [text, setText] = useState("")
  const input = useRef<HTMLInputElement>(null)

  // Typing anywhere goes to the prompt.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.key.length !== 1) return
      if (document.activeElement !== input.current) input.current?.focus()
    }
    window.addEventListener("keydown", onKey)
    input.current?.focus()
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const send = () => {
    const line = text.trim()
    if (!line || !client) return
    setText("")
    // As a finished turn, straight in (server/bot.py, `say`).
    client.sendClientMessage("say", { text: line })
  }

  const listening = speaking && heard
  return (
    <form
      className="frame flex h-11 shrink-0 items-center gap-3 bg-card pr-1.5 pl-3"
      style={{ ["--frame" as string]: speaking ? "var(--color-client)" : "var(--color-border)" }}
      onSubmit={(e) => {
        e.preventDefault()
        send()
      }}
    >
      <span className="text-[15px] font-bold text-client">&gt;</span>
      {listening ? (
        <span className="min-w-0 flex-1 truncate text-[14px] text-client">
          {heard}
          <span className="animate-blink">█</span>
        </span>
      ) : (
        <input
          ref={input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={isMicEnabled ? "talk, or type a line and press return" : "type a line and press return"}
          aria-label="Say something"
          className="min-w-0 flex-1 bg-transparent text-[14px] text-foreground caret-client outline-none placeholder:text-muted-foreground/50"
        />
      )}
      <button
        type="button"
        onClick={() => enableMic(!isMicEnabled)}
        title={isMicEnabled ? "Turn the microphone off" : "Turn the microphone on"}
        className="frame flex h-8 items-center gap-2 px-2.5 text-[11px] font-bold tracking-[0.16em] uppercase hover:bg-[var(--frame)] hover:text-background"
        style={{
          ["--frame" as string]: isMicEnabled ? (speaking ? "var(--color-client)" : "var(--color-active)") : "var(--color-muted-foreground)",
          color: isMicEnabled ? (speaking ? "var(--color-client)" : "var(--color-active)") : "var(--color-muted-foreground)",
        }}
      >
        {isMicEnabled ? <Mic className="size-3.5" aria-hidden /> : <MicOff className="size-3.5" aria-hidden />}
        {isMicEnabled ? (speaking ? "hearing" : "mic on") : "mic off"}
      </button>
    </form>
  )
}
