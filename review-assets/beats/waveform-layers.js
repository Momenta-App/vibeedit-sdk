// Layer names and colors match VibeEdit's LibrarySongBeatmap.
export const layers = [
  { id: 'volume', label: 'Volume', color: '#34d399', range: 'Full mix', filters: [] },

]

// Max pooling preserves short transients at every zoom level.
export function peakLevels(peaks) {
  const levels = [peaks]
  while (levels.at(-1).length > 2048) {
    const previous = levels.at(-1)
    const next = Array.from({ length: Math.ceil(previous.length / 4) }, (_, index) =>
      Math.max(...previous.slice(index * 4, index * 4 + 4)))
    levels.push(next)
  }
  return levels
}

export function rulerStep(seconds, width) {
  return [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60]
    .find((step) => step / seconds * width >= 80) ?? 120
}
