import { Mic, Timer, User } from "lucide-react"
import { useEffect, useRef } from "react"

import { Panel } from "@/components/panel"
import { ActRow, EmotionRow, HeartDelta } from "@/components/reading"
import { PLAYER, colorOf, labelOf } from "@/cast"
import { useTable } from "@/store"
import type { LineMessage } from "@/types"

/** One line as a block: who said it to whom, the words, then Tone's reading of it. */
function Block({ line }: { line: LineMessage }) {
  const you = line.speaker === PLAYER
  const color = colorOf(line.speaker)
  const change = Object.values(line.changes)[0]
  return (
    <article className="min-w-0 overflow-hidden border border-border" style={{ borderLeftWidth: 3, borderLeftColor: color }}>
      <header className="flex items-center gap-2 border-b border-border px-3 py-1.5 text-muted-foreground">
        {you ? <User className="size-3.5 shrink-0" style={{ color }} aria-hidden /> : <Mic className="size-3.5 shrink-0" style={{ color }} aria-hidden />}
        <span style={{ color }}>{labelOf(line.speaker)}</span>
        {line.to && <span>→ {labelOf(line.to)}</span>}
        <span className="ml-auto flex items-center gap-1 tabular-nums text-muted-foreground/70">
          <Timer className="size-3" aria-hidden />
          {line.latency_ms} ms
        </span>
      </header>
      <p className="px-3 py-2 text-foreground">“{line.text}”</p>
      <div className="space-y-1 border-t border-border bg-muted/40 px-3 py-2">
        <EmotionRow
          label={line.emotion.label}
          intensity={line.emotion.intensity}
          confidence={line.emotion.confidence}
          backchannel={line.backchannel}
        />
        {Object.entries(line.acts).map(([to, tag]) => (
          <ActRow key={to} to={labelOf(to).toLowerCase()} tag={tag} />
        ))}
        {change !== undefined && change !== 0 && (
          <div className="pt-1">
            <HeartDelta change={change} />
          </div>
        )}
      </div>
    </article>
  )
}

/** Every line as it was tagged, newest at the bottom, plus what you are saying now. */
export function Transcript() {
  const lines = useTable((s) => s.lines)
  const heard = useTable((s) => [...s.heardFinals, s.heardInterim].join(" ").trim())
  const userSpeaking = useTable((s) => s.userSpeaking)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" })
  }, [lines.length, heard])

  return (
    <Panel
      title="what tone heard"
      status={<span className="text-muted-foreground">{lines.length} lines</span>}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 pt-5 pb-4 text-[13px] leading-[1.6]">
        {lines.length === 0 && !heard && (
          <p className="text-muted-foreground/60">
            Say hello. Every line, yours and theirs, is read by Tone: how it sounded, and what it did
            to the other person.
          </p>
        )}
        {lines.map((l) => (
          <Block key={l.id} line={l} />
        ))}
        {heard && (
          <p className="flex items-center gap-2 text-muted-foreground">
            <User className="size-3.5 text-client" aria-hidden />
            <span className={userSpeaking ? "text-active" : "text-client"}>{userSpeaking ? "● " : ""}</span>
            {heard}
          </p>
        )}
        <div ref={end} />
      </div>
    </Panel>
  )
}
