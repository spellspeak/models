import {
  Ban,
  CircleX,
  Ear,
  EyeOff,
  FaceAngry,
  FaceExpressionless,
  FaceGrinning,
  FaceNeutral,
  FaceSlightlyFrowning,
  FaceSlightlySmiling,
  Ghost,
  Hand,
  HandHeart,
  HandHelping,
  HeartHandshake,
  Megaphone,
  MessageSquareX,
  Minus,
  Pointer,
  Siren,
  Swords,
  ThumbsUp,
  TriangleAlert,
  Zap,
  type LucideIcon,
} from "lucide-react"

import { Meter, percent } from "@/components/meter"
import { SENTIMENT_COLOR, actSentiment, emotionSentiment } from "@/sentiment"
import type { ActTag } from "@/types"

const EMOTION_ICON: Record<string, LucideIcon> = {
  neutral: FaceNeutral,
  happy: FaceSlightlySmiling,
  amused: FaceGrinning,
  angry: FaceAngry,
  sad: FaceSlightlyFrowning,
  afraid: Ghost,
  surprised: Zap,
  disgusted: FaceExpressionless,
  contemptuous: EyeOff,
}

const ACT_ICON: Record<string, LucideIcon> = {
  insult: MessageSquareX,
  threat: Swords,
  accusation: Pointer,
  tease: FaceGrinning,
  demand: Megaphone,
  dismiss: Ban,
  refusal: CircleX,
  request: Hand,
  thanks: HandHeart,
  praise: ThumbsUp,
  apology: HeartHandshake,
  comfort: HandHelping,
  warning: TriangleAlert,
  none: Minus,
}

/** One reading as a row: an icon, the label, an intensity, a confidence meter in the sentiment's colour. */
function Row({
  Icon,
  label,
  intensity,
  confidence,
  color,
  quiet = false,
  cells = 8,
  trailing,
}: {
  Icon: LucideIcon
  label: string
  intensity?: string
  confidence: number | null
  color: string
  quiet?: boolean
  cells?: number
  trailing?: React.ReactNode
}) {
  return (
    <div className={`flex min-w-0 items-start gap-2 ${quiet ? "opacity-60" : ""}`}>
      <Icon className="mt-[3px] size-3.5 shrink-0" style={{ color }} aria-hidden />
      <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
        <span style={{ color: quiet ? undefined : color }}>
          {label}
          {intensity && !quiet && <span className="text-muted-foreground"> · {intensity}</span>}
        </span>
        {trailing}
      </span>
      <span className="flex shrink-0 items-center gap-2 whitespace-pre">
        <Meter p={confidence ?? 0} color={color} cells={cells} dim={quiet} />
        <span className="text-muted-foreground tabular-nums">{percent(confidence)}</span>
      </span>
    </div>
  )
}

/** How a line sounded: the emotion, its intensity and how sure Tone is. */
export function EmotionRow({
  label,
  intensity,
  confidence,
  backchannel = false,
  cells,
}: {
  label: string
  intensity: string
  confidence: number | null
  backchannel?: boolean
  cells?: number
}) {
  const s = emotionSentiment(label)
  return (
    <Row
      Icon={backchannel ? Ear : (EMOTION_ICON[label] ?? FaceNeutral)}
      label={backchannel ? "just listening" : label}
      intensity={label === "neutral" ? undefined : intensity}
      confidence={confidence}
      color={SENTIMENT_COLOR[s]}
      quiet={label === "neutral" && !backchannel}
      cells={cells}
    />
  )
}

/** What a line did to one person: the act, its intensity, the confidence, and a badge when hostile. */
export function ActRow({ to, tag, cells }: { to: string; tag: ActTag | undefined; cells?: number }) {
  if (!tag) return <Row Icon={Minus} label={`→ ${to}`} confidence={null} color={SENTIMENT_COLOR.neutral} quiet cells={cells} />
  const s = actSentiment(tag.act, tag.hostile)
  return (
    <Row
      Icon={ACT_ICON[tag.act] ?? Minus}
      label={`${tag.act} → ${to}`}
      intensity={tag.intensity}
      confidence={tag.confidence}
      color={SENTIMENT_COLOR[s]}
      quiet={tag.act === "none"}
      cells={cells}
      trailing={tag.hostile ? <HostileBadge /> : undefined}
    />
  )
}

export function HostileBadge() {
  return (
    <span className="inline-flex items-center gap-1 border border-hostile/60 px-1.5 text-[11px] leading-[1.5] tracking-wider text-hostile uppercase">
      <Siren className="size-3" aria-hidden />
      hostile
    </span>
  )
}

/** A heart's movement, as a small badge: "+6" in green, "−10" in red. */
export function HeartDelta({ change }: { change: number | undefined }) {
  if (!change) return null
  const up = change > 0
  return (
    <span
      className="inline-flex items-center gap-1 border px-1.5 text-[11px] leading-[1.5] tabular-nums"
      style={{
        color: up ? "var(--color-warm)" : "var(--color-hostile)",
        borderColor: up ? "color-mix(in oklab, var(--color-warm) 60%, transparent)" : "color-mix(in oklab, var(--color-hostile) 60%, transparent)",
      }}
    >
      ♥ {up ? `+${change}` : `−${-change}`}
    </span>
  )
}
