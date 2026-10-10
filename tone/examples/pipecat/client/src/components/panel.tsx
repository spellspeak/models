import type { CSSProperties, ReactNode } from "react"

/**
 * A pixel window: a hard 2 px frame with stepped corners, and a title bar filled in the frame's
 * colour, its label knocked out of it. `color` sets the frame (a character's colour for their card).
 */
export function Panel({
  title,
  right,
  color,
  className = "",
  bodyClassName = "",
  style,
  children,
}: {
  title: ReactNode
  right?: ReactNode
  color?: string
  className?: string
  bodyClassName?: string
  style?: CSSProperties
  children?: ReactNode
}) {
  const frame = color ?? "var(--color-border)"
  return (
    <section className={`frame flex flex-col bg-card ${className}`} style={{ ["--frame" as string]: frame, ...style }}>
      <header
        className="flex h-6 shrink-0 items-center justify-between gap-3 px-2 text-[11px] leading-none font-bold tracking-[0.16em] uppercase"
        style={{ background: frame, color: color ? "var(--color-background)" : "var(--color-foreground)" }}
      >
        <span className="truncate">{title}</span>
        {right !== undefined && <span className="flex shrink-0 items-center gap-2 font-semibold">{right}</span>}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  )
}

/** A pixel button: framed, inverted on hover. */
export function PixelButton({
  children,
  onClick,
  color = "var(--color-foreground)",
  disabled = false,
  title,
  className = "",
}: {
  children: ReactNode
  onClick?: () => void
  color?: string
  disabled?: boolean
  title?: string
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`frame inline-flex h-7 items-center gap-2 px-3 text-[11px] leading-none font-bold tracking-[0.16em] uppercase transition-colors duration-75 hover:bg-[var(--frame)] hover:text-background disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-[var(--frame)] ${className}`}
      style={{ ["--frame" as string]: color, color }}
    >
      {children}
    </button>
  )
}
