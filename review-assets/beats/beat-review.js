export const reviewColors = ['#365971', '#635074', '#3f7065', '#846440', '#774d65', '#587348']

// Derive state from the audio clock, so seeking and skipped frames stay in sync.
export function beatAtTime(beats, time) {
  let low = 0
  let high = beats.length
  while (low < high) {
    const middle = Math.floor((low + high) / 2)
    if (beats[middle].timeSec <= time + 0.000001) low = middle + 1
    else high = middle
  }
  return low - 1
}
