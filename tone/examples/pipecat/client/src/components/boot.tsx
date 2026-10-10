import { usePipecatClientTransportState } from "@pipecat-ai/client-react"
import { CornerDownLeft } from "lucide-react"
import { motion, useReducedMotion } from "motion/react"
import { useEffect, useState } from "react"

import { CAST, USER, faceImages } from "@/cast"
import { PixelButton } from "@/components/panel"
import { preload } from "@/preload"
import { feelingWord } from "@/sentiment"

/** Every face the game shows: one sheet a character. */
const IMAGES = faceImages()

const DIALING: Record<string, string> = {
  initializing: "starting up",
  initialized: "starting up",
  authenticating: "asking for a room",
  authenticated: "room found",
  connecting: "dialing the garage",
  connected: "waiting for the cast",
  disconnecting: "hanging up",
}

function Step({ label, value, ok, i }: { label: string; value: React.ReactNode; ok?: boolean | null; i: number }) {
  const reduce = useReducedMotion()
  return (
    <motion.p
      className="grid grid-cols-[1.25rem_8.5rem_1fr_3rem] items-baseline text-[13px] leading-[1.9]"
      initial={reduce ? false : { opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: reduce ? 0 : 0.12 + i * 0.09, duration: 0.12, ease: "linear" }}
    >
      <span className="text-muted-foreground">&gt;</span>
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate text-foreground">{value}</span>
      <span className={`text-right font-bold ${ok === false ? "text-hostile" : ok ? "text-active" : "text-muted-foreground"}`}>
        {ok === null || ok === undefined ? "" : ok ? "[ok]" : "[..]"}
      </span>
    </motion.p>
  )
}

/**
 * The title screen: the cast's faces load (every one decoded before the game shows, so moods never
 * flicker), then you walk in. While the session starts, it says what it's doing.
 */
export function Boot({ onConnect, error }: { onConnect: () => void; error: string | null }) {
  const state = usePipecatClientTransportState()
  const [loaded, setLoaded] = useState(0)
  const ready = loaded >= IMAGES.length
  const dialing = DIALING[state]

  useEffect(() => {
    void preload(IMAGES, setLoaded)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // A focused button already takes Enter as a click.
      if (e.key !== "Enter" || e.repeat || document.activeElement instanceof HTMLButtonElement) return
      if (ready && !dialing) onConnect()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [ready, dialing, onConnect])

  const sheets = CAST.filter((c) => c.sheet).length
  return (
    <div className="scanlines flex min-h-svh items-center justify-center p-6">
      <div className="frame-thick w-full max-w-2xl bg-card" style={{ ["--frame" as string]: "var(--color-agent)" }}>
        <header className="flex h-7 items-center justify-between bg-agent px-3 text-[11px] font-bold tracking-[0.2em] text-background uppercase">
          <span>spellspeak // tone</span>
          <span>pipecat</span>
        </header>
        <div className="px-7 pt-7 pb-6">
          <h1 className="shadow-px text-[44px] leading-[0.95] font-extrabold tracking-tight text-foreground uppercase">
            the garage,
            <br />
            <span className="text-tool">after hours</span>
          </h1>
          <p className="mt-4 max-w-lg text-[13px] leading-[1.6] text-muted-foreground">
            {CAST.map((c) => c.name).join(", ")} {CAST.length === 1 ? "is" : "are"} here, and already {CAST.length === 1 ? "feels" : "feel"} something about you. Say anything:
            Tone reads every line in about ten milliseconds, and how they feel moves with it. Watch the face, hear the voice.
          </p>

          <div className="mt-6 border-t-2 border-border pt-3">
            <Step i={0} label="faces" value={`${loaded}/${IMAGES.length} ${sheets ? `sheets, ${sheets * 9} moods` : "portraits"}`} ok={ready ? true : false} />
            {CAST.map((c, i) => (
              <Step
                key={c.id}
                i={i + 1}
                label={c.name.toLowerCase()}
                value={
                  <>
                    <span style={{ color: c.color }}>{c.role.toLowerCase()}</span>
                    <span className="text-muted-foreground"> · {feelingWord(c.feelings[USER] ?? 50)} toward you · voice {c.voiceName.toLowerCase()}</span>
                  </>
                }
              />
            ))}
            <Step i={CAST.length + 1} label="models" value="audience rc2.1 · tone rc2.1 · eleven v4 turbo" />
            <Step i={CAST.length + 2} label="microphone" value="asked for when you walk in, or just type" />
            {dialing && <Step i={0} label="session" value={<span className="text-client">{dialing}<span className="animate-blink">_</span></span>} ok={false} />}
            {error && <Step i={0} label="error" value={<span className="text-hostile">{error}</span>} ok={false} />}
          </div>

          <div className="mt-6 flex items-center gap-4">
            <PixelButton onClick={onConnect} disabled={!ready || Boolean(dialing)} color="var(--color-tool)" className="h-10 px-6 text-[13px]">
              {dialing ? "walking in" : "walk in"}
            </PixelButton>
            {!dialing && ready && (
              <span className="flex items-center gap-1.5 text-[11px] tracking-[0.16em] text-muted-foreground uppercase">
                or press <CornerDownLeft className="size-3.5" aria-hidden /> enter
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
