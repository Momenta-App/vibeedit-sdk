// Adapted from packages/app/src/pages/session/library-song-beatmap.tsx.
// Retain VibeEdit's millisecond precision, 25 ms replacement window and Beat shape.
export function addBeat(beats, timeSec) {
  const next = Number(timeSec.toFixed(3))
  return [...beats.filter((beat) => Math.abs(beat.timeSec - next) > 0.025), { timeSec: next, strength: 1 }]
    .sort((a, b) => a.timeSec - b.timeSec)
}

export function adjacentBeatTime(beats, playhead, direction, duration) {
  const times = beats.map((beat) => beat.timeSec).filter(Number.isFinite).sort((a, b) => a - b)
  if (direction === "previous") return [...times].reverse().find((time) => time < playhead - 0.0005) ?? 0
  return times.find((time) => time > playhead + 0.0005) ?? duration
}

export function formatTime(seconds) {
  const value = Math.max(0, seconds)
  const minutes = Math.floor(value / 60)
  return `${String(minutes).padStart(2, "0")}:${(value - minutes * 60).toFixed(3).padStart(6, "0")}`
}

export function normalizePeaks(peaks) {
  const ceiling = Math.max(0.000_001, ...peaks)
  return peaks.map((peak) => Math.min(1, peak / ceiling))
}
