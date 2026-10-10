import type { DailyEventObjectTrack, DailyParticipant } from "@daily-co/daily-js"
import { usePipecatClient } from "@pipecat-ai/client-react"
import type { DailyTransport } from "@pipecat-ai/daily-transport"
import { useEffect, useRef, useState } from "react"

import { BY_ID, CAST } from "@/cast"

/** The characters' tracks from a remote participant (the bot) already in the call. */
function tracksOf(participant: DailyParticipant) {
  const tracks = participant.tracks as unknown as Record<
    string,
    { persistentTrack?: MediaStreamTrack; state?: string } | undefined
  >
  return CAST.flatMap((c) => {
    const t = tracks[c.id]
    return t?.persistentTrack && t.state === "playable" ? [[c.id, t.persistentTrack] as const] : []
  })
}

/**
 * Each character speaks on their own audio track: the bot publishes a Daily custom track per
 * character, named by their id (`audio_out_destinations` on the server), so several can talk at
 * once and the browser mixes them. Pipecat's `onTrackStarted` doesn't say which custom track a
 * track is, so this listens on the Daily call itself, where `track-started` names it, and plays
 * every character's track.
 */
export function CastAudio() {
  const client = usePipecatClient()
  const [tracks, setTracks] = useState<Record<string, MediaStreamTrack>>({})

  useEffect(() => {
    const call = (client?.transport as DailyTransport | undefined)?.dailyCallClient
    if (!call) return
    const put = (id: string, track: MediaStreamTrack | null) =>
      setTracks((all) => {
        const next = { ...all }
        if (track) next[id] = track
        else delete next[id]
        return next
      })
    const started = (ev: DailyEventObjectTrack) => {
      if (ev.participant?.local || ev.track.kind !== "audio") return
      if (ev.type && BY_ID[ev.type]) put(ev.type, ev.track)
    }
    const stopped = (ev: DailyEventObjectTrack) => {
      if (ev.participant?.local || !ev.type || !BY_ID[ev.type]) return
      put(ev.type, null)
    }
    const left = () => setTracks({})
    call.on("track-started", started)
    call.on("track-stopped", stopped)
    call.on("left-meeting", left)
    for (const p of Object.values(call.participants())) {
      if (!p.local) for (const [id, track] of tracksOf(p)) put(id, track)
    }
    return () => {
      call.off("track-started", started)
      call.off("track-stopped", stopped)
      call.off("left-meeting", left)
    }
  }, [client])

  return (
    <>
      {Object.entries(tracks).map(([id, track]) => (
        <TrackAudio key={id} track={track} />
      ))}
    </>
  )
}

function TrackAudio({ track }: { track: MediaStreamTrack }) {
  const ref = useRef<HTMLAudioElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.srcObject = new MediaStream([track])
    return () => {
      el.srcObject = null
    }
  }, [track])
  return <audio ref={ref} autoPlay />
}
