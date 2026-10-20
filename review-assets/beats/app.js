import { session, mutate } from './session.js'
import { addBeat, adjacentBeatTime, formatTime } from './beatmap.js'
import { layers, peakLevels, rulerStep } from './waveform-layers.js'
import { beatAtTime, reviewColors } from './beat-review.js'

const $ = (id) => document.getElementById(id)
const audio = $('audio')
const scroll = $('wave-scroll')
const canvas = $('wave')
const overview = $('overview')
const reviewSeek = $('review-seek')
const state = await session()
let revision = state.revision
let saving = Promise.resolve()
let saveFailed = false
const storageKey = `vibeedit:beatmap:${state.source.sha256}:v1`
audio.src = `/media/${state.source.id}`
$('track-name').textContent = 'Beat review'
$('save-status').textContent = 'Saved to project'
$('source-name').textContent = state.source.id
const source = state.source.sha256
const undoStack = []
const redoStack = []
let beats = state.beats
let selected = null
let waveform
let zoom = 1
let drag = null
let toastTimer
let storageAvailable = true
let lastRender = 0
let duration = state.source.durationUs / 1e6
let activeLayers = ['volume']
let layout = 'stacked'
let gain = 1
let hoverTime = null
let reviewing = false
let lastReviewBeat = null
let reviewScrubbing = false
let resumeAfterScrub = false

function setReview(open) {
  reviewing = open
  window.history.replaceState(null, '', open ? '#review' : window.location.pathname + window.location.search)
  $('review-screen').hidden = !open
  $('editor-workspace').hidden = open
  $('review-toggle').setAttribute('aria-pressed', String(open))
  $('review-toggle').textContent = open ? 'Waveforms' : 'Review beats'
  $('mark').disabled = open
  toggleBeats(false)
  lastReviewBeat = null
  drawReview()
  if (!open) draw()
}

function drawReview() {
  if (!reviewing) return
  const index = beatAtTime(beats, audio.currentTime)
  if (lastReviewBeat !== index) {
    $('review-screen').style.background = index < 0 ? '#273a36' : reviewColors[index % reviewColors.length]
    $('review-number').textContent = index < 0 ? '—' : String(index + 1).padStart(2, '0')
    $('review-caption').textContent = !beats.length ? 'NO BEATS YET' : index < 0 ? 'WAITING FOR FIRST BEAT' : `BEAT ${index + 1} OF ${beats.length}`
    $('review-detail').textContent = !beats.length ? 'Return to waveforms to mark beats, or import your saved JSON.' : index < 0 ? `First beat at ${formatTime(beats[0].timeSec)}` : `Marked at ${formatTime(beats[index].timeSec)}`
    lastReviewBeat = index
  }
  $('review-time').textContent = formatTime(audio.currentTime)
  $('current-time').textContent = formatTime(audio.currentTime)
  reviewSeek.max = duration
  reviewSeek.value = audio.currentTime
  reviewSeek.setAttribute('aria-valuetext', formatTime(audio.currentTime))
  reviewSeek.style.setProperty('--progress', `${audio.currentTime / duration * 100}%`)
  $('review-position').textContent = formatTime(audio.currentTime)
  $('review-duration').textContent = formatTime(duration)
  $('review-start').disabled = !beats.length
  $('review-previous').disabled = !beats.length
  $('review-next').disabled = !beats.length
}

function renderLayers() {
  $('layer-options').replaceChildren(...layers.map((layer) => {
    const button = document.createElement('button')
    button.className = 'layer-toggle'
    button.style.setProperty('--layer-color', layer.color)
    button.setAttribute('aria-pressed', String(activeLayers.includes(layer.id)))
    button.title = `${layer.label} · ${layer.range}`
    button.innerHTML = `<i></i>${layer.label}<small>${layer.range}</small>`
    button.addEventListener('click', () => {
      if (activeLayers.includes(layer.id) && activeLayers.length === 1) return notify('Keep at least one waveform visible.')
      activeLayers = activeLayers.includes(layer.id) ? activeLayers.filter((id) => id !== layer.id) : [...activeLayers, layer.id]
      renderLayers(); draw()
    })
    return button
  }))
}

function notify(message) {
  $('toast').textContent = message
  $('toast').classList.add('show')
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => $('toast').classList.remove('show'), 2200)
}

function validateBeats(value) {
  const items = Array.isArray(value) ? value : value?.beats
  if (!Array.isArray(items)) throw new Error('Choose a beat map JSON file containing a beats array.')
  return items.reduce((result, item) => {
    const time = typeof item === 'number' ? item : item?.timeSec
    if (typeof time !== 'number' || !Number.isFinite(time) || time < 0 || time > duration) {
      throw new Error('Every beat needs a valid timeSec within this song.')
    }
    return addBeat(result, time)
  }, [])
}

function save() {
  const savedBeats = beats.map(beat => ({...beat}))
  localStorage.setItem(storageKey, JSON.stringify({ beats: savedBeats, source, draft: true }))
  $('save-status').textContent = 'Saving to project…'
  saving = saving.then(async () => {
    if (saveFailed) return
    const result = await mutate({ operationId: crypto.randomUUID(), expectedRevision: revision, author: 'human:beat-review', sourceId: state.source.id, sourceSha256: source, domain: 'beats', action: 'set', targetId: 'beatmap', payload: {beats: savedBeats} })
    revision = result.event.revision
    $('save-status').textContent = 'Saved to project'
    localStorage.removeItem(storageKey)
  }).catch(error => {
    saveFailed = true
    $('save-status').textContent = 'Unsaved draft — export before reload'
    notify(error.message + '. Export your draft, reload the current project, then import it to reconcile.')
  })
}

function remember() {
  undoStack.push(beats.map((beat) => ({ ...beat })))
  if (undoStack.length > 200) undoStack.shift()
  redoStack.length = 0
}

function changed() {
  save()
  renderList()
  draw()
}

function mark(time = audio.currentTime) {
  remember()
  beats = addBeat(beats, Math.max(0, Math.min(duration, time)))
  selected = Number(Math.max(0, Math.min(duration, time)).toFixed(3))
  changed()
  const row = $('beat-list').querySelector('.selected')
  row?.scrollIntoView({ block: 'nearest' })
  notify(`Beat ${beats.findIndex((beat) => beat.timeSec === selected) + 1} added · ${formatTime(selected)}`)
}

function remove(time) {
  if (!beats.some((beat) => beat.timeSec === time)) return
  remember()
  beats = beats.filter((beat) => beat.timeSec !== time)
  if (selected === time) selected = null
  changed()
}

function setSelected(time) {
  selected = time
  seek(time)
  renderList()
}

function seek(time) {
  audio.currentTime = Math.max(0, Math.min(duration, time))
  if ($('follow').checked) reveal(audio.currentTime)
  draw()
}

function reveal(time) {
  const x = time / duration * timelineWidth()
  if (x < scroll.scrollLeft + 20 || x > scroll.scrollLeft + scroll.clientWidth - 40) {
    scroll.scrollLeft = Math.max(0, x - scroll.clientWidth * 0.2)
  }
}

async function togglePlay() {
  if (!audio.paused) return audio.pause()
  if (audio.currentTime >= duration - 0.01) seek(0)
  await audio.play().catch(() => {
    $('error').textContent = 'Audio could not play. Check your connection, then press Play again.'
    $('error').hidden = false
  })
}

function history(direction) {
  const from = direction === 'undo' ? undoStack : redoStack
  const to = direction === 'undo' ? redoStack : undoStack
  if (!from.length) return
  to.push(beats.map((beat) => ({ ...beat })))
  beats = from.pop()
  selected = null
  changed()
  notify(direction === 'undo' ? 'Undone' : 'Redone')
}

function nudge(delta) {
  if (selected === null) return
  remember()
  const next = Math.max(0, Math.min(duration, selected + delta))
  beats = addBeat(beats.filter((beat) => beat.timeSec !== selected), next)
  selected = Number(next.toFixed(3))
  seek(selected)
  changed()
}

function renderList() {
  $('beat-count').textContent = beats.length
  $('drawer-count').textContent = beats.length
  $('empty').hidden = beats.length > 0
  $('clear').disabled = !beats.length
  $('undo').disabled = !undoStack.length
  $('redo').disabled = !redoStack.length
  $('previous').disabled = !beats.length
  $('next').disabled = !beats.length
  $('list-status').textContent = beats.length ? `${beats.length} beat${beats.length === 1 ? '' : 's'} · ${storageAvailable ? 'autosaved locally' : 'export to save'}` : 'Ready when you are'
  $('beat-list').replaceChildren(...beats.map((beat, index) => {
    const row = document.createElement('div')
    row.className = `beat-row${selected === beat.timeSec ? ' selected' : ''}`
    const number = document.createElement('span')
    number.className = 'beat-number'
    number.textContent = String(index + 1).padStart(2, '0')
    const time = document.createElement('button')
    time.className = 'beat-time'
    time.textContent = formatTime(beat.timeSec)
    time.setAttribute('aria-label', `Seek to beat ${index + 1} at ${formatTime(beat.timeSec)}`)
    const removeButton = document.createElement('button')
    removeButton.className = 'remove-beat'
    removeButton.textContent = '×'
    removeButton.setAttribute('aria-label', `Delete beat ${index + 1}`)
    removeButton.addEventListener('click', (event) => { event.stopPropagation(); remove(beat.timeSec) })
    row.addEventListener('click', () => setSelected(beat.timeSec))
    row.append(number, time, removeButton)
    return row
  }))
  const index = beats.findIndex((beat) => beat.timeSec === selected)
  $('selected-panel').hidden = index < 0
  $('selected-label').textContent = `Beat ${index + 1} · ${formatTime(selected ?? 0)}`
}

function timelineWidth() { return scroll.clientWidth * zoom }
function timeAt(event) { return Math.max(0, Math.min(duration, (event.clientX - canvas.getBoundingClientRect().left + scroll.scrollLeft) / timelineWidth() * duration)) }

function setZoom(value, anchorTime = audio.currentTime, anchorX) {
  const anchor = anchorX ?? Math.max(0, Math.min(scroll.clientWidth, anchorTime / duration * timelineWidth() - scroll.scrollLeft))
  zoom = Math.max(1, Math.min(256, value))
  $('zoom').value = Math.log2(zoom)
  $('zoom-label').textContent = `${Number(zoom.toFixed(1))}×`
  $('wave-content').style.width = `${timelineWidth()}px`
  scroll.scrollLeft = Math.max(0, anchorTime / duration * timelineWidth() - anchor)
  draw()
}

function contextFor(element, width, height) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  if (element.width !== Math.round(width * dpr) || element.height !== Math.round(height * dpr)) {
    element.width = Math.round(width * dpr)
    element.height = Math.round(height * dpr)
  }
  element.style.width = `${width}px`
  element.style.height = `${height}px`
  const ctx = element.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)
  return ctx
}

function drawPeaks(ctx, levels, width, center, amplitude, color, start = 0, end = 1) {
  if (!levels?.length) return
  const level = Math.max(0, Math.min(levels.length - 1, Math.floor(Math.log(Math.max(1, (end - start) * levels[0].length / width)) / Math.log(4))))
  const peaks = levels[level]
  ctx.fillStyle = color
  for (let x = 0; x < width; x += 1) {
    const from = Math.floor((start + x / width * (end - start)) * peaks.length)
    const to = Math.max(from + 1, Math.ceil((start + (x + 1) / width * (end - start)) * peaks.length))
    let peak = 0
    for (let p = from; p < to && p < peaks.length; p++) peak = Math.max(peak, peaks[p] ?? 0)
    const height = Math.max(1, peak * amplitude)
    ctx.fillRect(x, center - height, 1, height * 2)
  }
}

function draw() {
  if (reviewing) return drawReview()
  const width = scroll.clientWidth
  const height = Math.max(100, scroll.clientHeight - 12)
  const fullWidth = timelineWidth()
  canvas.style.position = 'sticky'
  canvas.style.left = '0'
  const ctx = contextFor(canvas, width, height)
  const start = scroll.scrollLeft / fullWidth
  const end = Math.min(1, (scroll.scrollLeft + width) / fullWidth)
  const xFor = (time) => time / duration * fullWidth - scroll.scrollLeft
  ctx.fillStyle = '#1e2823'
  ctx.fillRect(0, 0, width, height)
  const step = rulerStep(duration / zoom, width)
  const from = Math.floor(start * duration / step) * step
  ctx.font = '9px ui-monospace, monospace'
  for (let time = from; time <= end * duration; time += step) {
    const x = xFor(time)
    const digits = step < 0.01 ? 3 : step < 0.1 ? 2 : step < 1 ? 1 : 0
    const label = `${Math.floor(time / 60)}:${(time % 60).toFixed(digits).padStart(digits ? digits + 3 : 2, '0')}`
    ctx.fillStyle = '#9baea0'; ctx.fillText(label, x + 7, 18)
    ctx.fillStyle = '#ffffff07'; ctx.fillRect(x, 29, 1, height - 29)
  }
  ctx.fillStyle = '#ffffff08'; ctx.fillRect(0, 29, width, 1)
  const shown = layers.filter((layer) => activeLayers.includes(layer.id))
  const laneHeight = (height - 30) / (layout === 'stacked' ? shown.length : 1)
  shown.forEach((layer, index) => {
    const top = 30 + (layout === 'stacked' ? index * laneHeight : 0)
    ctx.save(); ctx.beginPath(); ctx.rect(0, top + 1, width, laneHeight - 2); ctx.clip()
    ctx.globalAlpha = layout === 'overlay' && shown.length > 1 ? 0.55 : 0.9
    const ratio = duration / (waveform?.durationSec ?? duration)
    drawPeaks(ctx, waveform?.levels[layer.id], width, top + laneHeight / 2, (laneHeight / 2 - 12) * gain, layer.color, start * ratio, end * ratio)
    ctx.restore()
    if (layout === 'stacked') {
      ctx.fillStyle = '#ffffff0b'; ctx.fillRect(0, top, width, 1)
      ctx.fillStyle = '#142019de'; ctx.fillRect(7, top + 5, 170, 18)
      ctx.fillStyle = layer.color; ctx.font = '10px ui-monospace, monospace'; ctx.fillText(`${layer.label.toUpperCase()} · ${layer.range}`, 12, top + 17)
    }
  })
  if (!waveform) { ctx.fillStyle = '#b2c5a1'; ctx.font = '12px sans-serif'; ctx.fillText('Loading high-resolution waveforms…', 24, 90) }
  if (hoverTime !== null && !drag) {
    const x = xFor(hoverTime)
    ctx.fillStyle = '#ffffff30'; ctx.fillRect(x, 29, 1, height - 29)
    const labelX = Math.min(width - 100, Math.max(0, x + 8))
    ctx.fillStyle = '#101b15'; ctx.fillRect(labelX, height - 28, 95, 22)
    ctx.fillStyle = '#e2eddb'; ctx.font = '11px ui-monospace, monospace'; ctx.fillText(formatTime(hoverTime), labelX + 6, height - 13)
  }
  beats.forEach((beat, index) => {
    const x = xFor(beat.timeSec)
    if (x < -20 || x > width + 20) return
    const active = selected === beat.timeSec
    ctx.fillStyle = active ? '#f5ca7e' : '#e4a778'
    ctx.fillRect(x - (active ? 1 : 0), 30, active ? 2 : 1, height - 30)
    ctx.beginPath(); ctx.moveTo(x - 5, 30); ctx.lineTo(x + 5, 30); ctx.lineTo(x + 5, 42); ctx.lineTo(x, 47); ctx.lineTo(x - 5, 42); ctx.closePath(); ctx.fill()
    ctx.font = '9px ui-monospace, monospace'; ctx.fillText(String(index + 1), x + 7, height - 10)
  })
  const playX = xFor(audio.currentTime)
  ctx.fillStyle = '#f0f5e5'; ctx.fillRect(playX, 27, 1.5, height - 27)
  ctx.beginPath(); ctx.moveTo(playX - 4, 24); ctx.lineTo(playX + 5, 24); ctx.lineTo(playX, 30); ctx.closePath(); ctx.fill()
  const ow = Math.max(1, overview.parentElement.clientWidth - 24)
  const oc = contextFor(overview, ow, 49)
  drawPeaks(oc, waveform?.levels.volume, ow, 25, 18, '#9aaa8d')
  oc.fillStyle = '#47794a15'; oc.fillRect(start * ow, 1, (end - start) * ow, 47)
  oc.strokeStyle = '#7e9765'; oc.lineWidth = 1; oc.strokeRect(start * ow + 0.5, 1.5, Math.max(1, (end - start) * ow - 1), 46)
  beats.forEach((beat) => { oc.fillStyle = '#ad7754'; oc.fillRect(beat.timeSec / duration * ow, 5, 1, 40) })
  oc.fillStyle = '#355936'; oc.fillRect(audio.currentTime / duration * ow, 1, 2, 47)
  $('current-time').textContent = formatTime(audio.currentTime)
  $('visible-range').textContent = `${formatTime(start * duration)} — ${formatTime(end * duration)}`
  $('pixel-resolution').textContent = `${((end - start) * duration).toFixed(3)} s visible · ${(duration / fullWidth * 1000).toFixed(2)} ms / pixel`
}

$('play').addEventListener('click', togglePlay)
$('review-toggle').addEventListener('click', () => setReview(!reviewing))
$('review-back').addEventListener('click', () => setReview(false))
reviewSeek.addEventListener('input', () => seek(Number(reviewSeek.value)))
reviewSeek.addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return
  reviewScrubbing = true
  resumeAfterScrub = !audio.paused
  audio.pause()
})
function finishReviewScrub() {
  if (!reviewScrubbing) return
  reviewScrubbing = false
  if (resumeAfterScrub && audio.currentTime < duration) void togglePlay()
  resumeAfterScrub = false
}
window.addEventListener('pointerup', finishReviewScrub)
window.addEventListener('pointercancel', finishReviewScrub)
reviewSeek.addEventListener('wheel', (event) => {
  const movement = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
  if (!movement) return
  event.preventDefault()
  seek(audio.currentTime + Math.sign(movement) * (event.shiftKey ? 0.01 : 0.25))
}, { passive: false })
$('review-start').addEventListener('click', () => {
  if (!beats.length) return
  seek(Math.max(0, beats[0].timeSec - 1))
  if (audio.paused) void togglePlay()
})
$('review-previous').addEventListener('click', () => { audio.pause(); seek(adjacentBeatTime(beats, audio.currentTime, 'previous', duration)) })
$('review-next').addEventListener('click', () => { audio.pause(); seek(adjacentBeatTime(beats, audio.currentTime, 'next', duration)) })
$('restart').addEventListener('click', () => seek(0))
$('mark').addEventListener('click', () => mark())
$('speed').addEventListener('change', () => { audio.playbackRate = Number($('speed').value) })
$('undo').addEventListener('click', () => history('undo'))
$('redo').addEventListener('click', () => history('redo'))
$('clear').addEventListener('click', () => {
  if (!beats.length) return
  remember(); beats = []; selected = null; changed(); notify('All beats cleared. Press ⌘Z to undo.')
})
$('delete-selected').addEventListener('click', () => { if (selected !== null) remove(selected) })
$('nudge-back').addEventListener('click', () => nudge(-0.001))
$('nudge-forward').addEventListener('click', () => nudge(0.001))
$('step-back').addEventListener('click', () => { audio.pause(); seek(audio.currentTime - 0.001) })
$('step-forward').addEventListener('click', () => { audio.pause(); seek(audio.currentTime + 0.001) })
$('previous').addEventListener('click', () => seek(adjacentBeatTime(beats, audio.currentTime, 'previous', duration)))
$('next').addEventListener('click', () => seek(adjacentBeatTime(beats, audio.currentTime, 'next', duration)))
$('zoom').addEventListener('input', () => setZoom(2 ** Number($('zoom').value)))
$('zoom-in').addEventListener('click', () => setZoom(zoom * 2))
$('zoom-out').addEventListener('click', () => setZoom(zoom / 2))
$('fit').addEventListener('click', () => setZoom(1))
$('follow').addEventListener('change', () => { if ($('follow').checked) reveal(audio.currentTime) })
overview.addEventListener('click', (event) => seek((event.clientX - overview.getBoundingClientRect().left) / overview.clientWidth * duration))
scroll.addEventListener('scroll', draw, { passive: true })
scroll.addEventListener('wheel', (event) => {
  event.preventDefault()
  if (event.ctrlKey || event.metaKey) {
    const x = event.clientX - canvas.getBoundingClientRect().left
    setZoom(zoom * Math.exp(-event.deltaY * 0.012), timeAt(event), x)
    return
  }
  scroll.scrollLeft += Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
}, { passive: false })
$('all-layers').addEventListener('click', () => { activeLayers = layers.map((layer) => layer.id); renderLayers(); draw() })
$('volume-only').addEventListener('click', () => { activeLayers = ['volume']; renderLayers(); draw() })
$('wave-layout').addEventListener('change', () => { layout = $('wave-layout').value; draw() })
$('gain').addEventListener('input', () => { gain = Number($('gain').value); $('gain-label').textContent = `${gain}×`; draw() })
function toggleBeats(open) { $('beats-panel').hidden = !open; $('toggle-beats').setAttribute('aria-expanded', String(open)) }
$('toggle-beats').addEventListener('click', () => toggleBeats($('beats-panel').hidden))
$('close-beats').addEventListener('click', () => toggleBeats(false))
canvas.addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return
  const time = timeAt(event)
  const nearest = [...beats].sort((a, b) => Math.abs(a.timeSec - time) - Math.abs(b.timeSec - time))[0]
  if (nearest && Math.abs(nearest.timeSec - time) / duration * timelineWidth() < 7) {
    audio.pause()
    drag = { original: beats.map((beat) => ({ ...beat })), time: nearest.timeSec, x: event.clientX, moved: false }
    selected = nearest.timeSec
    canvas.setPointerCapture(event.pointerId)
    seek(nearest.timeSec)
    renderList()
    return
  }
  selected = null
  seek(time)
  renderList()
})
canvas.addEventListener('pointermove', (event) => {
  hoverTime = timeAt(event)
  if (!drag) { draw(); return }
  if (!drag || Math.abs(event.clientX - drag.x) < 3 && !drag.moved) return
  drag.moved = true
  const next = Number(timeAt(event).toFixed(3))
  beats = addBeat(beats.filter((beat) => beat.timeSec !== selected), next)
  selected = next
  // Keep the waveform stationary while positioning a marker.
  audio.currentTime = next
  draw()
})
canvas.addEventListener('pointerleave', () => { hoverTime = null; draw() })
function endDrag() {
  if (!drag) return
  if (drag.moved) { undoStack.push(drag.original); redoStack.length = 0; changed() }
  drag = null
}
canvas.addEventListener('pointerup', endDrag)
canvas.addEventListener('pointercancel', endDrag)
canvas.addEventListener('dblclick', (event) => mark(timeAt(event)))

document.addEventListener('keydown', (event) => {
  if (event.target instanceof HTMLInputElement && !['range', 'checkbox'].includes(event.target.type)) return
  if (event.target instanceof HTMLTextAreaElement || event.target.isContentEditable) return
  if (event.target instanceof HTMLSelectElement && event.code !== 'KeyM') return
  if (event.target instanceof HTMLInputElement && event.target.type === 'range' && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.code)) return
  if ((event.metaKey || event.ctrlKey) && event.code === 'KeyZ') { event.preventDefault(); history(event.shiftKey ? 'redo' : 'undo'); return }
  if (event.metaKey || event.ctrlKey || event.altKey) return
  if (event.code === 'Equal' || event.code === 'NumpadAdd') { event.preventDefault(); setZoom(zoom * 2); return }
  if (event.code === 'Minus' || event.code === 'NumpadSubtract') { event.preventDefault(); setZoom(zoom / 2); return }
  if (event.code === 'Digit0') { event.preventDefault(); setZoom(1); return }
  if (event.code === 'Escape') { if (reviewing) setReview(false); toggleBeats(false); return }
  if (event.code === 'Space') { event.preventDefault(); if (!event.repeat) void togglePlay(); return }
  if (event.code === 'KeyM') { event.preventDefault(); if (!event.repeat && !reviewing) mark(); return }
  if (event.code === 'Delete' || event.code === 'Backspace') { if (!reviewing && selected !== null) { event.preventDefault(); remove(selected) }; return }
  if (event.code === 'ArrowLeft' || event.code === 'ArrowRight') { event.preventDefault(); audio.pause(); seek(audio.currentTime + (event.code === 'ArrowLeft' ? -1 : 1) * (event.shiftKey ? 0.1 : 0.001)); return }
  if (event.code === 'BracketLeft' || event.code === 'BracketRight') { event.preventDefault(); seek(adjacentBeatTime(beats, audio.currentTime, event.code === 'BracketLeft' ? 'previous' : 'next', duration)) }
  if (event.code === 'Home') { event.preventDefault(); seek(0) }
})

$('export').addEventListener('click', () => {
  save()
  const payload = { schemaVersion: 1, title: 'VibeEdit beat review', sourceUrl: source, durationSec: duration, source: 'beatmap-review', model: 'human-edit-v1', beats, beatTimes: beats.map((beat) => beat.timeSec), updatedAt: new Date().toISOString() }
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2) + '\n'], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = 'vibeedit-beatmap.json'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  notify(`Exported ${beats.length} beats for VibeEdit`)
})
$('import-button').addEventListener('click', () => $('import-file').click())
$('import-top').addEventListener('click', () => $('import-file').click())
$('import-file').addEventListener('change', async () => {
  const file = $('import-file').files[0]
  if (!file) return
  try {
    const data = JSON.parse(await file.text())
    if (data.sourceUrl && data.sourceUrl !== source) throw new Error('This beat map belongs to a different song.')
    const imported = validateBeats(data)
    remember(); beats = imported; selected = null; lastReviewBeat = null; changed(); notify(`Imported ${beats.length} beats`)
  } catch (error) { notify(error.message || 'Could not import this beat map.') }
  $('import-file').value = ''
})

audio.addEventListener('play', () => { $('play').setAttribute('aria-label', 'Pause'); $('play').innerHTML = '<svg viewBox="0 0 24 24" width="19" height="19" fill="currentColor"><path d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg>'; $('error').hidden = true })
function paused() { $('play').setAttribute('aria-label', 'Play'); $('play').innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'; draw() }
audio.addEventListener('pause', paused)
audio.addEventListener('ended', paused)
audio.addEventListener('seeked', draw)
function metadataLoaded() {
  if (!Number.isFinite(audio.duration)) return
  duration = audio.duration
  $('loop-end').value = duration
  $('total-time').textContent = formatTime(duration)
  $('track-duration').textContent = `${Math.floor(duration / 60)}:${String(Math.floor(duration % 60)).padStart(2, '0')}`
  draw()
}
audio.addEventListener('loadedmetadata', metadataLoaded)
if (audio.readyState >= 1) metadataLoaded()
audio.addEventListener('error', () => { $('error').textContent = 'The track could not load. Refresh the page to try again. Your saved beats are kept in this browser.'; $('error').hidden = false })
new ResizeObserver(() => { $('wave-content').style.width = `${timelineWidth()}px`; draw() }).observe(scroll)

if (localStorage.getItem(storageKey)) notify('An unsaved browser draft exists. Export it before reloading if needed; project state remains authoritative.')
renderList()
renderLayers()
if (window.location.hash === '#review') setReview(true)
fetch('/api/waveform?' + new URLSearchParams({source: state.source.id})).then((response) => {
  if (!response.ok) throw new Error('waveform')
  return response.json()
}).then((data) => { waveform = { durationSec: data.durationSec, levels: Object.fromEntries(layers.map((layer) => [layer.id, peakLevels(data.bands[layer.id])])) }; draw() }).catch(() => {
  $('error').textContent = 'Waveforms could not load. Refresh to try again. Music and beat marking are still available.'
  $('error').hidden = false
})
function tick(now) {
  if (!audio.paused && now - lastRender > (reviewing ? 0 : 30)) {
    if (!reviewing && $('follow').checked) reveal(audio.currentTime)
    draw(); lastRender = now
  }
  requestAnimationFrame(tick)
}
requestAnimationFrame(tick)

audio.addEventListener('timeupdate', () => {
  if (!$('loop').checked) return
  const start = Number($('loop-start').value), end = Number($('loop-end').value)
  if (Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start && end <= duration && audio.currentTime >= end) audio.currentTime = start
})
