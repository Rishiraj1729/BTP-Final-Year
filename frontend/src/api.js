const BASE = import.meta.env.VITE_API_URL || ''

const post = async (path, body) => {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail || JSON.stringify(data))
  return data
}

export const interviewStart    = (body) => post('/api/interview/start', body)
export const interviewAnswer   = (body) => post('/api/interview/answer', body)
export const interviewGenerate = (body) => post('/api/interview/generate', body)

export const transcribeAudio = async (file) => {
  const form = new FormData()
  form.append('file', file)
  const r = await fetch(`${BASE}/api/interview/transcribe`, {
    method: 'POST', body: form,
  })
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail || 'Transcription failed')
  return data
}
