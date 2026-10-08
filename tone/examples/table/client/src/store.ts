import { create } from "zustand"

import { CAST } from "@/cast"
import type { LineMessage } from "@/types"

const MAX_LINES = 200
const HEARTS_KEY = "tone-table-hearts"

/** Hearts remembered between sessions, in this browser. Missing or blocked storage means 50 each. */
function loadHearts(): Record<string, number> {
  const hearts = Object.fromEntries(CAST.map((c) => [c.id, 50]))
  try {
    const saved = JSON.parse(localStorage.getItem(HEARTS_KEY) ?? "{}") as Record<string, unknown>
    for (const c of CAST) {
      const v = saved[c.id]
      if (typeof v === "number" && v >= 0 && v <= 100) hearts[c.id] = Math.round(v)
    }
  } catch {
    // storage unavailable: start fresh
  }
  return hearts
}

function saveHearts(hearts: Record<string, number>) {
  try {
    localStorage.setItem(HEARTS_KEY, JSON.stringify(hearts))
  } catch {
    // storage unavailable: hearts last for the page only
  }
}

interface TableState {
  /** The character chosen on the intro screen. */
  picked: string | null
  lines: LineMessage[]
  /** Every character's heart, 0 to 100: kept between sessions. */
  hearts: Record<string, number>
  botSpeaking: boolean
  userSpeaking: boolean
  /** What you have said so far this turn: final segments and the live partial. */
  heardFinals: string[]
  heardInterim: string
  pick: (id: string) => void
  receive: (message: LineMessage) => void
  setBotSpeaking: (on: boolean) => void
  setUserSpeaking: (on: boolean) => void
  hear: (text: string, final: boolean) => void
  /** A new session: the lines clear, the hearts stay. */
  reset: () => void
}

export const useTable = create<TableState>()((set) => ({
  picked: null,
  lines: [],
  hearts: loadHearts(),
  botSpeaking: false,
  userSpeaking: false,
  heardFinals: [],
  heardInterim: "",
  pick: (id) => set({ picked: id }),
  receive: (message) =>
    set((s) => {
      const hearts = { ...s.hearts, ...message.hearts }
      saveHearts(hearts)
      return {
        lines: [...s.lines, message].slice(-MAX_LINES),
        hearts,
        ...(message.speaker === "player" ? { heardFinals: [], heardInterim: "" } : {}),
      }
    }),
  setBotSpeaking: (on) => set({ botSpeaking: on }),
  setUserSpeaking: (on) => set({ userSpeaking: on }),
  hear: (text, final) =>
    set((s) =>
      final
        ? { heardFinals: [...s.heardFinals, text], heardInterim: "" }
        : { heardInterim: text }
    ),
  reset: () =>
    set({ lines: [], botSpeaking: false, userSpeaking: false, heardFinals: [], heardInterim: "" }),
}))

/** The latest line by a speaker. */
export function lastLineBy(lines: LineMessage[], speaker: string): LineMessage | null {
  for (let i = lines.length - 1; i >= 0; i--) if (lines[i].speaker === speaker) return lines[i]
  return null
}
