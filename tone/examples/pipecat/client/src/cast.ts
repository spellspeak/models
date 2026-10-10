import castJson from "@cast"

/** Small portraits, by character id: the face for a character with no mood sheet yet. */
const PORTRAITS = import.meta.glob<string>("./assets/portraits/*.webp", { eager: true, import: "default" })

/**
 * Mood sheets, by character id: `moods/<id>.webp`, nine faces in a 3 × 3 grid in Tone's order (MOODS),
 * 256 px each. `scripts/sheets.py` makes them from `portraits/<id>/<id>-<mood>.webp`.
 */
const SHEETS = import.meta.glob<string>("./assets/moods/*.webp", { eager: true, import: "default" })

/** Tone's nine emotions: every mood a face can show, in the order of a sheet. */
export const MOODS = ["neutral", "happy", "amused", "angry", "sad", "afraid", "surprised", "disgusted", "contemptuous"] as const
export type MoodName = (typeof MOODS)[number]

export function moodIndex(mood: string): number {
  return Math.max(0, MOODS.indexOf(mood as MoodName))
}

/** A character in the garage, from ../characters.json (which the bot reads too). */
export interface Character {
  id: string
  name: string
  role: string
  tagline: string
  /** CSS colour: their name, everywhere. */
  color: string
  /** Their mood sheet, or, without one, their portrait for every mood. */
  sheet?: string
  portrait: string
  /** How they feel about everyone at the start: the user ("player") and the others, 0 to 100. */
  feelings: Record<string, number>
  voiceName: string
}

/** Who's in the garage: every character marked `present`. */
export const CAST: Character[] = castJson
  .filter((c) => c.present)
  .map((c) => ({
    id: c.id,
    name: c.name,
    role: c.role,
    tagline: c.tagline,
    color: c.hex,
    sheet: SHEETS[`./assets/moods/${c.id}.webp`],
    portrait: PORTRAITS[`./assets/portraits/${c.id}.webp`],
    feelings: Object.fromEntries(Object.entries(c.feelings).filter((e): e is [string, number] => typeof e[1] === "number")),
    voiceName: c.voice_name,
  }))

export const BY_ID: Record<string, Character> = Object.fromEntries(CAST.map((c) => [c.id, c]))

/** The name both models reserve for the one playing: the user. */
export const USER = "player"

/** Who a character can feel something about: the user first, then whoever else is here. */
export function peopleFor(id: string): string[] {
  return [USER, ...CAST.map((c) => c.id).filter((o) => o !== id)]
}

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

/** The starting feelings, about the people here, before the bot says otherwise. */
export function startingFeelings(): Record<string, Record<string, number>> {
  return Object.fromEntries(
    CAST.map((c) => [c.id, Object.fromEntries(peopleFor(c.id).map((p) => [p, c.feelings[p] ?? 50]))])
  )
}

/** Every image the screen shows, to load and decode before the first frame. */
export function faceImages(): string[] {
  return CAST.map((c) => c.sheet ?? c.portrait)
}
