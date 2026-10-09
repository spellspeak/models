import { useEffect, useRef } from "react"

import { CAST, USER, colorOf, labelOf } from "@/cast"
import { Panel } from "@/components/panel"
import { useRoom } from "@/store"

/** Every line, who said it and who it was for, newest at the bottom, plus what you're saying now. */
export function Transcript() {
  const lines = useRoom((s) => s.lines)
  const heard = useRoom((s) => [...s.heardFinals, s.heardInterim].join(" ").trim())
  const userSpeaking = useRoom((s) => s.userSpeaking)
  const scroll = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight
  }, [lines, heard])

  return (
    <Panel
      title="conversation"
      status={<span className="text-muted-foreground">{lines.length} lines</span>}
      className="flex min-h-0 flex-1 basis-0 flex-col"
    >
      <div ref={scroll} className="min-h-0 flex-1 space-y-1.5 overflow-y-auto px-4 pt-5 pb-4 text-[12px] leading-[1.55]">
        {lines.map((l) => {
          const you = l.speaker === USER
          const color = colorOf(l.speaker)
          const to = you ? (l.to.length ? (l.to.length === CAST.length ? "everyone" : l.to.map((t) => labelOf(t).toLowerCase()).join(", ")) : "?") : null
          return (
            <p key={l.id}>
              <span style={{ color }}>{labelOf(l.speaker).toLowerCase()}</span>
              {to && <span className="text-muted-foreground/60"> → {to}</span>}
              {l.how === "together" && <span className="text-muted-foreground/50"> ∥</span>}
              <span className="text-muted-foreground/50"> │ </span>
              <span className="text-foreground">
                {l.text}
                {l.interrupted ? "…" : ""}
              </span>
            </p>
          )
        })}
        {heard && (
          <p className="text-muted-foreground">
            <span className={userSpeaking ? "text-active" : "text-client"}>{userSpeaking ? "● " : ""}you</span>
            <span className="text-muted-foreground/50"> │ </span>
            {heard}
          </p>
        )}
      </div>
    </Panel>
  )
}
