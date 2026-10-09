import castJson from "@cast"

import geometry from "@/scene-geometry.json"

/** Small portraits, by character id (made from the full-size ones in assets/). */
const PORTRAITS = import.meta.glob<string>("./assets/portraits/*.webp", { eager: true, import: "default" })

/** A character, from ../characters.json (which the bot reads too), placed in the scene. */
export interface Character {
  id: string
  name: string
  role: string
  tagline: string
  /** What the user can see of them: Audience reads these as their card. */
  features: [string, string][]
  /** CSS colour: their tint throughout the screen. */
  color: string
  portrait: string
  /** Their outline in base.png, in its 2048 px coordinates (scripts/masks/polygons.py). */
  outline: [number, number][]
  /** Its bounding box: [x0, y0, x1, y1]. */
  box: [number, number, number, number]
  /** Depth: higher stands in front (Atlas is behind Bruno). */
  z: number
}

const GEOMETRY = geometry as unknown as Record<
  string,
  { outline: [number, number][]; box: [number, number, number, number]; z: number }
>

export const CAST: Character[] = castJson.map((c) => ({
  id: c.id,
  name: c.name,
  role: c.role,
  tagline: c.tagline,
  features: Object.entries(c.features).filter((e): e is [string, string] => typeof e[1] === "string"),
  color: c.hex,
  portrait: PORTRAITS[`./assets/portraits/${c.id}.webp`],
  outline: GEOMETRY[c.id]?.outline ?? [],
  box: GEOMETRY[c.id]?.box ?? [0, 0, 0, 0],
  z: GEOMETRY[c.id]?.z ?? 0,
}))

/** The cast back to front, the order their outlines are drawn in. */
export const BY_DEPTH: Character[] = [...CAST].sort((a, b) => a.z - b.z)

export const BY_ID: Record<string, Character> = Object.fromEntries(CAST.map((c) => [c.id, c]))

/** SpellSpeak Audience's reserved name for the one speaking: the user. */
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
