import type { CSSProperties, ReactNode } from "react"

/** A bordered region labelled on its own border, as a fieldset legend without the fieldset. */
export function Panel({
  title,
  titleColor,
  status,
  footnote,
  className = "",
  style,
  children,
}: {
  title: string
  /** The legend's colour: the box's own when it lights up. */
  titleColor?: string
  status?: ReactNode
  footnote?: ReactNode
  className?: string
  style?: CSSProperties
  children?: ReactNode
}) {
  const legend = "absolute z-10 bg-background px-1.5 text-[13px] leading-none font-medium"
  return (
    <section className={`relative border border-border ${className}`} style={style}>
      <span
        className={`${legend} top-0 left-3 -translate-y-1/2 transition-colors duration-500 ${titleColor ? "" : "text-agent"}`}
        style={{ color: titleColor }}
      >
        {title}
      </span>
      {status !== undefined && (
        <span className={`${legend} top-0 right-3 -translate-y-1/2`}>{status}</span>
      )}
      {footnote !== undefined && (
        <span className={`${legend} bottom-0 left-3 translate-y-1/2 text-muted-foreground/70`}>
          {footnote}
        </span>
      )}
      {children}
    </section>
  )
}
