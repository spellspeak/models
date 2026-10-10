import { CAST, USER, colorOf, labelOf } from "@/cast"
import { Panel } from "@/components/panel"
import { Segments } from "@/components/segments"
import { SENTIMENT_COLOR, actSentiment, emotionSentiment } from "@/sentiment"
import { useRoom } from "@/store"

function percent(p: number | null | undefined): string {
  return p === null || p === undefined ? "—" : `${Math.round(p * 100)}%`
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[5.5rem_1fr] items-center gap-x-3 py-[3px]">
      <span className="text-[10px] font-bold tracking-[0.2em] text-muted-foreground uppercase">{label}</span>
      <div className="flex min-w-0 items-center gap-3">{children}</div>
    </div>
  )
}

/**
 * The latest line, as the models read it: who it was for (Audience, for yours), how it sounded and
 * what it did to each person (Tone), and whose feelings it moved.
 */
export function Scan() {
  const tone = useRoom((s) => s.lastTone)
  const reading = useRoom((s) => s.reading)
  const line = useRoom((s) => (tone ? s.lines.find((l) => l.id === tone.line) : undefined))

  const partial = reading && !reading.final
  const acts = tone ? Object.entries(tone.acts).filter(([who]) => who !== tone.speaker) : []

  return (
    <Panel title="scan" right={tone && <span className="text-muted-foreground normal-case">last line</span>} className="shrink-0" bodyClassName="px-3 py-2">
      {partial ? (
        <Row label="hearing">
          <span className="truncate text-[13px] text-client">
            {reading.heard}
            <span className="animate-blink">_</span>
          </span>
        </Row>
      ) : tone ? (
        <>
          <Row label="line">
            <span className="truncate text-[13px]">
              <span className="font-bold uppercase" style={{ color: colorOf(tone.speaker) }}>
                {labelOf(tone.speaker)}
              </span>
              <span className="text-muted-foreground"> → {tone.to ? labelOf(tone.to) : "the room"} </span>
              <span className="text-foreground/80">“{line?.text ?? "…"}”</span>
            </span>
          </Row>
          {tone.speaker === USER && reading?.final && (
            <Row label="audience">
              {CAST.map((c) => (
                <span key={c.id} className="flex items-center gap-2 text-[12px]">
                  <span style={{ color: c.color }}>to {c.name.toLowerCase()}</span>
                  <Segments p={reading.addressed[c.id] ?? 0} color={c.color} count={10} size={6} />
                  <span className="tabular-nums text-muted-foreground">{percent(reading.addressed[c.id])}</span>
                </span>
              ))}
            </Row>
          )}
          <Row label="emotion">
            <span className="w-44 shrink-0 truncate text-[13px] font-bold uppercase" style={{ color: SENTIMENT_COLOR[emotionSentiment(tone.emotion.label)] }}>
              {tone.backchannel ? "listening" : tone.emotion.label}
              {tone.emotion.label !== "neutral" && <span className="font-normal text-muted-foreground lowercase"> {tone.emotion.intensity}</span>}
            </span>
            <Segments p={tone.emotion.confidence ?? 0} color={SENTIMENT_COLOR[emotionSentiment(tone.emotion.label)]} count={10} size={6} />
            <span className="text-[12px] tabular-nums text-muted-foreground">{percent(tone.emotion.confidence)}</span>
          </Row>
          {acts.map(([who, a]) => {
            const color = SENTIMENT_COLOR[actSentiment(a.act, a.hostile)]
            return (
              <Row key={who} label={`act → ${labelOf(who)}`}>
                <span className="w-44 shrink-0 truncate text-[13px] font-bold uppercase" style={{ color: a.act === "none" ? "var(--color-muted-foreground)" : color }}>
                  {a.act}
                  {a.act !== "none" && <span className="font-normal text-muted-foreground lowercase"> {a.intensity}</span>}
                </span>
                <Segments p={a.confidence ?? 0} color={a.act === "none" ? "var(--color-neutral)" : color} count={10} size={6} />
                <span className="text-[12px] tabular-nums text-muted-foreground">{percent(a.confidence)}</span>
              </Row>
            )
          })}
          <Row label="effect">
            {tone.changes.length === 0 ? (
              <span className="text-[12px] text-muted-foreground">no feelings moved</span>
            ) : (
              tone.changes.map((c) => (
                <span key={`${c.from}:${c.toward}`} className="text-[13px]">
                  <span style={{ color: colorOf(c.from) }}>{labelOf(c.from)}</span>
                  <span className="text-muted-foreground"> about {labelOf(c.toward)} </span>
                  <span className="font-bold tabular-nums" style={{ color: c.change > 0 ? "var(--color-warm)" : "var(--color-hostile)" }}>
                    {c.change > 0 ? `+${c.change}` : `−${-c.change}`}
                  </span>
                  <span className="text-muted-foreground tabular-nums"> → {c.value}</span>
                </span>
              ))
            )}
          </Row>
        </>
      ) : (
        <p className="py-1 text-[12px] text-muted-foreground/70">nothing read yet</p>
      )}
    </Panel>
  )
}
