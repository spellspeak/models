import { motion, useReducedMotion } from "motion/react"
import { useEffect, useState } from "react"

import { moodIndex, type Character } from "@/cast"

/**
 * One face of a character's mood sheet, square, filling its box. The sheet is a 3 × 3 grid, so the
 * image is drawn three times the box's size and moved to the face's cell. Without a sheet, their
 * portrait.
 */
function Cell({ c, index }: { c: Character; index: number }) {
  if (!c.sheet) {
    return <img src={c.portrait} alt="" draggable={false} className="pixelated absolute inset-0 h-full w-full" />
  }
  const col = index % 3
  const row = Math.floor(index / 3)
  return (
    <img
      src={c.sheet}
      alt=""
      draggable={false}
      className="pixelated absolute top-0 left-0 max-w-none select-none"
      style={{ width: "300%", height: "300%", transform: `translate(${(-col * 100) / 3}%, ${(-row * 100) / 3}%)` }}
    />
  )
}

/**
 * A character's face in their mood. Every face is a cell of one sheet, loaded and decoded before
 * the screen shows (preload.ts), so a new mood is drawn over the last at once and faded in, with
 * nothing to wait for.
 */
export function Sprite({ c, mood }: { c: Character; mood: string }) {
  const reduce = useReducedMotion()
  const index = moodIndex(mood)
  const [base, setBase] = useState(index)
  const [top, setTop] = useState<number | null>(null)

  useEffect(() => {
    if (index === base && top === null) return
    if (index === top) return
    if (top !== null) setBase(top) // a change mid-fade: the face fading in is finished at once
    setTop(index)
  }, [index])

  return (
    <div role="img" aria-label={`${c.name}, ${mood}`} className="absolute inset-0 overflow-hidden bg-black">
      <Cell c={c} index={base} />
      {top !== null && (
        <motion.div
          key={top}
          className="absolute inset-0 overflow-hidden"
          initial={{ opacity: reduce ? 1 : 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.16, ease: "linear" }}
          onAnimationComplete={() => {
            setBase(top)
            setTop(null)
          }}
        >
          <Cell c={c} index={top} />
        </motion.div>
      )}
    </div>
  )
}
