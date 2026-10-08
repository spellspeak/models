import castJson from "@cast"

/** A character, from ../characters.json, which the bot reads too. */
export interface Character {
  id: string
  name: string
  role: string
  tagline: string
  voice: string
  /** CSS colour: their tint throughout the screen. */
  color: string
}

export const CAST: Character[] = castJson.map((c) => ({
  id: c.id,
  name: c.name,
  role: c.role,
  tagline: c.tagline,
  voice: c.voice,
  color: c.hex,
}))

export const BY_ID: Record<string, Character> = Object.fromEntries(
  CAST.map((c) => [c.id, c])
)

/** The reserved name Tone uses for the player. */
export const PLAYER = "player"

export function labelOf(id: string | null | undefined): string {
  if (!id) return "the room"
  if (id === PLAYER) return "you"
  return BY_ID[id]?.name ?? id
}

export function colorOf(id: string | null | undefined): string {
  if (id && BY_ID[id]) return BY_ID[id].color
  if (id === PLAYER) return "var(--color-client)"
  return "var(--color-muted-foreground)"
}
