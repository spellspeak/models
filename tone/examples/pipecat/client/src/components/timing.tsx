import { motion } from "motion/react"

import { USER, colorOf, labelOf } from "@/cast"
import { Panel } from "@/components/panel"
import { useRoom } from "@/store"

/** How many lines the chart shows. */
const BARS = 40
/** The chart's height in ms, at least: a line read in 10 ms fills half of it. */
const FLOOR_MS = 20

function stat(label: string, value: string, color?: string) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] leading-none font-bold tracking-[0.2em] text-muted-foreground uppercase">{label}</span>
      <span className="text-[18px] leading-none font-extrabold tabular-nums" style={{ color }}>
        {value}
      </span>
    </div>
  )
}

function ms(v: number | undefined): string {
  return v === undefined ? "—" : v.toFixed(1)
}

/**
 * How long Tone took over each line, in ms on the CPU: the last, the average and the slowest, and a
 * bar per line, coloured by who said it. Audience's time for the user's lines is beside it.
 */
export function Timing() {
  const timings = useRoom((s) => s.timings)
  const tone = timings.map((t) => t.tone)
  const audience = timings.flatMap((t) => (t.audience === null ? [] : [t.audience]))
  const last = timings.at(-1)
  const avg = tone.length ? tone.reduce((a, b) => a + b, 0) / tone.length : undefined
  const max = tone.length ? Math.max(...tone) : undefined
  const avgAudience = audience.length ? audience.reduce((a, b) => a + b, 0) / audience.length : undefined
  const scale = Math.max(FLOOR_MS, max ?? 0)
  const shown = timings.slice(-BARS)

  return (
    <Panel title="tone · ms per line" right={<span className="text-muted-foreground normal-case">on the cpu</span>} className="shrink-0" bodyClassName="px-3 pt-2.5 pb-2">
      <div className="flex items-end gap-6">
        {stat("last", ms(last?.tone), last ? colorOf(last.speaker) : undefined)}
        {stat("avg", ms(avg))}
        {stat("max", ms(max))}
        {stat("lines", String(tone.length))}
        <div className="ml-auto text-right">{stat("audience avg", ms(avgAudience), "var(--color-agent)")}</div>
      </div>
      <div className="relative mt-2.5 flex h-14 items-end gap-[2px] border-b-2 border-border" aria-label="Tone's time for each line">
        <span className="pointer-events-none absolute top-0 right-0 text-[9px] leading-none text-muted-foreground/60 tabular-nums">{scale.toFixed(0)} ms</span>
        {shown.length === 0 && <span className="self-center text-[11px] text-muted-foreground/60">a bar for every line, as it's read</span>}
        {shown.map((t, i) => (
          <motion.span
            key={t.line}
            title={`${labelOf(t.speaker)}: tone ${t.tone.toFixed(1)} ms${t.audience !== null ? `, audience ${t.audience.toFixed(1)} ms` : ""}`}
            className="block w-[7px] shrink-0 origin-bottom"
            style={{
              height: `${Math.max(4, (t.tone / scale) * 100)}%`,
              background: t.speaker === USER ? "var(--color-client)" : colorOf(t.speaker),
              opacity: i === shown.length - 1 ? 1 : 0.55,
            }}
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 22 }}
          />
        ))}
      </div>
    </Panel>
  )
}
