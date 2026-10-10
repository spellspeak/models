import { Heart, HeartCrack } from "lucide-react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { useMemo } from "react"

import { USER, labelOf } from "@/cast"
import { SENTIMENT_COLOR } from "@/sentiment"
import { type Pulse, useRoom } from "@/store"

/**
 * Over a character's face: a pulse whenever a line moves how they feel or puts a new mood on their
 * face. The face flashes and bursts pixels in the colour of the mood they're showing (green warm,
 * amber cold, red hostile, grey neither), so it always agrees with the face and the voice. If their
 * feeling moved, a heart slams in with how far: whole and green up, cracked and red down.
 */
export function PulseFx({ who }: { who: string }) {
  const pulse = useRoom((s) => s.pulses[who])
  return <AnimatePresence>{pulse && <Burst key={pulse.n} p={pulse} />}</AnimatePresence>
}

/** Pixels thrown out from the middle, falling a little as they go. */
function useParticles(p: Pulse) {
  return useMemo(() => {
    const n = p.intensity === "high" ? 30 : p.intensity === "medium" ? 22 : 14
    return Array.from({ length: n }, (_, i) => {
      const angle = (i / n) * Math.PI * 2 + Math.random() * 0.5
      const dist = 120 + Math.random() * 150
      return {
        x: Math.cos(angle) * dist,
        y: Math.sin(angle) * dist * 0.85 + 30,
        size: [6, 8, 10, 12][Math.floor(Math.random() * 4)],
        delay: Math.random() * 0.08,
      }
    })
  }, [p])
}

function Burst({ p }: { p: Pulse }) {
  const reduce = useReducedMotion()
  const color = SENTIMENT_COLOR[p.sentiment]
  const particles = useParticles(p)
  const loud = p.sentiment !== "neutral" && !reduce

  return (
    <motion.div className="pointer-events-none absolute inset-0 z-20 overflow-hidden" exit={{ opacity: 0 }} transition={{ duration: 0.22 }} aria-hidden>
      {/* The flash: hard on, off, on, off. A neutral mood only blinks. */}
      {!reduce && (
        <motion.div
          className="absolute inset-0"
          style={{ background: color, mixBlendMode: "color" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: loud ? [0, 0.7, 0.15, 0.45, 0] : [0, 0.35, 0] }}
          transition={{ duration: loud ? 0.55 : 0.3, ease: "linear" }}
        />
      )}

      {/* The burst. */}
      {loud &&
        particles.map((q, i) => (
          <motion.span
            key={i}
            className="absolute top-1/2 left-1/2 block"
            style={{ width: q.size, height: q.size, marginLeft: -q.size / 2, marginTop: -q.size / 2, background: color, boxShadow: "2px 2px 0 #000" }}
            initial={{ x: 0, y: 0, opacity: 1 }}
            animate={{ x: q.x, y: q.y, opacity: [1, 1, 0] }}
            transition={{ duration: 0.85, delay: q.delay, ease: [0.12, 0.8, 0.3, 1], times: [0, 0.7, 1] }}
          />
        ))}

      {/* The heart, if their feeling moved. */}
      {p.change !== 0 && <HeartPop change={p.change} toward={p.toward} />}
    </motion.div>
  )
}

function HeartPop({ change, toward }: { change: number; toward: string | null }) {
  const reduce = useReducedMotion()
  const up = change > 0
  const color = up ? "var(--color-warm)" : "var(--color-hostile)"
  const Icon = up ? Heart : HeartCrack
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <motion.div
        className="frame-thick flex items-center gap-3 bg-black px-4 py-2"
        style={{ ["--frame" as string]: color, color }}
        initial={reduce ? { opacity: 0 } : { scale: 2.6, opacity: 0, rotate: up ? -9 : 9 }}
        animate={{ scale: 1, opacity: 1, rotate: up ? -3 : 3 }}
        exit={reduce ? { opacity: 0 } : { y: up ? -50 : 30, opacity: 0 }}
        transition={{ type: "spring", stiffness: 560, damping: 17, mass: 0.8 }}
      >
        <Icon className="size-12" strokeWidth={2.5} style={{ fill: up ? color : "transparent" }} />
        <span className="flex flex-col items-start">
          <span className="shadow-px text-[52px] leading-[0.95] font-extrabold tabular-nums">{up ? `+${change}` : `−${-change}`}</span>
          {toward && toward !== USER && (
            <span className="text-[11px] leading-none font-bold tracking-[0.24em] uppercase">about {labelOf(toward)}</span>
          )}
        </span>
      </motion.div>
    </div>
  )
}
