import { create } from "zustand"

import { labelOf } from "@/cast"
import type { AudienceMessage, CastMessage, PlanInfo, ServerMessage } from "@/types"

const MAX_LINES = 200
const MAX_BLIPS = 7
/** How long the scene stays focused on a reading once the room has gone quiet. */
const SETTLE_MS = 4000

export interface Line {
  id: string
  speaker: string
  to: string[]
  text: string
  how: "said" | "together"
  interrupted: boolean
}

export interface Blip {
  n: number
  text: string
  color?: string
}

interface RoomState {
  engine: CastMessage["audience"] | null
  lines: Line[]
  /** Audience's latest reading: of what you're saying, or of your last whole turn. */
  reading: AudienceMessage | null
  /** The last whole turn's plan. */
  plan: PlanInfo | null
  /** Characters asked for a line that isn't playing yet, by id (their take). */
  thinking: Record<string, number>
  /** Characters whose voice is playing. */
  voices: string[]
  /** The room has been quiet a while since the last reading: the scene lets go of it. */
  settled: boolean
  /** The character you're looking at (sent to the bot as `look`). */
  looking: string | null
  userSpeaking: boolean
  heardFinals: string[]
  heardInterim: string
  blips: Blip[]
  receive: (message: ServerMessage) => void
  look: (id: string | null) => void
  setUserSpeaking: (on: boolean) => void
  hear: (text: string, final: boolean) => void
  reset: () => void
}

let blipCount = 0
let settleTimer: ReturnType<typeof setTimeout> | undefined

function percent(p: number | null | undefined) {
  return p === null || p === undefined ? "—" : `${Math.round(p * 100)}%`
}

/** The terminal line for a whole turn's reading and what came of it. */
function planBlip(m: AudienceMessage): Blip {
  const plan = m.plan
  const top = Object.entries(m.addressed).sort((a, b) => b[1] - a[1])[0]
  const odds = top ? `${labelOf(top[0]).toLowerCase()} ${percent(top[1])}` : "no reading"
  const who = plan?.speakers.map((s) => labelOf(s).toLowerCase()).join(", ") ?? ""
  const how =
    plan?.why === "unclear" ? "who, me?" : plan?.why === "chorus" ? "all at once" : plan?.together ? "at once" : plan?.speakers.length && plan.speakers.length > 1 ? "in turn" : plan?.why ?? ""
  return { n: ++blipCount, text: `audience ${m.ms.toFixed(1)}ms · ${odds} → ${who} (${how})` }
}

export const useRoom = create<RoomState>()((set, get) => {
  /** Once nothing is playing or being written, let the scene go back to rest after a while. */
  const schedule = () => {
    clearTimeout(settleTimer)
    const { voices, thinking, userSpeaking } = get()
    if (voices.length || Object.keys(thinking).length || userSpeaking) return
    settleTimer = setTimeout(() => set({ settled: true }), SETTLE_MS)
  }
  const blip = (b: Omit<Blip, "n"> | Blip) =>
    set((s) => ({ blips: [...s.blips, { n: ++blipCount, ...b }].slice(-MAX_BLIPS) }))

  return {
    engine: null,
    lines: [],
    reading: null,
    plan: null,
    thinking: {},
    voices: [],
    settled: true,
    looking: null,
    userSpeaking: false,
    heardFinals: [],
    heardInterim: "",
    blips: [],
    receive: (m) => {
      switch (m.type) {
        case "cast":
          set({ engine: m.audience })
          blip({ text: m.audience.engine === "model" ? `audience ${m.audience.release} loaded` : "audience: rules baseline (no model)" })
          break
        case "audience":
          if (m.final) {
            set({ reading: m, plan: m.plan ?? null, settled: false, heardFinals: [], heardInterim: "" })
            blip(planBlip(m))
          } else {
            set({ reading: m, settled: false })
          }
          break
        case "turn":
          set((s) => ({ thinking: { ...s.thinking, [m.speaker]: m.take }, settled: false }))
          if (m.reason === "handoff") blip({ text: `handoff → ${labelOf(m.speaker).toLowerCase()}` })
          break
        case "voices": {
          const was = get().voices
          set({ voices: m.speakers })
          for (const id of m.speakers.filter((v) => !was.includes(v))) blip({ text: `voice ▶ ${labelOf(id).toLowerCase()}` })
          break
        }
        case "line":
          set((s) => {
            const thinking = { ...s.thinking }
            for (const [who, take] of Object.entries(thinking)) if (m.id === `t${take}`) delete thinking[who]
            if (m.removed) return { thinking, lines: s.lines.filter((l) => l.id !== m.id) }
            const line: Line = { id: m.id, speaker: m.speaker, to: m.to, text: m.text, how: m.how, interrupted: m.interrupted }
            const at = s.lines.findIndex((l) => l.id === m.id)
            const lines = at >= 0 ? s.lines.map((l, i) => (i === at ? line : l)) : [...s.lines, line].slice(-MAX_LINES)
            return { thinking, lines }
          })
          break
      }
      schedule()
    },
    look: (id) => set({ looking: id }),
    setUserSpeaking: (on) => {
      set({ userSpeaking: on, ...(on ? { thinking: {}, settled: false } : {}) })
      schedule()
    },
    hear: (text, final) =>
      set((s) => (final ? { heardFinals: [...s.heardFinals, text], heardInterim: "" } : { heardInterim: text })),
    reset: () => {
      clearTimeout(settleTimer)
      set({
        lines: [],
        reading: null,
        plan: null,
        thinking: {},
        voices: [],
        settled: true,
        userSpeaking: false,
        heardFinals: [],
        heardInterim: "",
        blips: [],
      })
    },
  }
})

/**
 * How lit each character is, 0 to 1: speaking or about to, fully; otherwise Audience's chance that
 * your line is for them, while there's a reading in play. `focus` says whether the scene dims
 * everyone else at all.
 */
export function useLight(): { focus: boolean; lit: (id: string) => number } {
  const reading = useRoom((s) => s.reading)
  const voices = useRoom((s) => s.voices)
  const thinking = useRoom((s) => s.thinking)
  const settled = useRoom((s) => s.settled)
  const live = reading !== null && !settled
  const focus = voices.length > 0 || Object.keys(thinking).length > 0 || live
  const lit = (id: string) => {
    if (voices.includes(id)) return 1
    if (id in thinking) return 0.85
    return live ? (reading?.addressed[id] ?? 0) : 0
  }
  return { focus, lit }
}
