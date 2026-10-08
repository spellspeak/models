import { usePipecatClient, usePipecatClientTransportState } from "@pipecat-ai/client-react"
import { Eye, EyeOff } from "lucide-react"

import { CAST } from "@/cast"
import { useRoom } from "@/store"

/** The shared scene and an optional gaze cue, using the same look message as the seats. */
export function Scene() {
  const client = usePipecatClient()
  const state = usePipecatClientTransportState()
  const looking = useRoom((s) => s.looking)

  const toggleLook = (id: string) => {
    const next = looking === id ? null : id
    useRoom.getState().look(next)
    if (state === "ready") client?.sendClientMessage("look", { agent: next })
  }

  return (
    <figure className="min-w-0 border border-border bg-card">
      <img
        src="/neon-yard.png"
        width={2048}
        height={2048}
        alt="Wide anime Neon Yard station plaza: Juno, a purple-haired courier in a yellow raincoat, raises one boot and gestures beside a magenta hoverbike; Maya, a red-braided biohacker in a sleeveless lime biotech suit and round glasses, scans a glass plant tank; Theo, a broad mechanic in a black tank top and orange overalls tied at his waist, works with his silver cyberarm at an orange repair bench; and Otto, a silver-haired humanoid cyborg with an amber optic, exposed mechanical torso and limbs and cyan armor panels, holds a tablet beside a cyan vending machine. Their faces turn toward the viewer, with space between their different poses."
        className="block aspect-square h-auto w-full object-contain"
      />
      <figcaption className="space-y-3 border-t border-border px-3 py-3 sm:px-4">
        <p className="text-muted-foreground">
          Call someone out by name, appearance, or what they’re standing beside.
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {CAST.map((agent) => {
            const selected = looking === agent.id
            const landmark = agent.features.find(([key]) => key === "standing beside")?.[1]
            return (
              <button
                key={agent.id}
                type="button"
                aria-pressed={selected}
                aria-label={`${selected ? "Stop looking at" : "Look at"} ${agent.name}`}
                onClick={() => toggleLook(agent.id)}
                className="min-w-0 border border-border px-2 py-2 text-left transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2"
                style={{ borderColor: selected ? agent.color : undefined }}
              >
                <span className="flex items-center gap-1.5" style={{ color: agent.color }}>
                  {selected ? <Eye className="size-3.5 shrink-0" aria-hidden /> : <EyeOff className="size-3.5 shrink-0" aria-hidden />}
                  {agent.name.toLowerCase()}
                </span>
                {landmark && <span className="mt-1 block text-[11px] leading-[1.5] text-muted-foreground">{landmark}</span>}
              </button>
            )
          })}
        </div>
        <p className="text-[11px] text-muted-foreground/70">Select a character to show who you’re looking at. Select again to clear.</p>
      </figcaption>
    </figure>
  )
}
