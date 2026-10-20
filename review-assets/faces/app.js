import { session } from './session.js'
const $ = id => document.getElementById(id)
let state
let groups
let appearances
let groupOffset = 0
let appearanceOffset = 0
let activeGroup = null
let activeAppearance = null
let libraryRevision = null
let retry = null
let busy = false
let viewBaselineId = null
let baselineChanged = false
let previewReady = false
const selected = new Set()
const knownPeople = new Map()
const knownGroups = new Map()
function status(text, error = false) { $('status').textContent = text; $('status').classList.toggle('error', error) }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
  const value = await response.json()
  if (!response.ok) { if (response.status === 409) $('rebase').hidden = false; throw new Error(value.error || 'Face review request failed') }
  return value
}
function query(path, values) {
  const params = new URLSearchParams(location.search)
  for (const [key, value] of Object.entries(values)) if (value !== null && value !== undefined) params.set(key, value)
  return path + '?' + params
}
function personName(id) { return id ? 'Person ' + id.slice(-6) : 'Unresolved identity' }
function history() {
  const portraits = new Map()
  for (const event of state.corrections || []) if (event.action === "portrait") { const request = event.payload.previewRequest; portraits.set(request.personId || request.groupId || event.targetId, event) }
  $("saved-portraits").replaceChildren(...[...portraits.values()].slice(-10).map(event => { const figure = document.createElement("figure"); const image = document.createElement("img"); image.loading = "lazy"; image.alt = "Saved local portrait from native source frame " + event.payload.previewRequest.frameOrdinal; image.src = query("/api/faces/preview", {appearanceId:event.payload.appearanceId,portrait:1}); const caption = document.createElement("figcaption"); caption.textContent = (event.payload.previewRequest.groupId || "Saved appearance") + " · source frame " + event.payload.previewRequest.frameOrdinal; figure.append(image, caption); return figure }))
  $('history').textContent = (state.corrections || []).map(event => `${event.revision} · ${event.action} · ${event.remoteStatus || 'local'} · ${event.targetId}`).join('\n') || 'No saved changes for this baseline.'
  $('pending').replaceChildren(...(state.corrections || []).filter(event=>event.remoteStatus === 'pending').map(event=>{const button=document.createElement('button');button.textContent='Retry saved library operation '+event.operationId.slice(0,8);button.onclick=()=>run(async()=>{const result=await api('/api/faces/corrections/'+encodeURIComponent(event.operationId)+'/retry',{});await afterMutation(result,false)});return button}))
  $('conflicts').textContent = state.mappingConflicts?.length ? `${state.mappingConflicts.length} previous changes need explicit mapping to this baseline.` : ''
}
function controls() {
  $('selection').textContent = selected.size ? `${selected.size} whole appearance groups selected.` : 'No groups selected.'
  for (const id of ['merge','split','unresolved']) $(id).disabled = busy || baselineChanged || !selected.size || !libraryRevision
  $('portrait').disabled = busy || baselineChanged || !activeAppearance || !previewReady
}
function targets() {
  const previous = $('target').value
  $('target').replaceChildren(new Option('Choose a person', ''), ...[...knownPeople].map(([id, label]) => new Option(label, id)))
  $('target').value = previous
}
async function loadGroups() {
  groups = await api(query('/api/faces/groups', {offset:groupOffset,limit:50}))
  $('coverage').textContent = `Requested frames ${groups.coverage.sourceFrameRange[0]}–${groups.coverage.sourceFrameRange[1]} (end excluded) of ${groups.coverage.sourceTotalFrameCount}; ${groups.coverage.faceObservationCount} saved observations. Native boundary context stays separate.`
  $('groups-page').textContent = `${groups.total ? groups.offset+1 : 0}–${Math.min(groups.offset+groups.limit,groups.total)} / ${groups.total}`
  $('groups-previous').disabled = !groupOffset
  $('groups-next').disabled = groups.nextOffset === null
  $('groups').replaceChildren(...groups.groups.map(group => {
    knownGroups.set(group.id, group)
    if (group.personId) knownPeople.set(group.personId, personName(group.personId))
    const row = document.createElement('div'); row.className = 'group'; row.classList.toggle('selected',selected.has(group.id))
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = selected.has(group.id); checkbox.setAttribute('aria-label',`Select group ${group.id}`)
    checkbox.onchange = () => { checkbox.checked ? selected.add(group.id) : selected.delete(group.id); row.classList.toggle('selected',checkbox.checked); controls() }
    const button = document.createElement('button'); button.textContent = `${group.id} · ${personName(group.personId)}`
    const detail = document.createElement('small'); detail.textContent = `${group.observationCount} observations · ${group.status}`; button.append(detail)
    button.onclick = () => run(async () => {activeGroup=group;activeAppearance=null;previewReady=false;$('preview-panel').hidden=true;appearanceOffset=0;await loadAppearances()})
    row.append(checkbox,button); return row
  }))
  targets(); controls()
}
async function loadAppearances() {
  appearances = await api(query('/api/faces/appearances',{groupId:activeGroup?.id,offset:appearanceOffset,limit:40}))
  $('appearances-title').textContent = activeGroup ? `Native appearances · ${activeGroup.id}` : 'Native appearances'
  $('appearances-page').textContent = `${appearances.total ? appearances.offset+1 : 0}–${Math.min(appearances.offset+appearances.limit,appearances.total)} / ${appearances.total}`
  $('appearances-previous').disabled = !appearanceOffset
  $('appearances-next').disabled = appearances.nextOffset === null
  $('appearances').replaceChildren(...appearances.appearances.map(appearance => {
    const button = document.createElement('button'); button.className = 'appearance'; button.classList.toggle('selected', activeAppearance?.id === appearance.id)
    button.textContent = `Frame ${appearance.frameOrdinal} · ${(appearance.startUs/1e6).toFixed(3)}s · ${personName(appearance.personId)}`
    button.onclick = () => run(async () => {
      activeAppearance = appearance
      previewReady=false; $('preview-panel').hidden=true
      $('frame-note').textContent=`Loading native ordinal ${appearance.frameOrdinal}…`
      $('preview').onload=()=>{
        if(activeAppearance?.id!==appearance.id) return
        for (const [key,value] of Object.entries({x:appearance.geometry.bbox[0],y:appearance.geometry.bbox[1],width:appearance.geometry.bbox[2],height:appearance.geometry.bbox[3]})) $('face-box').setAttribute(key,value)
        previewReady=true; $('preview-panel').hidden=false; controls()
        $('frame-note').textContent = `Exact native ordinal ${appearance.frameOrdinal}, PTS ${appearance.pts}. Box and landmarks use original source geometry; video playback seeking is approximate.`
      }
      $('preview').src = query('/api/faces/preview',{appearanceId:appearance.id,portrait:0})
      $('media').pause(); $('media').currentTime = Math.max(0,appearance.startUs/1e6)
      await loadAppearances();controls()
    })
    return button
  }))
}
async function run(action) {
  if (busy) return
  busy = true; controls()
  try { await action() } catch(error) { status(error.message,true) }
  finally { busy=false; controls() }
}
async function afterMutation(result, portrait) {
  state = await session(); history()
  baselineChanged = state.baseline?.id !== viewBaselineId
  if (baselineChanged) { $('conflicts').textContent='Analysis changed. Saved changes retain their original baseline; reopen the intended saved analysis before making new selections.'; controls() }
  if (portrait) { status('Local portrait saved. Cloud library unchanged.'); return }
  if (result.remoteStatus === 'applied') {
    libraryRevision = result.appliedRevisionSha256 || null
    status('Library change acknowledged. Original native predictions remain unchanged.')
    return
  }
  status('Library operation remains pending. Retry the saved operation without changing its original body.')
}
async function save(action) {
  const fields = {expectedRevision:state.revision,sourceId:state.source.id,baselineId:viewBaselineId,expectedLibraryRevisionSha256:action.kind === 'portrait' ? null : libraryRevision,action}
  const signature = JSON.stringify({...fields,expectedRevision:undefined,expectedLibraryRevisionSha256:undefined})
  if (!retry || retry.signature !== signature) retry = {signature,command:{operationId:crypto.randomUUID(),...fields}}
  const result = await api('/api/faces/corrections',retry.command)
  retry = null
  await afterMutation(result,action.kind === 'portrait')
  return result
}
async function cloudDraft(kind) {
  const ids = [...selected]
  const target = $('target').value
  let operation
  if (kind === 'merge') {
    const sourceIds = [...new Set(ids.map(id=>knownGroups.get(id)?.personId))].filter(id=>id && id !== target)
    if (!target || sourceIds.length !== 1) throw new Error('Choose groups for one source person and a different target person. Merge additional people in separate saved operations.')
    operation = {kind:'merge',fromPersonId:sourceIds[0],toPersonId:target}
  }
  if (kind === 'split') {
    const sourceIds = [...new Set(ids.map(id=>knownGroups.get(id)?.personId))]
    if (sourceIds.length !== 1 || !sourceIds[0]) throw new Error('Select groups belonging to one saved person before splitting.')
    operation = {kind:'split',fromPersonId:sourceIds[0],groupIds:ids}
  }
  if (kind === 'assign') operation = {kind:'assign',personId:null,groupIds:ids}
  await save(operation)
}
$('merge').onclick=()=>run(()=>cloudDraft('merge'))
$('split').onclick=()=>run(()=>cloudDraft('split'))
$('unresolved').onclick=()=>run(()=>cloudDraft('assign'))
$('portrait').onclick=()=>run(()=>save({kind:'portrait',appearanceId:activeAppearance.id}))
$('refresh-library').onclick=()=>run(async()=>{const value=await api(query('/api/faces/library',{})); libraryRevision=value.revisionSha256;for(const id of (value.identityIds || [])) knownPeople.set(id,personName(id));targets(); if(!/^[a-f0-9]{64}$/.test(libraryRevision)) throw new Error('Authoritative library revision unavailable'); $('library-state').textContent='Current cloud revision read. Any concurrent change will require comparison.';status('Library revision read; no paid job submitted.')})
$('groups-previous').onclick=()=>run(async()=>{groupOffset=Math.max(0,groupOffset-50);await loadGroups()})
$('groups-next').onclick=()=>run(async()=>{groupOffset=groups.nextOffset;await loadGroups()})
$('appearances-previous').onclick=()=>run(async()=>{appearanceOffset=Math.max(0,appearanceOffset-40);await loadAppearances()})
$('appearances-next').onclick=()=>run(async()=>{appearanceOffset=appearances.nextOffset;await loadAppearances()})
$('rebase').onclick=()=>run(async()=>{state=await session();retry=null;$('rebase').hidden=true;history();status('Current project revision loaded. Compare saved changes before saving your retained selection.')})
$('preview').onerror=()=>status('Exact native source preview unavailable. Relink the original source; no neighboring frame was substituted.',true)
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schemaVersion:'vibeedit.faceReviewExport.v1',source:state.source,baseline:state.baseline,corrections:state.corrections,mappingConflicts:state.mappingConflicts},null,2)],{type:'application/json'})); const link=document.createElement('a');link.href=url;link.download='vibeedit-face-review.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
try { state=await session();viewBaselineId=state.baseline?.id;$('media').src='/media/'+state.source.id;history();await loadGroups();await loadAppearances();status(`Project revision ${state.revision} · original predictions retained.`);$('refresh-library').disabled=!groups.library;controls() }
catch(error){status(error.message,true)}
