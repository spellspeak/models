import castJson from "@cast"

/** An agent, from ../characters.json, which the bot reads too. */
export interface Agent {
  id: string
  name: string
  role: string
  tagline: string
  /** What the user can see of them: Audience reads these as their card. */
  features: [string, string][]
  aliases: string[]
  /** CSS colour: their tint throughout the screen. */
  color: string
}

export const CAST: Agent[] = castJson.map((c) => ({
  id: c.id,
  name: c.name,
  role: c.role,
  tagline: c.tagline,
  features: Object.entries(c.features).filter((e): e is [string, string] => typeof e[1] === "string"),
  aliases: c.aliases,
  color: c.hex,
}))

export const BY_ID: Record<string, Agent> = Object.fromEntries(CAST.map((c) => [c.id, c]))

/** The runtime's reserved name for the user. */
export const USER = "player"

export function labelOf(id: string | null | undefined): string {
  if (!id) return "the room"
  if (id === USER) return "you"
  return BY_ID[id]?.name ?? id
}

export function colorOf(id: string | null | undefined): string {
  if (id && BY_ID[id]) return BY_ID[id].color
  if (id === USER) return "var(--color-client)"
  return "var(--color-muted-foreground)"
}
