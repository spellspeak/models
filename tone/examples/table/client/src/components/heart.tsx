import { HeartIcon } from "lucide-react"

import { Meter } from "@/components/meter"
import { HeartDelta } from "@/components/reading"
import { SENTIMENT_COLOR, heartSentiment, heartWord } from "@/sentiment"

/** A character's heart: how they feel about you, 0 to 100. Its colour is the level, not the character. */
export function Heart({
  value,
  change,
  cells = 16,
  words = false,
}: {
  value: number
  change?: number
  cells?: number
  /** Also say it in words ("wary of you"). */
  words?: boolean
}) {
  const color = SENTIMENT_COLOR[heartSentiment(value)]
  return (
    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <HeartIcon
        className="size-3.5 shrink-0"
        aria-label="heart"
        style={{ color, fill: value >= 50 ? color : "transparent" }}
      />
      <span className="flex items-center gap-2 whitespace-pre">
        <Meter p={value / 100} color={color} cells={cells} />
        <span className="tabular-nums">{String(value).padStart(3, " ")}</span>
      </span>
      {words && <span className="text-muted-foreground">· {heartWord(value)}</span>}
      <HeartDelta change={change} />
    </span>
  )
}
