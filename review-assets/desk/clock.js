// This is a nominal rate grid. A native presentation clock is required for VFR accuracy.
const mediaPrecisionSeconds = 1e-6

export function frameBoundary(currentSeconds, stepSeconds, direction, durationSeconds = Infinity) {
  requireClock(currentSeconds, stepSeconds)
  if (direction !== -1 && direction !== 1) throw new RangeError('Frame direction must be -1 or 1')
  const last = Number.isFinite(durationSeconds) && durationSeconds > 0
    ? Math.max(0, Math.ceil(durationSeconds / stepSeconds) - 1)
    : Infinity
  const ordinal = Math.min(last, Math.max(0, Math.round(currentSeconds / stepSeconds) + direction))
  return {ordinal, exactSeconds: ordinal * stepSeconds, stepSeconds}
}

export function noteRange(currentSeconds, stepSeconds, stepped) {
  requireClock(currentSeconds, stepSeconds)
  // Only recover our last commanded boundary. Continuous/manual seeks retain their
  // own timestamp, and coarse browser readbacks do not masquerade as exact steps.
  const known = stepped?.stepSeconds === stepSeconds
    && Number.isInteger(stepped.ordinal) && stepped.ordinal >= 0
    && Number.isFinite(stepped.exactSeconds) && Number.isFinite(stepped.browserSeconds)
    && Math.abs(stepped.browserSeconds - stepped.exactSeconds) <= mediaPrecisionSeconds
    && Math.abs(currentSeconds - stepped.browserSeconds) <= mediaPrecisionSeconds
  return {
    startUs: Math.round((known ? stepped.exactSeconds : currentSeconds) * 1e6),
    endUs: Math.round((known ? (stepped.ordinal + 1) * stepSeconds : currentSeconds + stepSeconds) * 1e6),
  }
}

function requireClock(currentSeconds, stepSeconds) {
  if (!Number.isFinite(currentSeconds) || currentSeconds < 0 || !Number.isFinite(stepSeconds) || stepSeconds <= 0) {
    throw new RangeError('Finite nonnegative media time and positive frame duration required')
  }
}
