/**
 * UserApp.jsx — Dynamic requirements interview
 *
 * Phases:
 *   describe   → user types/speaks their product idea
 *   interview  → AI asks gap-driven questions (no fixed limit)
 *   generating → 5-agent pipeline runs
 *   done       → PRD displayed with download
 *
 * Audio: Web Speech API for live mic, file upload for recorded audio.
 */
import { useState, useRef, useEffect } from 'react'
import * as api from '../api'
import styles from './UserApp.module.css'

const SR = window.SpeechRecognition || window.webkitSpeechRecognition || null

export default function UserApp() {
  const [phase, setPhase]               = useState('describe')
  const [description, setDesc]          = useState('')
  const [sessionId, setSessionId]       = useState(null)
  const [messages, setMessages]         = useState([])
  const [completeness, setCompleteness] = useState(0)
  const [areasCovered, setAreasCovered] = useState([])
  const [areasMissing, setAreasMissing] = useState([])
  const [domainLabel, setDomainLabel]   = useState('')
  const [answer, setAnswer]             = useState('')
  const [loading, setLoading]           = useState(false)
  const [prdResult, setPrdResult]       = useState(null)
  const [listening, setListening]       = useState(false)
  const [micError, setMicError]         = useState('')
  const [answerCount, setAnswerCount]   = useState(0)
  const [speakEnabled, setSpeakEnabled] = useState(true)
  const [speaking, setSpeaking]         = useState(false)
  const [tbdAreas, setTbdAreas]         = useState([])
  const [isRephrasing, setIsRephrasing] = useState(false)
  const [techLabel, setTechLabel]       = useState('')
  const [techLevel, setTechLevel]       = useState(0)

  const recRef      = useRef(null)
  const interimRef  = useRef('')
  const chatEndRef  = useRef(null)
  const inputRef    = useRef(null)
  const fileRef     = useRef(null)
  const lastSpokenRef = useRef(-1)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    if (phase === 'interview' && !loading) inputRef.current?.focus()
  }, [messages, loading, phase])

  // ── Text-to-Speech: read new AI messages aloud ────────────────────────
  const stripMarkdown = (text) =>
    text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1')
        .replace(/`(.+?)`/g, '$1').replace(/^#+\s*/gm, '').replace(/\n/g, ' ').trim()

  const speak = (text) => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const plain = stripMarkdown(text)
    if (!plain) return
    const utt = new SpeechSynthesisUtterance(plain)
    utt.lang = 'en-US'
    utt.rate = 1.05
    utt.pitch = 1.0
    utt.onstart = () => setSpeaking(true)
    utt.onend   = () => setSpeaking(false)
    utt.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(utt)
  }

  const stopSpeaking = () => {
    if (window.speechSynthesis) window.speechSynthesis.cancel()
    setSpeaking(false)
  }

  useEffect(() => {
    if (!speakEnabled || messages.length === 0) return
    const lastIdx = messages.length - 1
    const last = messages[lastIdx]
    if (last.role === 'ai' && lastIdx > lastSpokenRef.current) {
      lastSpokenRef.current = lastIdx
      speak(last.text)
    }
  }, [messages, speakEnabled])

  // ── Start interview ────────────────────────────────────────────────────
  const startInterview = async () => {
    if (!description.trim()) return
    setLoading(true)
    try {
      const r = await api.interviewStart({ description: description.trim() })
      setSessionId(r.session_id)
      setDomainLabel(r.domain_label)
      setCompleteness(r.completeness)
      setAreasMissing(r.areas_missing || [])
      setAreasCovered(r.areas_covered || [])
      if (r.tech_level)      setTechLevel(r.tech_level)
      if (r.tech_level_label) setTechLabel(r.tech_level_label)
      setMessages([
        { role: 'user', text: description.trim() },
        { role: 'ai',   text: `Detected: **${r.domain_label}**. I'll keep asking until requirements are complete — no fixed limit.\n\n${r.first_question}` },
      ])
      setPhase('interview')
    } catch (e) {
      alert('Error: ' + e.message)
    }
    setLoading(false)
  }

  // ── Submit answer ──────────────────────────────────────────────────────
  const submitAnswer = async (text) => {
    text = (text || '').trim()
    if (!text || !sessionId) return

    // Stop any active voice recognition first so it doesn't bleed into next answer
    if (listening && recRef.current) {
      recRef.current.stop()
      setListening(false)
    }
    stopSpeaking()

    setLoading(true)
    setIsRephrasing(false)
    setMessages(prev => [...prev, { role: 'user', text }])
    // Clear textarea and voice interim buffer immediately
    setAnswer('')
    interimRef.current = ''

    try {
      const r = await api.interviewAnswer({ session_id: sessionId, answer: text })
      setCompleteness(r.completeness)
      setAreasCovered(r.areas_covered || [])
      setAreasMissing(r.areas_missing || [])
      if (r.tbd_areas)        setTbdAreas(r.tbd_areas)
      if (r.tech_level)       setTechLevel(r.tech_level)
      if (r.tech_level_label) setTechLabel(r.tech_level_label)

      // If a recommendation was returned, insert it as a special card before the next question
      if (r.recommendation) {
        setMessages(prev => [...prev, { role: 'rec', rec: r.recommendation }])
      }

      if (r.rephrased) {
        setIsRephrasing(true)
        setMessages(prev => [...prev, { role: 'ai', text: r.next_question, rephrased: true }])
      } else if (r.ready_for_prd || !r.next_question) {
        setMessages(prev => [...prev, {
          role: 'ai',
          text: `Requirements are **${r.completeness}% complete**. Generating your PRD now!`,
        }])
        await doGenerate()
      } else {
        setAnswerCount(c => c + 1)
        setMessages(prev => [...prev, { role: 'ai', text: r.next_question }])
      }
    } catch {
      setMessages(prev => [...prev, { role: 'ai', text: 'Error processing answer. Please try again.' }])
    }
    setLoading(false)
  }

  // ── Generate PRD ───────────────────────────────────────────────────────
  const doGenerate = async () => {
    setPhase('generating')
    try {
      const r = await api.interviewGenerate({ session_id: sessionId })
      setPrdResult(r)
      setPhase('done')
    } catch (e) {
      alert('Generation error: ' + e.message)
      setPhase('interview')
    }
  }

  const forceGenerate = () => {
    setMessages(prev => [...prev, { role: 'ai', text: 'Generating PRD with current requirements...' }])
    doGenerate()
  }

  // ── Voice (Web Speech API) ────────────────────────────────────────────
  const toggleMic = (setter) => {
    setMicError('')
    if (listening) { recRef.current?.stop(); return }
    if (!SR) { setMicError('Voice not supported in this browser. Use Chrome/Edge or upload audio.'); return }
    stopSpeaking()

    const rec = new SR()
    rec.lang = 'en-US'
    rec.continuous = true
    rec.interimResults = true

    rec.onstart  = () => setListening(true)
    rec.onresult = (e) => {
      let final = '', interim = ''
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript + ' '
        else interim += e.results[i][0].transcript
      }
      const combined = (interimRef.current + final).trim()
      if (final) interimRef.current = combined
      setter((combined + (interim ? ' ' + interim : '')).trim())
    }
    rec.onerror = (e) => {
      if (e.error === 'not-allowed') setMicError('Microphone permission denied.')
      else if (e.error !== 'aborted') setMicError(`Mic error: ${e.error}`)
      setListening(false)
    }
    rec.onend = () => setListening(false)
    recRef.current = rec
    rec.start()
  }

  // ── Audio file upload ─────────────────────────────────────────────────
  const handleAudioUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    try {
      const r = await api.transcribeAudio(file)
      if (r.success && r.transcript) {
        if (phase === 'describe') setDesc(prev => (prev + ' ' + r.transcript).trim())
        else setAnswer(prev => (prev + ' ' + r.transcript).trim())
      } else {
        setMicError(r.error || 'Could not transcribe audio.')
      }
    } catch (err) {
      setMicError('Transcription failed: ' + err.message)
    }
    setLoading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  // ── Reset ─────────────────────────────────────────────────────────────
  const resetAll = () => {
    stopSpeaking()
    setPhase('describe'); setDesc(''); setSessionId(null); setMessages([])
    setCompleteness(0); setAreasCovered([]); setAreasMissing([])
    setDomainLabel(''); setAnswer(''); setPrdResult(null)
    setAnswerCount(0); setListening(false); setMicError('')
    setSpeakEnabled(true); setTbdAreas([]); setIsRephrasing(false)
    setTechLabel(''); setTechLevel(0)
    interimRef.current = ''
    lastSpokenRef.current = -1
  }

  const downloadPRD = () => {
    if (!prdResult) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([prdResult.prd_markdown], { type: 'text/markdown' }))
    a.download = `${(prdResult.project_name || 'PRD').replace(/\s+/g, '_')}_PRD.md`
    a.click()
  }

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className={styles.root}>
      <input ref={fileRef} type="file" accept="audio/*,.wav,.mp3,.webm,.ogg,.m4a"
             style={{ display: 'none' }} onChange={handleAudioUpload} />

      {/* Header */}
      <header className={styles.topBar}>
        <div className={styles.brand}><LogoMark /><span>Requirements Engine</span></div>
        <div className={styles.topRight}>
          <button
            className={`${styles.speakerBtn} ${speakEnabled ? styles.speakerOn : ''} ${speaking ? styles.speakerActive : ''}`}
            onClick={() => { setSpeakEnabled(v => !v); if (speakEnabled) stopSpeaking() }}
            title={speakEnabled ? 'Voice output ON — click to mute' : 'Voice output OFF — click to unmute'}
          >
            {speakEnabled ? <SpeakerOnIcon /> : <SpeakerOffIcon />}
            {speaking && <span className={styles.speakerPulse} />}
          </button>
          {phase !== 'describe' && (
            <button className={styles.headerBtn} onClick={resetAll}>New Project</button>
          )}
        </div>
      </header>

      <main className={styles.main}>
        {/* ───── DESCRIBE ───── */}
        {phase === 'describe' && (
          <div className={styles.center}>
            <div className={styles.card}>
              <h2 className={styles.cardTitle}>Tell us about your product</h2>
              <p className={styles.cardSub}>
                Describe what you want to build. The AI will interview you to gather complete requirements — no fixed question limit.
              </p>
              <div className={styles.descArea}>
                <textarea
                  className={`${styles.bigInput} ${listening ? styles.inputGlow : ''}`}
                  value={description}
                  onChange={e => setDesc(e.target.value)}
                  placeholder="e.g. I want to build a mobile app for a restaurant chain so customers can order food, track deliveries and earn loyalty points..."
                  rows={6}
                />
                <div className={styles.descActions}>
                  <MicBtn active={listening} onClick={() => toggleMic(setDesc)} />
                  <UploadBtn onClick={() => fileRef.current?.click()} />
                  {listening && <span className={styles.hint}>Speaking... click mic to stop</span>}
                </div>
                {micError && <div className={styles.err}>{micError}</div>}
              </div>
              <button className={styles.primaryBtn} onClick={startInterview}
                      disabled={!description.trim() || loading}>
                {loading ? 'Analyzing...' : 'Start Requirements Interview'}
              </button>
            </div>
          </div>
        )}

        {/* ───── INTERVIEW ───── */}
        {phase === 'interview' && (
          <div className={styles.interview}>
            {/* Progress */}
            <div className={styles.progressBar}>
              <div className={styles.progressFill} style={{ width: `${completeness}%` }} />
            </div>
            <div className={styles.progressInfo}>
              <span>Completeness: <strong>{completeness}%</strong></span>
              <span>{answerCount} answered</span>
              <span>{domainLabel}</span>
              {techLabel && (
                <span className={`${styles.techBadge} ${
                  techLevel <= 3 ? styles.techNon :
                  techLevel <= 6 ? styles.techSemi : styles.techPro}`}>
                  {techLabel}
                </span>
              )}
            </div>

            {/* Status chips row */}
            <div className={styles.statusRow}>
              {areasMissing.length > 0 && (
                <div className={styles.chips}>
                  <span className={styles.chipsLabel}>Still needed:</span>
                  {areasMissing.slice(0, 5).map((a, i) =>
                    <span key={i} className={styles.chip}>{a.replace(/_/g,' ')}</span>)}
                  {areasMissing.length > 5 &&
                    <span className={styles.chip}>+{areasMissing.length - 5}</span>}
                </div>
              )}
              {tbdAreas.length > 0 && (
                <div className={styles.chips}>
                  <span className={`${styles.chipsLabel} ${styles.tbdLabel}`}>TBD:</span>
                  {tbdAreas.map((a, i) =>
                    <span key={i} className={`${styles.chip} ${styles.chipTbd}`}>{a.replace(/_/g,' ')}</span>)}
                </div>
              )}
            </div>

            {/* Rephrase hint banner */}
            {isRephrasing && (
              <div className={styles.rephraseBanner}>
                <span className={styles.rephraseIcon}>💡</span>
                <span>No worries — I've rephrased that question. Answer with what you know, or type <strong>"skip"</strong> to mark it as TBD and move on.</span>
              </div>
            )}

            {/* Chat */}
            <div className={styles.chat}>
              {messages.map((m, i) => {
                if (m.role === 'rec') return <RecommendationCard key={i} rec={m.rec} />
                return (
                  <div key={i} className={`${styles.msg} ${m.role === 'user' ? styles.msgUser : styles.msgAi}`}>
                    {m.role === 'ai' && <AiAvatar rephrased={m.rephrased} />}
                    <div className={`${styles.msgText} ${m.rephrased ? styles.msgRephrased : ''}`}>
                      {m.rephrased && <span className={styles.rephrasedBadge}>Rephrased ↻</span>}
                      <InlineMarkdown text={m.text} />
                    </div>
                  </div>
                )
              })}
              {loading && (
                <div className={`${styles.msg} ${styles.msgAi}`}>
                  <AiAvatar /><div className={styles.msgText}><Dots /></div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input bar */}
            <div className={styles.bar}>
              <textarea
                ref={inputRef}
                className={`${styles.barInput} ${listening ? styles.inputGlow : ''}`}
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitAnswer(answer) } }}
                placeholder={isRephrasing ? 'Answer what you can, or type "skip" to note as TBD...' : 'Type your answer... (Enter to send)'}
                rows={2}
                disabled={loading}
              />
              <div className={styles.barBtns}>
                <MicBtn active={listening} disabled={speaking || loading}
                        onClick={() => !speaking && toggleMic(setAnswer)}
                        title={speaking ? 'Wait for AI to finish speaking…' : undefined} />
                <UploadBtn onClick={() => fileRef.current?.click()} disabled={loading} />
                <button className={styles.sendBtn} onClick={() => submitAnswer(answer)}
                        disabled={!answer.trim() || loading}><SendIcon /></button>
              </div>
            </div>
            {micError && <div className={styles.err}>{micError}</div>}

            {answerCount >= 3 && (
              <div className={styles.genRow}>
                <button className={styles.genBtn} onClick={forceGenerate} disabled={loading}>
                  Generate PRD Now
                </button>
                <span className={styles.genHint}>
                  {completeness < 70
                    ? 'More questions would improve quality.'
                    : 'Good coverage! Generate now or continue.'}
                </span>
              </div>
            )}
          </div>
        )}

        {/* ───── GENERATING ───── */}
        {phase === 'generating' && (
          <div className={styles.center}>
            <div className={styles.genCard}>
              <Spinner />
              <div className={styles.genTitle}>Generating your PRD...</div>
              <div className={styles.genSub}>
                Running 5-agent pipeline: Transcription, Analyzer, Ambiguity, Questions, Documentation
              </div>
            </div>
          </div>
        )}

        {/* ───── DONE ───── */}
        {phase === 'done' && prdResult && (
          <div className={styles.done}>
            <div className={styles.metrics}>
              <Metric label="Score"
                      value={`${Math.round((prdResult.completion?.overall_score || 0) * 100)}%`} />
              <Metric label="Functional" value={prdResult.functional?.length || 0} />
              <Metric label="Non-Functional" value={prdResult.non_functional?.length || 0} />
              <Metric label="Gaps" value={prdResult.gaps?.length || 0} />
              <Metric label="Questions" value={answerCount} />
              {prdResult.recommendations?.length > 0 && (
                <Metric label="AI Recs" value={prdResult.recommendations.length} />
              )}
              {tbdAreas.length > 0 && (
                <Metric label="TBD Areas" value={tbdAreas.length} warn />
              )}
            </div>

            {tbdAreas.length > 0 && (
              <div className={styles.tbdBanner}>
                <strong>⚠ {tbdAreas.length} area{tbdAreas.length > 1 ? 's' : ''} marked TBD</strong>
                <span> — these are noted in the PRD and require follow-up:</span>
                <div className={styles.tbdList}>
                  {tbdAreas.map((a, i) => (
                    <span key={i} className={styles.chipTbd}>{a.replace(/_/g, ' ')}</span>
                  ))}
                </div>
              </div>
            )}

            <div className={styles.prd}>
              <div className={styles.prdHead}>
                <div className={styles.prdName}>{prdResult.project_name}</div>
                <div className={styles.prdBtns}>
                  <button className={styles.dlBtn} onClick={downloadPRD}>Download .md</button>
                  <button className={styles.headerBtn} onClick={resetAll}>New Project</button>
                </div>
              </div>
              <div className={styles.prdBody}>
                <div className="md-body"
                     dangerouslySetInnerHTML={{ __html: renderMd(prdResult.prd_markdown) }} />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

// ── helpers ──────────────────────────────────────────────────────────────────

function renderMd(md) {
  if (!md) return ''
  return md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/---/g, '<hr/>')
    .replace(/\n{2,}/g, '</p><p>')
}

function InlineMarkdown({ text }) {
  if (!text) return null
  const parts = text.split(/(\*\*.*?\*\*|\n)/g)
  return <>{parts.map((p, i) => {
    if (p === '\n') return <br key={i} />
    if (p.startsWith('**') && p.endsWith('**'))
      return <strong key={i}>{p.slice(2, -2)}</strong>
    return <span key={i}>{p}</span>
  })}</>
}

function Metric({ label, value, warn = false }) {
  return (
    <div className={`${styles.metricBox} ${warn ? styles.metricWarn : ''}`}>
      <div className={styles.metricVal}>{value}</div>
      <div className={styles.metricLbl}>{label}</div>
    </div>
  )
}

function MicBtn({ active, onClick, disabled = false, title }) {
  return (
    <button
      className={`${styles.iconBtn} ${active ? styles.iconBtnActive : ''} ${disabled && !active ? styles.iconBtnDisabled : ''}`}
      onClick={onClick} type="button"
      disabled={disabled && !active}
      title={title || (active ? 'Stop recording' : 'Use microphone')}>
      {active ? <StopIcon /> : <MicIcon />}
      {active && <span className={styles.pulse} />}
    </button>
  )
}

function UploadBtn({ onClick, disabled = false }) {
  return (
    <button className={`${styles.iconBtn} ${disabled ? styles.iconBtnDisabled : ''}`}
            onClick={onClick} type="button" title="Upload audio file" disabled={disabled}>
      <UploadIcon />
    </button>
  )
}

function RecommendationCard({ rec }) {
  if (!rec) return null
  return (
    <div className={styles.recCard}>
      <div className={styles.recHeader}>
        <span className={styles.recIcon}>💡</span>
        <span className={styles.recTitle}>AI Recommendation — {rec.title}</span>
        <span className={styles.recCat}>{rec.category}</span>
      </div>
      <div className={styles.recBody}>
        <strong>{rec.recommendation}</strong>
        {rec.rationale && <p className={styles.recRationale}>{rec.rationale}</p>}
      </div>
      <div className={styles.recNote}>This recommendation will be included in your PRD.</div>
    </div>
  )
}

function Dots() {
  return <div className={styles.dots}><span /><span /><span /></div>
}

function Spinner() {
  return <div className={styles.spinner} />
}

// ── icons ────────────────────────────────────────────────────────────────────

function LogoMark() {
  return <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
    <rect width="40" height="40" rx="10" fill="rgba(67,97,238,.15)" stroke="rgba(67,97,238,.4)" strokeWidth="1.5"/>
    <polygon points="20,7 31,13 31,27 20,33 9,27 9,13" fill="none" stroke="#4361ee" strokeWidth="1.8"/>
    <circle cx="20" cy="20" r="5" fill="#4361ee"/>
  </svg>
}

function AiAvatar({ rephrased = false }) {
  return <div className={`${styles.avatar} ${rephrased ? styles.avatarRephrased : ''}`}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke={rephrased ? '#f59e0b' : '#4361ee'} strokeWidth="1.8">
      <path d="M12 2a9 9 0 0 1 9 9v3a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v-3a9 9 0 0 1 9-9z"/>
    </svg>
  </div>
}

function MicIcon() {
  return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
}
function StopIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2"/>
  </svg>
}
function SendIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
}
function UploadIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
}
function SpeakerOnIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
  </svg>
}
function SpeakerOffIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
    <line x1="23" y1="9" x2="17" y2="15"/>
    <line x1="17" y1="9" x2="23" y2="15"/>
  </svg>
}
