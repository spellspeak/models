import { useMemo } from "react"

import { CAST, USER, colorOf, labelOf } from "@/cast"
import { Segments } from "@/components/segments"
import { useRoom } from "@/store"

/** Tone's sarcasm reading of one line: whether it's sarcastic, and how likely. */
interface Reading {
  sarcastic: boolean
  probability: number | null
}

/** One person's last line, as a vertical bar: how likely it was sarcastic, lit when Tone calls it sarcastic. */
function Bar({ who, reading }: { who: string; reading: Reading | null | undefined }) {
  const p = reading?.probability ?? null
  const on = Boolean(reading?.sarcastic)
  const pct = p === null ? null : Math.round(p * 100)
  const said = reading === undefined ? "nothing read yet" : reading === null ? "no sarcasm reading (Tone rc4 on)" : on ? "sarcastic" : "sincere"
  return (
    <div
      className="flex min-h-0 flex-col items-center gap-1.5"
      role="meter"
      aria-label={`${labelOf(who)}: sarcasm in the last line`}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct ?? undefined}
      aria-valuetext={pct === null ? said : `${pct}%, ${said}`}
      title={pct === null ? said : `${said}: ${pct}% likely sarcastic`}
    >
      <span
        className="text-[13px] font-bold tabular-nums"
        style={{ color: on ? "var(--color-sarcasm)" : "var(--color-muted-foreground)" }}
      >
        {pct === null ? "—" : `${pct}%`}
      </span>
      <div className="min-h-0 flex-1">
        <Segments p={p ?? 0} color={on ? "var(--color-sarcasm)" : "var(--color-neutral)"} count={20} gap={3} vertical fill width={22} />
      </div>
      <span className="text-[10px] font-bold tracking-[0.14em] uppercase" style={{ color: colorOf(who) }}>
        {labelOf(who)}
      </span>
    </div>
  )
}

/**
 * Beside the log, the log's full height: how sarcastic each person's last line was, as Tone read it (from
 * rc4): a bar and the percentage for you and for each character. Teal when Tone calls the line sarcastic.
 */
export function SarcasmMeters() {
  const lines = useRoom((s) => s.lines)
  const tones = useRoom((s) => s.tones)
  // The latest line each person said that Tone has read: its sarcasm reading, or null from a release without it.
  const latest = useMemo(() => {
    const out: Record<string, Reading | null> = {}
    for (let i = lines.length - 1; i >= 0; i--) {
      const l = lines[i]
      const t = tones[l.id]
      if (out[l.speaker] !== undefined || !t) continue
      out[l.speaker] = t.sarcasm ?? null
    }
    return out
  }, [lines, tones])

  return (
    <aside className="flex shrink-0 flex-col items-center border-l-2 border-border px-3 py-2" aria-label="Sarcasm in each person's last line">
      <span className="text-[10px] font-bold tracking-[0.2em] text-muted-foreground uppercase">sarcasm</span>
      <div className="mt-3 flex min-h-0 flex-1 gap-4">
        {[USER, ...CAST.map((c) => c.id)].map((who) => (
          <Bar key={who} who={who} reading={latest[who]} />
        ))}
      </div>
    </aside>
  )
}
