/** The wire shape of the bot's server messages (server/bot.py, `LineTagger.tag`). */

export interface ActTag {
  act: string
  intensity: "low" | "medium" | "high"
  /** The chance the tag is right (hostile tags: that the line is hostile toward them). */
  confidence: number | null
  hostile: boolean
}

/** Whether a line is sarcastic: it means something other than what its words say (Tone rc4 on). */
export interface SarcasmTag {
  sarcastic: boolean
  /** The chance the line is sarcastic. */
  probability: number | null
}

export interface LineMessage {
  type: "line"
  id: number
  /** "player" or a character id. */
  speaker: string
  /** Who it was said to: a character id, "player", or null for the room. */
  to: string | null
  text: string
  emotion: { label: string; intensity: "low" | "medium" | "high"; confidence: number | null }
  /** The act toward each other person present, by id. */
  acts: Record<string, ActTag>
  backchannel: boolean
  /** Null with a release before rc4, which has no sarcasm output. */
  sarcasm: SarcasmTag | null
  /** Every character's heart, 0 to 100, after this line. */
  hearts: Record<string, number>
  /** The hearts this line moved, by id, and by how much. */
  changes: Record<string, number>
  latency_ms: number
}
