import { Mic, User } from "lucide-react"
import { useEffect, useRef } from "react"

import { USER, colorOf, labelOf } from "@/cast"
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
  }, [lines.length, heard])

  return (
    <Panel
      title="conversation"
      status={<span className="text-muted-foreground">{lines.length} lines</span>}
      className="flex h-80 min-h-0 flex-col xl:h-96"
    >
      <div ref={scroll} className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 pt-5 pb-4">
        {lines.map((l, i) => {
          const you = l.speaker === USER
          const color = colorOf(l.speaker)
          const to = you ? (l.to.length ? l.to.map(labelOf).join(", ") : "unclear") : null
          return (
            <p key={i} className="flex gap-2">
              {you ? (
                <User className="mt-1 size-3.5 shrink-0" style={{ color }} aria-hidden />
              ) : (
                <Mic className="mt-1 size-3.5 shrink-0" style={{ color }} aria-hidden />
              )}
              <span>
                <span style={{ color }}>{labelOf(l.speaker)}</span>
                {to && <span className="text-muted-foreground/60"> → {to}</span>}
                <span className="text-muted-foreground/60">: </span>
                <span className="text-foreground">
                  {l.text}
                  {l.interrupted ? "…" : ""}
                </span>
              </span>
            </p>
          )
        })}
        {heard && (
          <p className="flex items-center gap-2 text-muted-foreground">
            <User className="size-3.5 text-client" aria-hidden />
            <span className={userSpeaking ? "text-active" : "text-client"}>{userSpeaking ? "● " : ""}</span>
            {heard}
          </p>
        )}
      </div>
    </Panel>
  )
}
