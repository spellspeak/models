/** The wire shapes of the bot's server messages (server/director.py). */

/** How everyone feels about everyone: by who feels it, then about whom ("player" is you), 0 to 100. */
export type FeelingMatrix = Record<string, Record<string, number>>

/** The face a character shows (server/feelings.py). */
export interface Face {
  /** One of Tone's nine emotions. */
  mood: string
  intensity: "low" | "medium" | "high"
  /** rest: how they feel about you; reaction: to something said to or about them; expressed: in their own line. */
  why: "rest" | "reaction" | "expressed"
  /** Who caused a reaction, and with what act. */
  by: string | null
  act: string | null
}

export interface CastMessage {
  type: "cast"
  characters: { id: string; name: string; role: string }[]
  /** Which engine routes: the model, or the rules baseline when the model can't be loaded. */
  audience: { engine: "model" | "rules"; release: string; error: string | null }
  tone: { release: string }
  feelings: FeelingMatrix
  faces: Record<string, Face>
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
  plan?: PlanInfo
}

export interface ActTag {
  act: string
  intensity: "low" | "medium" | "high"
  confidence: number | null
  hostile: boolean
}

export interface FeelingChange {
  /** Whose feeling moved... */
  from: string
  /** ...about whom. */
  toward: string
  change: number
  value: number
  act: string
}

/** Tone's reading of a line (yours, or a character's as it starts playing), and what it moved. */
export type ToneMessage =
  | {
      type: "tone"
      /** The transcript line it read ("u3", "t12"). */
      line: string
      speaker: string
      to: string | null
      ms: number
      emotion: { label: string; intensity: "low" | "medium" | "high"; confidence: number | null }
      /** The act toward each person present, by id ("player" is you). */
      acts: Record<string, ActTag>
      backchannel: boolean
      changes: FeelingChange[]
      feelings: FeelingMatrix
      faces: Record<string, Face>
      at: number
      error?: undefined
    }
  | { type: "tone"; line: string; error: string }

/** A take: a line asked of a character (they're thinking until it plays). */
export interface TurnMessage {
  type: "turn"
  take: number
  speaker: string
  reason: string
  note: string | null
  /** The audio tag their line opens with, for their mood ("" for none). */
  tag: string
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

export type ServerMessage = CastMessage | AudienceMessage | ToneMessage | TurnMessage | VoicesMessage | LineMessage
