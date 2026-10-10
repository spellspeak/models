import { motion, useReducedMotion } from "motion/react"
import { useEffect, useRef, useState } from "react"

/**
 * A pixel bar: `count` square segments, the first `filled` lit in `color`. When it moves, the
 * segments that light up or go out pop one after another, in the direction it went.
 */
export function Segments({
  p,
  color,
  count = 20,
  size = 8,
  gap = 2,
}: {
  p: number
  color: string
  count?: number
  size?: number
  gap?: number
}) {
  const reduce = useReducedMotion()
  const filled = Math.round(Math.min(Math.max(p, 0), 1) * count)
  const last = useRef(filled)
  const [wave, setWave] = useState({ from: filled, to: filled, n: 0 })
  useEffect(() => {
    if (last.current !== filled) {
      setWave((w) => ({ from: last.current, to: filled, n: w.n + 1 }))
      last.current = filled
    }
  }, [filled])

  const lo = Math.min(wave.from, wave.to)
  const hi = Math.max(wave.from, wave.to)
  const up = wave.to > wave.from
  return (
    <span className="inline-flex shrink-0" style={{ gap }} aria-hidden>
      {Array.from({ length: count }, (_, i) => {
        const moved = !reduce && wave.n > 0 && i >= lo && i < hi
        const order = up ? i - lo : hi - 1 - i
        return (
          <motion.span
            key={moved ? `${i}-${wave.n}` : i}
            className="block"
            style={{
              width: size,
              height: size,
              background: i < filled ? color : "var(--color-muted)",
              transition: `background-color 60ms steps(1) ${moved ? order * 45 : 0}ms`,
            }}
            initial={false}
            animate={moved ? { scale: [1, 1.7, 1], y: [0, up ? -3 : 3, 0] } : undefined}
            transition={{ duration: 0.28, delay: order * 0.045, ease: "easeOut" }}
          />
        )
      })}
    </span>
  )
}
