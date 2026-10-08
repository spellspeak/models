import { usePipecatClientTransportState } from "@pipecat-ai/client-react"

import { Heart } from "@/components/heart"
import { Panel } from "@/components/panel"
import { CAST } from "@/cast"
import { useTable } from "@/store"

const BUSY = ["initializing", "authenticating", "authenticated", "connecting", "disconnecting"]

/** Before a session: pick who to sit down with. Each card shows how they feel about you so far. */
export function ConnectScreen({
  onConnect,
  onDisconnect,
  error,
}: {
  onConnect: () => void
  onDisconnect: () => void
  error: string | null
}) {
  const state = usePipecatClientTransportState()
  const busy = BUSY.includes(state)
  const picked = useTable((s) => s.picked)
  const hearts = useTable((s) => s.hearts)
  const pick = useTable((s) => s.pick)
  const who = CAST.find((c) => c.id === picked)

  return (
    <main className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto py-8">
      <div className="my-auto w-full max-w-2xl space-y-7 px-2">
        <h2 className="text-center text-2xl font-medium tracking-tight">who will you sit with?</h2>

        <div className="grid grid-cols-2 gap-4">
          {CAST.map((c) => {
            const on = c.id === picked
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => pick(c.id)}
                disabled={busy}
                aria-pressed={on}
                className="border border-border px-4 pt-4 pb-3 text-left transition-colors hover:bg-muted/60 disabled:opacity-60"
                style={{ borderColor: on ? c.color : undefined }}
              >
                <p>
                  <span style={{ color: c.color }}>{on ? "❯ " : "● "}{c.name.toLowerCase()}</span>
                  <span className="text-muted-foreground/60"> · {c.role.toLowerCase()}</span>
                </p>
                <p className="mt-1 min-h-10 text-muted-foreground/70">{c.tagline}</p>
                <div className="mt-2 text-muted-foreground">
                  <Heart value={hearts[c.id] ?? 50} cells={12} words />
                </div>
              </button>
            )
          })}
        </div>

        <Panel title="connect" footnote="deepgram · openai · deepgram · tone">
          <div className="space-y-4 px-5 pt-6 pb-5">
            <p className="text-muted-foreground/70">
              One at a time, at the kitchen table. Tone reads every line, yours and theirs, and says
              how it sounded and what it did to the other person. Hearts carry over: be kind and they fill,
              be rude and they drain, and the character knows it next time you sit down.
            </p>
            <button
              type="button"
              onClick={busy ? onDisconnect : onConnect}
              disabled={!busy && !who}
              className={`h-11 w-full tracking-wider uppercase transition-colors disabled:opacity-40 ${
                busy
                  ? "border border-inactive/40 text-inactive hover:bg-inactive/10"
                  : "bg-active text-background hover:bg-active/85"
              }`}
            >
              {busy
                ? state === "disconnecting"
                  ? "disconnecting…"
                  : "connecting… (click to cancel)"
                : who
                  ? `sit with ${who.name.toLowerCase()}`
                  : "pick someone"}
            </button>
          </div>
        </Panel>
        <div className="min-h-12 text-center" aria-live="polite">
          {error && <p role="alert" className="break-words text-inactive">{error}</p>}
        </div>
      </div>
    </main>
  )
}
