export async function session() {
  const token = location.hash.slice(1)
  if (token && token !== 'review') {
    const response = await fetch('/api/session', {method:'POST', headers:{'Authorization':`Bearer ${token}`, 'Content-Type':'application/json'}, body:'{}'})
    if (!response.ok) throw new Error('Review capability rejected')
    history.replaceState(null, '', location.pathname + location.search)
  }
  const params = new URLSearchParams(location.search)
  const route = location.pathname.split('/')[1]
  if (['beats','faces','words','video'].includes(route)) params.set('mode', route)
  const response = await fetch('/api/state?' + params)
  if (!response.ok) throw new Error('Open the project review URL supplied by your agent')
  return response.json()
}
export async function mutate(command) {
  const response = await fetch('/api/corrections', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(command)})
  const result = await response.json()
  if (!response.ok) throw new Error(result.error || 'Correction failed')
  return result
}
