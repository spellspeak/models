import { usePipecatClient, usePipecatClientTransportState } from "@pipecat-ai/client-react"
import { Eye } from "lucide-react"
import type { CSSProperties, ReactNode } from "react"

import base from "@/assets/base.png"
import { BY_DEPTH, CAST, type Character } from "@/cast"
import { Meter, percent } from "@/components/meter"
import { useLight, useRoom } from "@/store"

const EASE = "600ms cubic-bezier(0.2, 0.8, 0.2, 1)"
/** How far the scene darkens around whoever is lit. */
const DIM = 0.66

/** Look at a character (or stop): the bot reads it as gaze. */
function useLook() {
  const client = usePipecatClient()
  const state = usePipecatClientTransportState()
  const looking = useRoom((s) => s.looking)
  return (id: string) => {
    const next = looking === id ? null : id
    useRoom.getState().look(next)
    if (state === "ready") client?.sendClientMessage("look", { character: next })
  }
}

function points(c: Character) {
  return c.outline.map(([x, y]) => `${x},${y}`).join(" ")
}

/**
 * base.png filling the space, with each character's outline over it (the same viewBox and
 * cropping as the image, so the two line up at any size). Whoever is lit (speaking, about to, or
 * likely to be the one you're talking to) stays bright; everyone else drops back into the dark.
 */
export function Scene({ children }: { children?: ReactNode }) {
  const { focus, lit } = useLight()
  const voices = useRoom((s) => s.voices)
  const looking = useRoom((s) => s.looking)
  const look = useLook()

  return (
    <div className="scanlines relative h-[62svh] min-w-0 shrink-0 overflow-hidden border border-border bg-black lg:h-auto lg:min-h-0 lg:flex-1 lg:shrink">
      <img
        src={base}
        alt="A cramped neon garage at night: Nova the courier beside her dirt bike, Bruno the engineer crouched at a machine, Atlas the robot in the doorway, and Kai the hacker at the screens."
        className="pixelated absolute inset-0 h-full w-full object-cover"
      />
      <svg
        viewBox="0 0 2048 2048"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full"
        aria-hidden
      >
        <defs>
          <mask id="spotlight">
            <rect width="2048" height="2048" fill="white" />
            {CAST.map((c) => (
              <polygon
                key={c.id}
                points={points(c)}
                fill="black"
                style={{ fillOpacity: lit(c.id), transition: `fill-opacity ${EASE}` }}
              />
            ))}
          </mask>
        </defs>
        <rect
          width="2048"
          height="2048"
          fill="#03030a"
          mask="url(#spotlight)"
          style={{ opacity: focus ? DIM : 0, transition: `opacity ${EASE}` }}
        />
        {BY_DEPTH.map((c) => {
          const speaking = voices.includes(c.id)
          const shown = Math.max(focus ? lit(c.id) : 0, looking === c.id ? 0.55 : 0)
          return (
            <g key={c.id} className="group cursor-pointer" onClick={() => look(c.id)}>
              <polygon
                points={points(c)}
                fill="transparent"
                pointerEvents="all"
                stroke={c.color}
                strokeWidth={speaking ? 5 : 3.5}
                strokeDasharray={speaking ? "16 8" : "6 10"}
                strokeLinejoin="miter"
                className={`group-hover:[stroke-opacity:0.7] ${speaking ? "outline-speaking" : ""}`}
                style={{ strokeOpacity: shown, transition: `stroke-opacity ${EASE}` } as CSSProperties}
              />
              <Tag c={c} shown={Math.max(shown, 0.35)} speaking={speaking} looking={looking === c.id} />
            </g>
          )
        })}
      </svg>
      {children}
    </div>
  )
}

/** A character's name tag, a terminal label pinned to the top of their outline. */
function Tag({ c, shown, speaking, looking }: { c: Character; shown: number; speaking: boolean; looking: boolean }) {
  const [x0, y0] = c.box
  const text = `${speaking ? "▶" : looking ? "◉" : "▸"} ${c.name.toLowerCase()}`
  const w = 22 * text.length + 28
  const x = Math.min(Math.max(x0, 8), 2048 - w - 8)
  const y = Math.max(y0 - 58, 8)
  return (
    <g style={{ opacity: shown, transition: `opacity ${EASE}` }} className="group-hover:[opacity:1]">
      <rect x={x} y={y} width={w} height={46} fill="#03030a" fillOpacity={0.82} stroke={c.color} strokeOpacity={0.6} strokeWidth={2} />
      <text x={x + 14} y={y + 32} fill={c.color} fontSize={30} fontFamily="JetBrains Mono Variable, ui-monospace, monospace">
        {text}
      </text>
    </g>
  )
}

/**
 * Along the bottom of the scene: each character's portrait and Audience's chance that what you're
 * saying is for them, as it's read, plus everyone and unclear. A portrait lights up as its
 * character is addressed, blinks a cursor while they think, and glows while they speak.
 */
export function Strip() {
  const reading = useRoom((s) => s.reading)
  const settled = useRoom((s) => s.settled)
  const live = reading !== null && !settled
  const partial = reading !== null && !reading.final

  return (
    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/85 to-transparent px-3 pt-10 pb-3">
      <div className="flex items-end gap-2 sm:gap-3">
        {CAST.map((c) => (
          <Portrait key={c.id} c={c} p={reading?.addressed[c.id] ?? null} live={live} partial={partial} />
        ))}
        <div className="ml-auto hidden min-w-0 shrink-0 flex-col gap-1 pb-0.5 text-[11px] leading-none md:flex">
          <Odds label="everyone" p={reading?.to_group ?? null} color="var(--color-agent)" live={live} partial={partial} />
          <Odds label="unclear" p={reading?.unclear ?? null} color="var(--color-tool)" live={live} partial={partial} />
        </div>
      </div>
    </div>
  )
}

function Odds({ label, p, color, live, partial }: { label: string; p: number | null; color: string; live: boolean; partial: boolean }) {
  return (
    <div className="flex items-center gap-2 transition-opacity duration-500" style={{ opacity: live ? 1 : 0.35 }}>
      <span className="w-16 text-right text-muted-foreground">{label}</span>
      <Meter p={live ? (p ?? 0) : 0} color={color} cells={8} dim={partial} />
      <span className="w-8 tabular-nums text-muted-foreground">{live ? percent(p) : "  —"}</span>
    </div>
  )
}

function Portrait({ c, p, live, partial }: { c: Character; p: number | null; live: boolean; partial: boolean }) {
  const { lit } = useLight()
  const speaking = useRoom((s) => s.voices.includes(c.id))
  const thinking = useRoom((s) => c.id in s.thinking)
  const looking = useRoom((s) => s.looking === c.id)
  const look = useLook()
  const glow = lit(c.id)
  const on = glow > 0.5

  return (
    <button
      type="button"
      onClick={() => look(c.id)}
      title={looking ? `stop looking at ${c.name}` : `look at ${c.name}: Audience reads it as gaze`}
      className="group flex min-w-0 flex-1 items-end gap-2 text-left sm:max-w-56"
    >
      <span
        className={`relative block size-11 shrink-0 overflow-hidden border transition-[filter,border-color] duration-500 sm:size-14 ${speaking ? "animate-speaking" : ""}`}
        style={{
          ["--tint" as string]: c.color,
          borderColor: on || looking ? c.color : "var(--color-border)",
          filter: on ? "none" : `grayscale(${1 - glow}) brightness(${0.45 + glow * 0.55})`,
        }}
      >
        <img src={c.portrait} alt={c.name} className="pixelated h-full w-full object-cover" />
        {thinking && !speaking && (
          <span className="animate-blink absolute right-1 bottom-0.5 text-[13px] leading-none" style={{ color: c.color }}>
            ▌
          </span>
        )}
        {looking && <Eye className="absolute top-0.5 left-0.5 size-3" style={{ color: c.color }} aria-hidden />}
      </span>
      <span className="min-w-0 flex-1 pb-0.5 text-[11px] leading-[1.35]">
        <span className="block truncate transition-colors duration-500" style={{ color: on || looking ? c.color : "var(--color-muted-foreground)" }}>
          {speaking ? "▶ " : ""}
          {c.name.toLowerCase()}
          <span className="text-muted-foreground/60"> · {c.role.toLowerCase()}</span>
        </span>
        <span className="flex items-center gap-1.5 transition-opacity duration-500" style={{ opacity: live ? 1 : 0.35 }}>
          <span className="min-w-0 overflow-hidden">
            <Meter p={live ? (p ?? 0) : 0} color={c.color} cells={8} dim={partial} />
          </span>
          <span className="tabular-nums text-muted-foreground">{live ? percent(p) : "  —"}</span>
        </span>
      </span>
    </button>
  )
}

/** Terminal blips over the scene's top-left corner: what Audience read, who's speaking. */
export function Blips() {
  const blips = useRoom((s) => s.blips)
  return (
    <div className="pointer-events-none absolute top-2 left-2 max-w-[min(34rem,70%)] space-y-0.5 text-[11px] leading-[1.4]">
      {blips.map((b, i) => (
        <p
          key={b.n}
          className="animate-blip truncate bg-black/70 px-1.5 text-muted-foreground"
          style={{ opacity: 0.35 + (0.65 * (i + 1)) / blips.length, color: b.color }}
        >
          <span className="text-active">›</span> {b.text}
        </p>
      ))}
    </div>
  )
}
