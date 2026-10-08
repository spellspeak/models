import { usePipecatClient, VoiceVisualizer } from "@pipecat-ai/client-react"
import { Eye, EyeOff } from "lucide-react"

import type { Agent } from "@/cast"
import { Meter, percent } from "@/components/meter"
import { Panel } from "@/components/panel"
import { useRoom } from "@/store"

/**
 * One character in the yard: what you can see of them (their card, as Audience reads it), the chance
 * your line is for them, and whether it's their turn. Look at them and Audience is told so.
 */
export function Seat({ agent }: { agent: Agent }) {
  const client = usePipecatClient()
  const speaking = useRoom((s) => s.speaking === agent.id)
  const thinking = useRoom((s) => s.active === agent.id && s.speaking !== agent.id)
  const looking = useRoom((s) => s.looking === agent.id)
  const p = useRoom((s) => s.reading?.addressed[agent.id] ?? null)
  const partial = useRoom((s) => s.reading !== null && !s.reading.final)
  const name = agent.name.toLowerCase()

  const toggleLook = () => {
    const next = looking ? null : agent.id
    useRoom.getState().look(next)
    client?.sendClientMessage("look", { agent: next })
  }

  return (
    <Panel
      title={`${name} · ${agent.role.toLowerCase()}`}
      titleColor={speaking || looking ? agent.color : undefined}
      status={
        <span className="text-muted-foreground">
          <span className={speaking ? "mr-1.5 text-active" : thinking ? "mr-1.5 text-tool" : "mr-1.5 text-muted-foreground/40"}>
            ●
          </span>
          {speaking ? "speaking" : thinking ? "thinking" : "listening"}
        </span>
      }
      className={`flex min-h-0 flex-col gap-3 px-4 pt-5 pb-4 transition-colors duration-500 ${speaking ? "animate-floor" : ""}`}
      style={{ borderColor: speaking || looking ? agent.color : undefined, ["--tint" as string]: agent.color }}
    >
      <p className="text-muted-foreground/70">{agent.tagline}</p>

      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 text-muted-foreground">
        {agent.aliases.length > 0 && (
          <>
            <dt className="text-muted-foreground/50">aka</dt>
            <dd className="min-w-0 break-words">{agent.aliases.join(", ")}</dd>
          </>
        )}
        {agent.features.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="max-w-28 text-muted-foreground/50">{k}</dt>
            <dd className="min-w-0 break-words">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-auto flex h-10 items-center justify-center" style={{ opacity: speaking ? 1 : 0.25 }}>
        {speaking ? (
          <VoiceVisualizer
            participantType="bot"
            barColor={agent.color}
            barCount={16}
            barGap={5}
            barWidth={6}
            barMaxHeight={40}
            barOrigin="center"
            barLineCap="square"
            backgroundColor="transparent"
          />
        ) : (
          <span className="text-muted-foreground/40">· · · · · · · ·</span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-border pt-3">
        <span className="text-muted-foreground/70">for {name}</span>
        <Meter p={p ?? 0} color={agent.color} cells={12} dim={partial} />
        <span className="tabular-nums text-muted-foreground">{percent(p)}</span>
        <button
          type="button"
          onClick={toggleLook}
          aria-pressed={looking}
          title={looking ? "stop looking at them" : "look at them: Audience is told who you're facing"}
          className="ml-auto flex items-center gap-1.5 border border-border px-2 py-1 leading-none transition-colors hover:bg-muted/60"
          style={{ color: looking ? agent.color : undefined, borderColor: looking ? agent.color : undefined }}
        >
          {looking ? <Eye className="size-3.5" aria-hidden /> : <EyeOff className="size-3.5" aria-hidden />}
          {looking ? "looking" : "look"}
        </button>
      </div>
    </Panel>
  )
}
