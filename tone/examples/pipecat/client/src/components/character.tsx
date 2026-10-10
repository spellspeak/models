import { AnimatePresence, LayoutGroup, motion, useAnimate, useReducedMotion } from "motion/react"
import { useEffect, useRef, useState } from "react"

import { MOODS, labelOf, peopleFor, type Character } from "@/cast"
import { PulseFx } from "@/components/fx"
import { Segments } from "@/components/segments"
import { Sprite } from "@/components/sprite"
import { SENTIMENT_COLOR, emotionSentiment, feelingSentiment, feelingWord } from "@/sentiment"
import { useRoom } from "@/store"
import type { Face } from "@/types"

/** The portrait's size: square, as large as fits, never past twice the art (512 px). */
const PORTRAIT = "min(512px, 100%, calc(100svh - 21rem))"

/**
 * A character's card: who they are and what they're doing, their face in their mood (with a pulse
 * over it when a line moves them), how they feel about everyone here, and the mood
 * map: Tone's nine emotions, where they are among them, and why.
 */
export function CharacterCard({ c }: { c: Character }) {
  return (
    <div className="flex w-full flex-col gap-3" style={{ maxWidth: PORTRAIT }}>
      <Portrait c={c} />
      <Feelings c={c} />
      <MoodMap c={c} />
    </div>
  )
}

function State({ c }: { c: Character }) {
  const speaking = useRoom((s) => s.voices.includes(c.id))
  const thinking = useRoom((s) => c.id in s.thinking)
  const listening = useRoom((s) => s.userSpeaking)
  if (speaking)
    return (
      <span className="flex items-center gap-2">
        <span className="flex h-3 items-end gap-[2px]" aria-hidden>
          {[0, 0.15, 0.3, 0.1].map((d, i) => (
            <span key={i} className="animate-bar block h-full w-[3px] bg-current" style={{ animationDelay: `${d}s` }} />
          ))}
        </span>
        speaking
      </span>
    )
  if (thinking)
    return (
      <span>
        thinking<span className="animate-blink">_</span>
      </span>
    )
  if (listening) return <span>listening</span>
  return <span className="opacity-60">idle</span>
}

/** Their face, framed in their colour, with the pulse and the mood stamp over it. */
function Portrait({ c }: { c: Character }) {
  const reduce = useReducedMotion()
  const face = useRoom((s) => s.faces[c.id])
  const speaking = useRoom((s) => s.voices.includes(c.id))
  const pulse = useRoom((s) => s.pulses[c.id])
  const [scope, animate] = useAnimate<HTMLDivElement>()
  const mood = face?.mood ?? "neutral"

  // In the mood they're showing: hostile, a hard shake; warm, a hop; cold, a flinch.
  useEffect(() => {
    if (!pulse || reduce || !scope.current) return
    if (pulse.sentiment === "hostile") {
      const k = pulse.intensity === "high" ? 16 : 11
      void animate(scope.current, { x: [0, -k, k, -k * 0.75, k * 0.75, -k / 2, k / 2, 0] }, { duration: 0.42, ease: "linear" })
    } else if (pulse.sentiment === "warm") {
      void animate(scope.current, { y: [0, -18, 0, -7, 0] }, { duration: 0.5, ease: "easeOut" })
    } else if (pulse.sentiment === "cold") {
      void animate(scope.current, { x: [0, -6, 4, 0], y: [0, 2, 0, 0] }, { duration: 0.3, ease: "linear" })
    }
  }, [pulse?.n])

  return (
    <section className="frame-thick bg-black" style={{ ["--frame" as string]: speaking ? c.color : "var(--color-border)" }}>
      <header
        className="flex h-7 items-center justify-between px-2.5 text-[12px] leading-none font-bold tracking-[0.16em] uppercase"
        style={{ background: c.color, color: "var(--color-background)" }}
      >
        <span>
          {c.name} <span className="opacity-60">/ {c.role}</span>
        </span>
        <State c={c} />
      </header>
      <div ref={scope} className="relative aspect-square w-full overflow-hidden">
        <Sprite c={c} mood={mood} />
        <MoodStamp face={face} />
        <PulseFx who={c.id} />
      </div>
    </section>
  )
}

/** The mood, stamped into the corner of the face: it slams in whenever it changes. */
function MoodStamp({ face }: { face: Face | undefined }) {
  const reduce = useReducedMotion()
  const mood = face?.mood ?? "neutral"
  const color = SENTIMENT_COLOR[emotionSentiment(mood)]
  const pips = face?.intensity === "high" ? 3 : face?.intensity === "medium" ? 2 : 1
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 z-10">
      <AnimatePresence mode="popLayout">
        <motion.div
          key={mood}
          className="frame flex items-center gap-2 bg-black px-2 py-1"
          style={{ ["--frame" as string]: color, color }}
          initial={reduce ? { opacity: 0 } : { scale: 2.2, opacity: 0, rotate: -12 }}
          animate={{ scale: 1, opacity: 1, rotate: 0 }}
          exit={{ opacity: 0, transition: { duration: 0.08 } }}
          transition={{ type: "spring", stiffness: 520, damping: 20 }}
        >
          <span className="text-[15px] leading-none font-extrabold tracking-[0.12em] uppercase">{mood}</span>
          {mood !== "neutral" && (
            <span className="flex gap-[2px]" aria-label={`${face?.intensity} intensity`}>
              {[0, 1, 2].map((i) => (
                <span key={i} className="block size-[5px]" style={{ background: i < pips ? color : "var(--color-muted)" }} />
              ))}
            </span>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

/** A number that just moved, shown beside it for a moment: "+8", "−14". */
function useDelta(value: number): { change: number; n: number } | null {
  const last = useRef(value)
  const [delta, setDelta] = useState<{ change: number; n: number } | null>(null)
  useEffect(() => {
    const change = value - last.current
    last.current = value
    if (!change) return
    setDelta((d) => ({ change, n: (d?.n ?? 0) + 1 }))
    const t = setTimeout(() => setDelta(null), 2200)
    return () => clearTimeout(t)
  }, [value])
  return delta
}

/** The last values of a feeling as a strip of block characters. */
function Trend({ values, color }: { values: number[]; color: string }) {
  const blocks = "▁▂▃▄▅▆▇█"
  const shown = values.slice(-12)
  return (
    <span className="text-[13px] leading-none tracking-[-0.05em]" style={{ color }} aria-hidden>
      <span className="text-muted">{"▁".repeat(Math.max(0, 12 - shown.length))}</span>
      {shown.map((v) => blocks[Math.min(7, Math.floor((v / 100) * 8))]).join("")}
    </span>
  )
}

function FeelingRow({ who, toward }: { who: string; toward: string }) {
  const value = useRoom((s) => s.feelings[who]?.[toward] ?? 50)
  const history = useRoom((s) => s.history[`${who}:${toward}`])
  const delta = useDelta(value)
  const color = SENTIMENT_COLOR[feelingSentiment(value)]

  return (
    <div className="grid grid-cols-[3rem_auto_2rem_2.75rem] items-center gap-x-2 py-[5px] sm:grid-cols-[3rem_auto_2rem_1fr_2.75rem]">
      <span className="text-[12px] font-bold tracking-[0.12em] uppercase" style={{ color: toward === "player" ? "var(--color-client)" : undefined }}>
        {labelOf(toward)}
      </span>
      <Segments p={value / 100} color={color} count={20} size={7} gap={2} />
      <motion.span key={value} className="text-right text-[14px] leading-none font-extrabold tabular-nums" style={{ color }} initial={delta ? { scale: 1.6 } : false} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 15 }}>
        {value}
      </motion.span>
      <span className="hidden min-w-0 flex-col gap-1 sm:flex">
        <Trend values={history ?? [value]} color={color} />
        <span className="truncate text-[10px] leading-none font-bold tracking-[0.12em] uppercase" style={{ color }}>
          {feelingWord(value)}
        </span>
      </span>
      <span className="text-right">
        <AnimatePresence>
          {delta && (
            <motion.span
              key={delta.n}
              className="inline-block px-1 py-[3px] text-[12px] leading-none font-extrabold tabular-nums"
              style={{ background: delta.change > 0 ? "var(--color-warm)" : "var(--color-hostile)", color: "var(--color-background)" }}
              initial={{ scale: 0, y: 6 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ type: "spring", stiffness: 700, damping: 18 }}
            >
              {delta.change > 0 ? `+${delta.change}` : `−${-delta.change}`}
            </motion.span>
          )}
        </AnimatePresence>
      </span>
    </div>
  )
}

/** How they feel about everyone here, a row each, right under their face. */
function Feelings({ c }: { c: Character }) {
  return (
    <section className="frame bg-card px-2.5 pt-1.5 pb-1">
      <p className="flex justify-between pb-0.5 text-[10px] font-bold tracking-[0.2em] text-muted-foreground uppercase">
        <span>{c.name} feels about</span>
        <span>0–100</span>
      </p>
      <div className="divide-y divide-border/60">
        {peopleFor(c.id).map((p) => (
          <FeelingRow key={p} who={c.id} toward={p} />
        ))}
      </div>
    </section>
  )
}

/** Why a face is what it is, in a few words. */
function why(face: Face | undefined): string {
  if (!face || face.why === "rest") return "at rest · how they feel about you"
  if (face.why === "expressed") return "expressing it · in their own words"
  return `reacting to ${labelOf(face.by).toLowerCase()} · ${face.act}`
}

/** Tone's nine emotions as a 3 × 3 map, laid out like the sheet: a cursor jumps to the mood. */
function MoodMap({ c }: { c: Character }) {
  const face = useRoom((s) => s.faces[c.id])
  const tag = useRoom((s) => s.tags[c.id])
  const mood = face?.mood ?? "neutral"
  const color = SENTIMENT_COLOR[emotionSentiment(mood)]
  return (
    <section className="frame bg-card px-2.5 pt-1.5 pb-2.5">
      <p className="flex justify-between pb-1.5 text-[10px] font-bold tracking-[0.2em] text-muted-foreground uppercase">
        <span>mood</span>
        <span>tone's nine</span>
      </p>
      <LayoutGroup id={`moods-${c.id}`}>
        <div className="grid grid-cols-3 gap-[3px]">
          {MOODS.map((m) => {
            const on = m === mood
            const mc = SENTIMENT_COLOR[emotionSentiment(m)]
            return (
              <div key={m} className="relative h-6 bg-muted/60">
                {on && (
                  <motion.div layoutId="cursor" className="absolute inset-0" style={{ background: mc }} transition={{ type: "spring", stiffness: 700, damping: 34 }} />
                )}
                <span
                  className="relative flex h-full items-center justify-center text-[11px] leading-none font-bold tracking-[0.08em] uppercase"
                  style={{ color: on ? "var(--color-background)" : mc, opacity: on ? 1 : 0.55 }}
                >
                  {m}
                </span>
              </div>
            )
          })}
        </div>
      </LayoutGroup>
      <div className="mt-2 flex items-center justify-between gap-3 text-[11px] leading-none">
        <span className="truncate" style={{ color }}>
          {why(face)}
        </span>
        <span className="shrink-0 text-muted-foreground">
          voice <span className="text-foreground">{tag || "[no tag]"}</span>
        </span>
      </div>
    </section>
  )
}
