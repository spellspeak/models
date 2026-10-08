import { usePipecatClientTransportState } from "@pipecat-ai/client-react"

import { CAST } from "@/cast"
import { Scene } from "@/components/scene"

const BUSY = ["initializing", "authenticating", "authenticated", "connecting", "disconnecting"]

/** Before a session: meet the yard's cast and choose a gaze cue. */
export function ConnectScreen({ onConnect, error }: { onConnect: () => void; error: string | null }) {
  const state = usePipecatClientTransportState()
  const busy = BUSY.includes(state)

  return (
    <main className="mx-auto grid w-full max-w-[1440px] flex-1 items-start gap-6 py-2 lg:grid-cols-[1.3fr_1fr] lg:gap-8">
      <Scene />
      <div className="space-y-6 lg:pt-4">
        <div className="space-y-3">
          <p className="text-[11px] tracking-widest text-agent uppercase">spellspeak audience demo</p>
          <h2 className="text-2xl font-medium tracking-tight sm:text-3xl">Welcome to Neon Yard</h2>
          <p className="text-muted-foreground">
            Four characters share a neon-lit plaza. Talk to one by name or by what you can see,
            to everyone, or to nobody in particular. Audience decides who each turn is for before anyone answers.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
          {CAST.map((c) => (
            <div key={c.id} className="border border-border px-4 pt-4 pb-3">
              <p>
                <span style={{ color: c.color }}>● {c.name.toLowerCase()}</span>
                <span className="text-muted-foreground/60"> · {c.role.toLowerCase()}</span>
              </p>
              <p className="mt-1 text-muted-foreground">{c.tagline}</p>
            </div>
          ))}
        </div>

        <div className="space-y-3 border-t border-border pt-5">
          <p className="text-muted-foreground">Try “the cyborg by the vending machine” or “hey, all of you”.</p>
          <button
            type="button"
            onClick={onConnect}
            disabled={busy}
            className="border border-active/60 px-6 py-2.5 leading-none tracking-wider text-active uppercase transition-colors hover:bg-active/10 disabled:opacity-60"
          >
            {busy ? "connecting…" : "enter the yard"}
          </button>
          {error && <p className="text-inactive">{error}</p>}
        </div>
      </div>
    </main>
  )
}
