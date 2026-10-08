import { create } from "zustand"

import type { AudienceMessage, CastMessage, LineMessage, ServerMessage } from "@/types"

const MAX_LINES = 200

interface RoomState {
  engine: CastMessage["audience"] | null
  lines: LineMessage[]
  /** Audience's latest reading: of what you're saying, or of your last whole turn. */
  reading: AudienceMessage | null
  /** The last whole turn's reading, with its route. */
  routed: AudienceMessage | null
  /** The agent whose turn it is, and whose voice is playing. */
  active: string | null
  speaking: string | null
  /** The agent you're looking at (sent to the bot as `look`). */
  looking: string | null
  userSpeaking: boolean
  heardFinals: string[]
  heardInterim: string
  receive: (message: ServerMessage) => void
  look: (id: string | null) => void
  setUserSpeaking: (on: boolean) => void
  hear: (text: string, final: boolean) => void
  reset: () => void
}

export const useRoom = create<RoomState>()((set) => ({
  engine: null,
  lines: [],
  reading: null,
  routed: null,
  active: null,
  speaking: null,
  looking: null,
  userSpeaking: false,
  heardFinals: [],
  heardInterim: "",
  receive: (m) =>
    set((s) => {
      switch (m.type) {
        case "cast":
          return { engine: m.audience }
        case "audience":
          if (!m.final) return { reading: m }
          return { reading: m, routed: m, heardFinals: [], heardInterim: "" }
        case "turn":
          return { active: m.speaker }
        case "speaker":
          return { speaking: m.speaker }
        case "line":
          return { lines: [...s.lines, m].slice(-MAX_LINES) }
        default:
          return {}
      }
    }),
  look: (id) => set({ looking: id }),
  setUserSpeaking: (on) => set({ userSpeaking: on }),
  hear: (text, final) =>
    set((s) =>
      final ? { heardFinals: [...s.heardFinals, text], heardInterim: "" } : { heardInterim: text }
    ),
  reset: () =>
    set({
      lines: [],
      reading: null,
      routed: null,
      active: null,
      speaking: null,
      userSpeaking: false,
      heardFinals: [],
      heardInterim: "",
    }),
}))
