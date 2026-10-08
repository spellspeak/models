/** The wire shapes of the bot's server messages (server/director.py). */

export interface CastMessage {
  type: "cast"
  agents: { id: string; name: string; role: string; looks: string }[]
  /** Which engine routes: the model, or the rules baseline when the model files are missing. */
  audience: { engine: "model" | "rules"; release: string; error: string | null }
}

export interface RouteInfo {
  /** one agent, everyone, or unclear ("Who, me?") */
  kind: "one" | "group" | "unclear"
  reason: string
  /** Who answers, in order. */
  speakers: string[]
}

/** Audience's reading of a line: partial while you speak, final (with its route) once the turn ends. */
export interface AudienceMessage {
  type: "audience"
  final: boolean
  heard: string
  engine: "model" | "rules"
  ms: number
  /** The chance the line is for each agent, by id. */
  addressed: Record<string, number>
  unclear: number | null
  to_group: number | null
  error: string | null
  looking: string | null
  route?: RouteInfo
}

export interface TurnMessage {
  type: "turn"
  speaker: string
  reason: string
  note: string | null
  at: number
}

export interface SpeakerMessage {
  type: "speaker"
  /** Whose voice is playing, or null when it stops. */
  speaker: string | null
  at: number
}

export interface LineMessage {
  type: "line"
  /** "player" (you) or an agent id. */
  speaker: string
  /** Who it was for: agent ids, or ["player"]; [] when unclear. */
  to: string[]
  text: string
  interrupted: boolean
  at: number
}

export type ServerMessage = CastMessage | AudienceMessage | TurnMessage | SpeakerMessage | LineMessage
