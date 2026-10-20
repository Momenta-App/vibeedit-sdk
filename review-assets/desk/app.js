import {session, mutate} from './session.js'
import {frameBoundary, noteRange} from './clock.js'
const $ = id => document.getElementById(id)
let state = await session()
let revision = state.revision
let selected = null
const media = $('media')
media.src = `/media/${state.source.id}`
$('title').textContent = `${state.mode[0].toUpperCase()}${state.mode.slice(1)} review`
$('mode').textContent = state.mode
$('source').textContent = state.source.id
$('status').textContent = `Project revision ${revision}`
$('conflicts').textContent = state.mappingConflicts.length ? `${state.mappingConflicts.length} prior corrections require explicit mapping to this baseline.` : ''
const machine = state.machine || {}
const hasProjection = machine.sourceTimeline?.audioToVideoMillis != null || machine.preparedAudio?.sourceTimeline?.audioToVideoMillis != null
const audioClockOnly = state.mode === 'words' && machine.clock !== 'video-relative' && !hasProjection && state.source.streams.some(s=>s.codec_type==='video')
if(audioClockOnly) $('uncertainty').textContent = 'Audio-to-video projection is unavailable. Word times remain on the first decoded audio sample; video seeking/timing application waits for explicit mapping.'
const offsetUs = Number(machine.preparedAudio?.sourceTimeline?.audioToVideoMillis ?? machine.sourceTimeline?.audioToVideoMillis ?? 0)*1000
function rows() {
  if (state.mode === 'words') return (machine.words || []).map(word => ({...word,id:String(word.id ?? word.ordinal),startUs:word.startUs ?? Math.round(word.start*1000+offsetUs),endUs:word.endUs ?? Math.round(word.end*1000+offsetUs)}))
  if (state.mode === 'faces') return machine.appearances || machine.faceAppearances || machine.groups || []
  return state.corrections.filter(e=>e.action==='note').map(e=>({...e.payload,id:e.targetId}))
}
function renderedRows() {
  const values = new Map(rows().map(row=>[String(row.id??row.appearanceId??row.groupId),{...row}]))
  for (const event of state.corrections) {
    if (event.action==='delete') values.set(event.targetId,{...values.get(event.targetId),id:event.targetId,deleted:true})
    if (['set','note','portrait','restore'].includes(event.action)) values.set(event.targetId,{...values.get(event.targetId),...event.payload,...(event.action==='restore'?{deleted:false}:{}),id:event.targetId,humanCorrected:true})
    if (event.action==='assign') values.set(event.targetId,{...values.get(event.targetId),id:event.targetId,confirmedPersonId:event.payload.personId,linkStatus:event.payload.personId?'human-confirmed':'unresolved',humanCorrected:true})
  }
  return [...values.values()]
}
function draw() {
  $('rows').replaceChildren(...renderedRows().filter(row=>JSON.stringify(row).toLowerCase().includes($('filter').value.toLowerCase())).map(row=>{
    const button = document.createElement('button')
    button.className = 'row' + (selected?.id===row.id?' selected':'')
    button.textContent = `${row.text??row.name??row.id} · ${row.startUs??'native geometry'} · voice ${row.speakerId??row.voiceGroupId??'unresolved'} · person ${row.confirmedPersonId??'unresolved'}${row.personId?' · model person proposal '+row.personId:''}${row.deleted?' · DELETED':''}${row.humanCorrected?' · human correction':''}`
    button.onclick = ()=>{
      selected=row; $('target').value=row.id; $('text').value=row.text??row.note??''; $('start').value=row.startUs??''; $('end').value=row.endUs??''; $('person').value=row.confirmedPersonId??''
      if(!audioClockOnly) media.currentTime=Math.max(0,(row.startUs??0)/1e6); draw()
    }
    return button
  }))
  $('history').textContent=state.corrections.map(e=>`${e.revision} · ${e.action} · ${e.targetId}${e.remoteStatus?' · '+e.remoteStatus:''}`).join('\n')
}
async function save(action) {
  const payload = action==='undo' ? {operationId:state.corrections.at(-1)?.operationId} : action==='assign' ? {personId:$('person').value||null,confirmation:'human-reviewed'} : {text:$('text').value}
  if(!['undo','assign'].includes(action)) {
    payload.clock = audioClockOnly ? 'first-decoded-audio-sample' : 'video-relative'
    if($('start').value!=='') payload.startUs=Number($('start').value)
    if($('end').value!=='') payload.endUs=Number($('end').value)
    if($('portrait').value) payload.portraitSourceId=$('portrait').value
    if($('members').value) payload.members=$('members').value.split(',').map(s=>s.trim())
    if($('library').value) {payload.libraryId=$('library').value;payload.expectedLibraryRevision=$('library-revision').value}
  }
  try {
    await mutate({operationId:crypto.randomUUID(),expectedRevision:revision,author:'human:review',sourceId:state.source.id,sourceSha256:state.source.sha256,domain:state.mode,action,targetId:$('target').value||crypto.randomUUID(),...(state.baseline?{baselineId:state.baseline.id}:{}),payload})
    state=await session();revision=state.revision;$('status').textContent=`Saved revision ${revision}`;draw()
  }catch(error){$('status').textContent=error.message}
}
$('save').onclick=()=>save(state.mode==='video'?'note':'set')
$('assign-person').onclick=()=>save('assign')
$('assign-person').hidden=state.mode!=='words'
for(const action of ['delete','undo','merge','split','restore']) $(action).onclick=()=>save(action)
$('filter').oninput=draw
const rate=state.source.streams.find(s=>s.codec_type==='video')?.avg_frame_rate?.split('/').map(Number)??[30,1]
const step=rate.length===2&&rate.every(Number.isFinite)&&rate[0]>0&&rate[1]>0?rate[1]/rate[0]:1/30
let stepped = null
function stepFrame(direction) {
  media.pause()
  const boundary = frameBoundary(media.currentTime, step, direction, media.duration)
  media.currentTime = boundary.exactSeconds
  stepped = {...boundary, browserSeconds:media.currentTime}
}
$('back').onclick=()=>stepFrame(-1)
$('forward').onclick=()=>stepFrame(1)
$('uncertainty').textContent += ' Frame steps use the nominal frame-rate grid; variable-rate video timing is approximate.'
media.ontimeupdate=()=>{if($('loop').checked&&selected&&media.currentTime>=selected.endUs/1e6) media.currentTime=Math.max(0,selected.startUs/1e6)}
$('export').onclick=()=>{const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([JSON.stringify({schemaVersion:'vibeedit.revisionRequest.v1',source:state.source,corrections:state.corrections,mappingConflicts:state.mappingConflicts},null,2)],{type:'application/json'}));link.download='vibeedit-revisions.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}
draw()

$('note-here').onclick=()=>{media.pause();const range=noteRange(media.currentTime,step,stepped);$('target').value=crypto.randomUUID();$('start').value=range.startUs;$('end').value=range.endUs;$('text').focus()}

const coverage = state.coverage.words || state.coverage.appearances || state.coverage.faceAppearances || state.coverage.groups
if(coverage) $('page').textContent=`${coverage.offset + 1}–${Math.min(coverage.offset+coverage.limit,coverage.total)} / ${coverage.total}`
function page(direction){const params=new URLSearchParams(location.search);params.set('offset',Math.max(0,(coverage?.offset||0)+direction*(coverage?.limit||200)));location.search=params}
$('previous-page').onclick=()=>page(-1)
$('next-page').onclick=()=>page(1)
$('previous-page').disabled=!coverage||coverage.offset===0
$('next-page').disabled=!coverage||coverage.offset+coverage.limit>=coverage.total
