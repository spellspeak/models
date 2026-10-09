/** The wire shapes of the bot's server messages (server/director.py). */

export interface CastMessage {
  type: "cast"
  characters: { id: string; name: string; role: string }[]
  /** Which engine routes: the model, or the rules baseline when the model can't be loaded. */
  audience: { engine: "model" | "rules"; release: string; error: string | null }
}

/** What the room did with a whole turn (server/audience.py, `plan`). */
export interface PlanInfo {
  /** chorus / group: everyone; unclear: "Who, me?"; several / addressed / fallback: one or more */
  why: "addressed" | "several" | "group" | "chorus" | "unclear" | "fallback"
  /** All at once, rather than in turn. */
  together: boolean
  /** Who answers, in order. */
  speakers: string[]
  /** Who the line was for ([]: unclear). */
  addressed: string[]
}

/** Audience's reading of a line: partial while you speak, final (with its plan) once the turn ends. */
export interface AudienceMessage {
  type: "audience"
  final: boolean
  heard: string
  engine: "model" | "rules"
  ms: number
  /** The chance the line is for each character, by id. */
  addressed: Record<string, number>
  unclear: number | null
  to_group: number | null
  error: string | null
  looking: string | null
  plan?: PlanInfo
}

/** A take: a line asked of a character (they're thinking until it plays). */
export interface TurnMessage {
  type: "turn"
  take: number
  speaker: string
  reason: string
  note: string | null
  at: number
}

/** Whose voices are playing now. */
export interface VoicesMessage {
  type: "voices"
  speakers: string[]
  at: number
}

/** A line of the transcript: sent as it starts playing, again if it's cut short, or removed. */
export type LineMessage =
  | {
      type: "line"
      id: string
      /** "player" (you) or a character id. */
      speaker: string
      /** Who it was for: character ids, or ["player"]; [] when unclear. */
      to: string[]
      text: string
      how: "said" | "together"
      interrupted: boolean
      at: number
      removed?: undefined
    }
  | { type: "line"; id: string; removed: true }

export type ServerMessage = CastMessage | AudienceMessage | TurnMessage | VoicesMessage | LineMessage
