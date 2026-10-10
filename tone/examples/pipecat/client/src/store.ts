import { create } from "zustand"

import { BY_ID, USER, startingFeelings } from "@/cast"
import { emotionSentiment, type Sentiment } from "@/sentiment"
import type { AudienceMessage, CastMessage, Face, FeelingMatrix, ServerMessage, ToneMessage } from "@/types"

const MAX_LINES = 200
/** How many of a feeling's past values its trend shows. */
const MAX_HISTORY = 24
/** How long a pulse stays on screen. */
const PULSE_MS = 1700

export type ToneReading = Extract<ToneMessage, { error?: undefined }>

export interface Line {
  id: string
  speaker: string
  to: string[]
  text: string
  how: "said" | "together"
  interrupted: boolean
  /** When it arrived (ms, this page's clock). */
  at: number
}

/**
 * A pulse over a character's face, played once: a line moved how they feel, or put a new mood on
 * their face. It takes the colour of the mood they're showing now (the face and the voice agree on
 * it), and carries how far their feeling moved, if it did.
 */
export interface Pulse {
  n: number
  who: string
  sentiment: Sentiment
  intensity: "low" | "medium" | "high"
  /** How far their feeling about `toward` moved (0: it didn't). */
  change: number
  toward: string | null
}

/** How long the models took over one line: Tone always, Audience too for the user's. */
export interface Timing {
  line: string
  speaker: string
  tone: number
  audience: number | null
}

interface RoomState {
  engine: CastMessage["audience"] | null
  toneRelease: string | null
  lines: Line[]
  /** Audience's latest reading: of what you're saying, or of your last whole turn. */
  reading: AudienceMessage | null
  /** Tone's reading of each line, by line id. */
  tones: Record<string, ToneReading>
  /** The latest line Tone read. */
  lastTone: ToneReading | null
  /** Every line's model times, oldest first. */
  timings: Timing[]
  feelings: FeelingMatrix
  /** Each feeling's past values, by "from:toward", oldest first. */
  history: Record<string, number[]>
  faces: Record<string, Face>
  /** Pulses playing now, by character. */
  pulses: Record<string, Pulse>
  /** The audio tag of each character's latest line. */
  tags: Record<string, string>
  /** Characters asked for a line that isn't playing yet, by id (their take). */
  thinking: Record<string, number>
  /** Characters whose voice is playing. */
  voices: string[]
  userSpeaking: boolean
  heardFinals: string[]
  heardInterim: string
  receive: (message: ServerMessage) => void
  setUserSpeaking: (on: boolean) => void
  hear: (text: string, final: boolean) => void
  reset: () => void
}

function historyOf(feelings: FeelingMatrix): Record<string, number[]> {
  const out: Record<string, number[]> = {}
  for (const [from, row] of Object.entries(feelings)) for (const [toward, v] of Object.entries(row)) out[`${from}:${toward}`] = [v]
  return out
}

let pulseCount = 0

/** Whether two faces are the same mood, for the same reason. */
function sameFace(a: Face | undefined, b: Face | undefined): boolean {
  return Boolean(a && b) && a!.mood === b!.mood && a!.intensity === b!.intensity && a!.why === b!.why && a!.by === b!.by && a!.act === b!.act
}

export const useRoom = create<RoomState>()((set, get) => {
  const pulse = (p: Omit<Pulse, "n">) => {
    const next = { ...p, n: ++pulseCount }
    set((s) => ({ pulses: { ...s.pulses, [p.who]: next } }))
    setTimeout(() => {
      set((s) => {
        if (s.pulses[p.who]?.n !== next.n) return {}
        const pulses = { ...s.pulses }
        delete pulses[p.who]
        return { pulses }
      })
    }, PULSE_MS)
  }

  const initial = startingFeelings()
  return {
    engine: null,
    toneRelease: null,
    lines: [],
    reading: null,
    tones: {},
    lastTone: null,
    timings: [],
    feelings: initial,
    history: historyOf(initial),
    faces: {},
    pulses: {},
    tags: {},
    thinking: {},
    voices: [],
    userSpeaking: false,
    heardFinals: [],
    heardInterim: "",
    receive: (m) => {
      switch (m.type) {
        case "cast":
          set({ engine: m.audience, toneRelease: m.tone.release, feelings: m.feelings, history: historyOf(m.feelings), faces: m.faces })
          break
        case "audience":
          if (m.final) set({ reading: m, heardFinals: [], heardInterim: "" })
          else set({ reading: m })
          break
        case "tone": {
          if (m.error !== undefined) break
          const before = get().faces
          set((s) => {
            const history = { ...s.history }
            for (const c of m.changes) {
              const key = `${c.from}:${c.toward}`
              history[key] = [...(history[key] ?? []), c.value].slice(-MAX_HISTORY)
            }
            // The user's line was read by Audience just before (its final reading); a character's wasn't.
            const audience = m.speaker === USER && s.reading?.final ? s.reading.ms : null
            const timings = [...s.timings, { line: m.line, speaker: m.speaker, tone: m.ms, audience }].slice(-MAX_LINES)
            return { tones: { ...s.tones, [m.line]: m }, lastTone: m, timings, feelings: m.feelings, faces: m.faces, history }
          })
          // A pulse for each character the line moved, or put a new mood on (not a mood fading back to rest).
          for (const [who, face] of Object.entries(m.faces)) {
            if (!BY_ID[who]) continue
            const moved = m.changes.find((c) => c.from === who)
            const newMood = face.why !== "rest" && !sameFace(before[who], face)
            if (!moved && !newMood) continue
            pulse({
              who,
              sentiment: emotionSentiment(face.mood),
              intensity: face.intensity,
              change: moved?.change ?? 0,
              toward: moved?.toward ?? null,
            })
          }
          break
        }
        case "turn":
          set((s) => ({ thinking: { ...s.thinking, [m.speaker]: m.take }, tags: { ...s.tags, [m.speaker]: m.tag } }))
          break
        case "voices":
          set({ voices: m.speakers })
          break
        case "line":
          set((s) => {
            const thinking = { ...s.thinking }
            for (const [who, take] of Object.entries(thinking)) if (m.id === `t${take}`) delete thinking[who]
            if (m.removed) return { thinking, lines: s.lines.filter((l) => l.id !== m.id) }
            const at = s.lines.findIndex((l) => l.id === m.id)
            const line: Line = {
              id: m.id,
              speaker: m.speaker,
              to: m.to,
              text: m.text,
              how: m.how,
              interrupted: m.interrupted,
              at: at >= 0 ? s.lines[at].at : Date.now(),
            }
            const lines = at >= 0 ? s.lines.map((l, i) => (i === at ? line : l)) : [...s.lines, line].slice(-MAX_LINES)
            return { thinking, lines }
          })
          break
      }
    },
    setUserSpeaking: (on) => set({ userSpeaking: on, ...(on ? { thinking: {} } : {}) }),
    hear: (text, final) =>
      set((s) => (final ? { heardFinals: [...s.heardFinals, text], heardInterim: "" } : { heardInterim: text })),
    reset: () => {
      const feelings = startingFeelings()
      set({
        lines: [],
        reading: null,
        tones: {},
        lastTone: null,
        timings: [],
        feelings,
        history: historyOf(feelings),
        faces: {},
        pulses: {},
        tags: {},
        thinking: {},
        voices: [],
        userSpeaking: false,
        heardFinals: [],
        heardInterim: "",
      })
    },
  }
})
