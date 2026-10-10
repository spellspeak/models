import { useReducedMotion } from "motion/react"
import { useEffect, useRef, useState } from "react"
import { useShallow } from "zustand/react/shallow"

import { BY_ID, USER, colorOf, labelOf } from "@/cast"
import { Panel } from "@/components/panel"
import { SENTIMENT_COLOR, actSentiment, emotionSentiment } from "@/sentiment"
import { type Line, type ToneReading, useRoom } from "@/store"

/** About how fast a voice speaks, in characters a second: a line types out as it's heard. */
const SPOKEN_CPS = 17

/** Text that types itself out, at the pace it's spoken. A line that grows (cut short, then fixed) carries on. */
function Typed({ text, cps }: { text: string; cps: number }) {
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(reduce ? text.length : 0)
  useEffect(() => {
    if (reduce) {
      setShown(text.length)
      return
    }
    const id = setInterval(() => setShown((n) => (n >= text.length ? n : n + 1)), 1000 / cps)
    return () => clearInterval(id)
  }, [text, cps, reduce])
  const done = shown >= text.length
  return (
    <>
      {text.slice(0, shown)}
      {!done && <span className="animate-blink">█</span>}
    </>
  )
}

function clock(ms: number): string {
  const d = new Date(ms)
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":")
}

/** Under a line: how Tone read it, and how long it took. */
function ToneLine({ tone }: { tone: ToneReading | undefined }) {
  if (!tone) return null
  const acts = Object.entries(tone.acts).filter(([, a]) => a.act !== "none")
  const e = tone.emotion
  return (
    <p className="mt-0.5 text-[11px] leading-[1.5] text-muted-foreground">
      <span className="text-muted-foreground/60">└ tone </span>
      <span style={{ color: e.label === "neutral" ? undefined : SENTIMENT_COLOR[emotionSentiment(e.label)] }}>
        {e.label}
        {e.label !== "neutral" && <span className="text-muted-foreground/70"> {e.intensity}</span>}
      </span>
      {acts.map(([who, a]) => (
        <span key={who}>
          <span className="text-muted-foreground/50"> · </span>
          <span style={{ color: SENTIMENT_COLOR[actSentiment(a.act, a.hostile)] }}>{a.act}</span>
          <span className="text-muted-foreground/70"> → {labelOf(who).toLowerCase()}</span>
        </span>
      ))}
      {tone.changes.map((c) => (
        <span key={`${c.from}:${c.toward}`}>
          <span className="text-muted-foreground/50"> · </span>
          <span style={{ color: c.change > 0 ? "var(--color-warm)" : "var(--color-hostile)" }}>
            {labelOf(c.from).toLowerCase()} {c.change > 0 ? `+${c.change}` : `−${-c.change}`}
          </span>
        </span>
      ))}
      <span className="text-muted-foreground/50"> · {tone.ms.toFixed(1)} ms</span>
    </p>
  )
}

function Entry({ line, tone, fresh }: { line: Line; tone: ToneReading | undefined; fresh: boolean }) {
  const you = line.speaker === USER
  return (
    <div className="grid grid-cols-[4.25rem_3.25rem_1fr] gap-x-2 py-1 text-[13px] leading-[1.55]">
      <span className="pt-px text-[11px] text-muted-foreground/60 tabular-nums">{clock(line.at)}</span>
      <span className="font-bold tracking-[0.1em] uppercase" style={{ color: colorOf(line.speaker) }}>
        {labelOf(line.speaker)}
      </span>
      <div className="min-w-0">
        <p className={you ? "text-client" : "text-foreground"}>
          {you && <span className="text-muted-foreground">&gt; </span>}
          {!you && fresh ? <Typed text={line.text} cps={SPOKEN_CPS} /> : line.text}
          {line.interrupted && <span className="text-muted-foreground"> [cut off]</span>}
        </p>
        <ToneLine tone={tone} />
      </div>
    </div>
  )
}

/** The conversation, as a terminal log: each line, who said it, and Tone's reading under it. */
export function Log() {
  const lines = useRoom((s) => s.lines)
  const tones = useRoom((s) => s.tones)
  const thinking = useRoom(useShallow((s) => Object.keys(s.thinking)))
  const scroll = useRef<HTMLDivElement>(null)
  // Lines already on screen when the log first drew are shown whole; new ones type out.
  const [since] = useState(() => Date.now())

  useEffect(() => {
    const el = scroll.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines, tones, thinking.length])

  return (
    <Panel title="log" right={<span className="text-muted-foreground">{lines.length} lines</span>} className="min-h-0 flex-1" bodyClassName="flex flex-col">
      <div ref={scroll} className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {lines.length === 0 && (
          <p className="py-1 text-[12px] text-muted-foreground/70">
            the garage is quiet. say something, or type it below<span className="animate-blink">_</span>
          </p>
        )}
        {lines.map((l) => (
          <Entry key={l.id} line={l} tone={tones[l.id]} fresh={l.at >= since} />
        ))}
        {thinking.map((id) => (
          <div key={id} className="grid grid-cols-[4.25rem_3.25rem_1fr] gap-x-2 py-1 text-[13px] leading-[1.55]">
            <span />
            <span className="font-bold tracking-[0.1em] uppercase" style={{ color: BY_ID[id]?.color }}>
              {labelOf(id)}
            </span>
            <span className="animate-blink text-muted-foreground">█</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}
