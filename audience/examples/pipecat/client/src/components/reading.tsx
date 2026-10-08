import { ArrowRight, Timer } from "lucide-react"

import { BY_ID, CAST, labelOf } from "@/cast"
import { Meter, percent } from "@/components/meter"
import { Panel } from "@/components/panel"
import { useRoom } from "@/store"
import type { AudienceMessage } from "@/types"

function Row({ label, p, color, dim }: { label: string; p: number | null; color: string; dim: boolean }) {
  return (
    <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_2.5rem] items-center gap-2 sm:grid-cols-[6rem_minmax(0,1fr)_3rem] sm:gap-3">
      <span style={{ color }}>{label}</span>
      <span className="text-[11px] sm:text-[13px]">
        <Meter p={p ?? 0} color={color} cells={20} dim={dim} />
      </span>
      <span className="text-right tabular-nums text-muted-foreground">{percent(p)}</span>
    </div>
  )
}

/** What the route made of a whole turn. */
function routeText(m: AudienceMessage): string {
  const r = m.route
  if (!r) return ""
  const who = r.speakers.map((s) => labelOf(s)).join(", ")
  if (r.kind === "group") return `everyone, in turn: ${who}`
  if (r.kind === "unclear") return `unclear: ${who} asks "who, me?"`
  if (r.reason === "fallback") return `${who} (not sure: whoever you spoke with last)`
  return who
}

/** Audience's reading: who your line is for, as you speak it, and who answered your last turn. */
export function Reading() {
  const engine = useRoom((s) => s.engine)
  const reading = useRoom((s) => s.reading)
  const routed = useRoom((s) => s.routed)
  const looking = useRoom((s) => s.looking)
  const dim = reading !== null && !reading.final

  return (
    <Panel
      title="who is it for · spellspeak audience"
      status={
        engine && (
          <span className={engine.engine === "model" ? "text-active" : "text-tool"}>
            {engine.engine === "model" ? `model ${engine.release}` : "rules baseline"}
          </span>
        )
      }
      footnote={
        reading && (
          <span className="flex items-center gap-1 tabular-nums">
            <Timer className="size-3" aria-hidden />
            {reading.ms} ms
          </span>
        )
      }
      className="shrink-0 space-y-3 px-4 pt-5 pb-5"
    >
      {engine?.error && (
        <p className="text-tool" title={engine.error}>
          no model files: routing with the rules
        </p>
      )}
      <p className="min-h-6 text-foreground">
        {reading ? (
          <>
            “{reading.heard}
            {reading.final ? "”" : "…"}
          </>
        ) : (
          <span className="text-muted-foreground/60">Say something, to one of them or to everyone.</span>
        )}
      </p>

      <div className="space-y-0.5">
        {CAST.map((c) => (
          <Row key={c.id} label={c.name.toLowerCase()} p={reading?.addressed[c.id] ?? null} color={c.color} dim={dim} />
        ))}
      </div>
      <div className="space-y-0.5 border-t border-border pt-3">
        <Row label="everyone" p={reading?.to_group ?? null} color="var(--color-agent)" dim={dim} />
        <Row label="unclear" p={reading?.unclear ?? null} color="var(--color-tool)" dim={dim} />
      </div>

      <div className="space-y-1 border-t border-border pt-3 text-muted-foreground">
        <p className="flex items-center gap-2">
          <ArrowRight className="size-3.5 text-agent" aria-hidden />
          <span className="text-muted-foreground/70">last turn went to</span>
          <span className="text-foreground">{routed ? routeText(routed) : "—"}</span>
        </p>
        <p className="text-muted-foreground/70">
          looking at{" "}
          <span style={{ color: looking ? BY_ID[looking]?.color : undefined }}>
            {looking ? labelOf(looking) : "nobody in particular"}
          </span>
        </p>
      </div>
    </Panel>
  )
}
