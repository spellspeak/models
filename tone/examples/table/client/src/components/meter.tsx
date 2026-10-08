const EIGHTHS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]

/** A share as a row of block characters, `cells` wide, to an eighth of a cell. */
export function Meter({
  p,
  color,
  cells = 20,
  dim = false,
}: {
  p: number
  color: string
  cells?: number
  dim?: boolean
}) {
  const eighths = Math.round(Math.min(Math.max(p, 0), 1) * cells * 8)
  const full = Math.floor(eighths / 8)
  const part = EIGHTHS[eighths % 8]
  const filled = "█".repeat(full) + part
  const empty = "░".repeat(Math.max(cells - full - (part ? 1 : 0), 0))
  return (
    <span className="whitespace-pre" aria-hidden>
      <span style={{ color, opacity: dim ? 0.55 : 1 }}>{filled}</span>
      <span className="text-muted-foreground/30">{empty}</span>
    </span>
  )
}

export function percent(p: number | null | undefined): string {
  return p === null || p === undefined ? "  —" : `${Math.round(p * 100)}%`.padStart(4, " ")
}
