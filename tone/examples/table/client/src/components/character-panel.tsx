import { VoiceVisualizer } from "@pipecat-ai/client-react"
import { Mic, User } from "lucide-react"

import { Heart } from "@/components/heart"
import { Panel } from "@/components/panel"
import { ActRow, EmotionRow } from "@/components/reading"
import { PLAYER, type Character } from "@/cast"
import { lastLineBy, useTable } from "@/store"

/**
 * The character you are with: their voice as it plays, their heart, how their last line sounded and what
 * Tone says it did to you, and what your last line did to them.
 */
export function CharacterPanel({ character }: { character: Character }) {
  const heart = useTable((s) => s.hearts[character.id] ?? 50)
  const speaking = useTable((s) => s.botSpeaking)
  const said = useTable((s) => lastLineBy(s.lines, character.id))
  const yours = useTable((s) => lastLineBy(s.lines, PLAYER))
  const last = useTable((s) => s.lines[s.lines.length - 1])
  const change = last?.changes[character.id]
  const name = character.name.toLowerCase()

  return (
    <Panel
      title={`${name} · ${character.role.toLowerCase()}`}
      titleColor={speaking ? character.color : undefined}
      status={
        <span className="text-muted-foreground">
          <span className={speaking ? "mr-1.5 text-active" : "text-muted-foreground/40"}>●</span>
          {speaking ? "speaking" : "listening"}
        </span>
      }
      className={`flex min-h-0 flex-1 flex-col gap-4 px-5 pt-6 pb-5 transition-colors duration-500 ${speaking ? "animate-floor" : ""}`}
      style={{ borderColor: speaking ? character.color : undefined, ["--tint" as string]: character.color }}
    >
      <div className="flex h-24 shrink-0 items-center justify-center" style={{ opacity: speaking ? 1 : 0.4 }}>
        <VoiceVisualizer
          participantType="bot"
          barColor={character.color}
          barCount={24}
          barGap={6}
          barWidth={8}
          barMaxHeight={96}
          barOrigin="center"
          barLineCap="square"
          backgroundColor="transparent"
        />
      </div>

      <div className="shrink-0 border-y border-border py-3">
        <Heart value={heart} change={change} cells={24} words />
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto text-[13px] leading-[1.6]">
        <section className="space-y-1.5">
          <p className="flex items-center gap-2 text-muted-foreground">
            <Mic className="size-3.5" style={{ color: character.color }} aria-hidden />
            <span style={{ color: character.color }}>{name}</span> last said
          </p>
          {said ? (
            <>
              <p className="text-foreground">“{said.text}”</p>
              <EmotionRow
                label={said.emotion.label}
                intensity={said.emotion.intensity}
                confidence={said.emotion.confidence}
                backchannel={said.backchannel}
                cells={10}
              />
              <ActRow to="you" tag={said.acts[PLAYER]} cells={10} />
            </>
          ) : (
            <p className="text-muted-foreground/60">{character.tagline}</p>
          )}
        </section>

        <section className="space-y-1.5 border-t border-border pt-3">
          <p className="flex items-center gap-2 text-muted-foreground">
            <User className="size-3.5 text-client" aria-hidden />
            <span className="text-client">you</span> last said
          </p>
          {yours ? (
            <>
              <p className="text-foreground">“{yours.text}”</p>
              <EmotionRow
                label={yours.emotion.label}
                intensity={yours.emotion.intensity}
                confidence={yours.emotion.confidence}
                backchannel={yours.backchannel}
                cells={10}
              />
              <ActRow to={name} tag={yours.acts[character.id]} cells={10} />
            </>
          ) : (
            <p className="text-muted-foreground/60">nothing yet</p>
          )}
        </section>
      </div>
    </Panel>
  )
}
