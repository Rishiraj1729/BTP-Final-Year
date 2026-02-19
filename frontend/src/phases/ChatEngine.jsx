/**
 * ChatEngine — Phase 1
 * Iterative AI interview with:
 * - Gap detection after every message
 * - Live completion progress
 * - Voice mic using Web Speech API (100% local, no API key, runs in browser)
 *   Press mic → start listening → text appears live in chatbox → press again to stop & send
 * - Audio file upload (mock transcription)
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { processMessage, analyzeConvo, detectTone } from '../api'
import GapSidebar from '../components/GapSidebar'
import styles from './ChatEngine.module.css'

const INITIAL_MSG = (name, level) => ({
  role: 'ai',
  text: `Hello! I'm your AI Solutions Architect${name ? ` for **${name}**` : ''}.

I'll guide you through a structured requirements interview and keep asking until I have everything needed for a complete, enterprise-grade PRD.

${level === 'technical'
  ? "Since you're technical, we'll go deep on architecture, NFRs, and system design."
  : "I'll focus on features, users, and business outcomes — keeping things product-focused."
}

**Let's start: In one sentence, what does your product do and who does it help?**`,
  ts: Date.now(),
})

// ── Check browser speech support ──────────────────────────────────────────────
const SR_CLASS = window.SpeechRecognition || window.webkitSpeechRecognition || null

export default function ChatEngine({ session, onComplete, onUpdate }) {
  const [messages,      setMessages]    = useState([INITIAL_MSG(session.project_name, session.level)])
  const [input,         setInput]       = useState('')
  const [gapReport,     setGapReport]   = useState(null)
  const [functional,    setFunctional]  = useState([])
  const [nonFunctional, setNFR]         = useState([])
  const [rawText,       setRawText]     = useState('')
  const [loading,       setLoading]     = useState(false)
  const [analyzing,     setAnalyzing]   = useState(false)
  const [listening,     setListening]   = useState(false)
  const [micError,      setMicError]    = useState('')
  const [upgraded,      setUpgraded]    = useState(false)

  // audio file upload
  const [audioFile,     setAudioFile]   = useState(null)
  const [transcribing,  setTranscribing]= useState(false)
  const [showAudioMode, setShowAudioMode] = useState(false)

  const bottomRef   = useRef(null)
  const fileRef     = useRef(null)
  const recRef      = useRef(null)
  const inputRef    = useRef(null)

  // interim speech text (shown live while mic is on)
  const interimRef  = useRef('')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Send a message ────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (textOverride) => {
    const trimmed = (textOverride ?? input).trim()
    if (!trimmed || loading || analyzing) return

    setInput('')
    interimRef.current = ''
    setLoading(true)

    const newMsg      = { role: 'user', text: trimmed, ts: Date.now() }
    const newMessages = [...messages, newMsg]
    setMessages(newMessages)
    const newRaw = rawText + '\nClient: ' + trimmed
    setRawText(newRaw)

    try {
      // auto-upgrade technical jargon to CTO mode
      const tone = await detectTone({ message: trimmed, stated_level: session.level })
      if (tone.jargon_count >= 3 && session.level === 'business' && !upgraded) {
        setUpgraded(true)
        onUpdate({ level: 'technical', persona: 'CTO' })
        setMessages(m => [...m, {
          role: 'system',
          text: 'Technical vocabulary detected — upgrading to architect-level depth.',
          ts: Date.now(),
        }])
      }

      // gap check + AI response
      const res = await processMessage({
        message:          trimmed,
        role:             'user',
        current_raw_text: newRaw,
        functional,
        non_functional:   nonFunctional,
        messages:         newMessages.map(m => ({ role: m.role, text: m.text })),
        provider:         session.provider,
      })

      const gapRpt = res.gap_report
      setGapReport(gapRpt)
      onUpdate({ gapReport: gapRpt, completion: Math.round((gapRpt?.completion_score || 0) * 100) })
      setMessages(m => [...m, { role: 'ai', text: res.ai_response, ts: Date.now() }])

      if (gapRpt?.is_complete) {
        setTimeout(() => triggerAnalysis(newRaw, newMessages), 800)
      }
    } catch (e) {
      setMessages(m => [...m, { role: 'system', text: `Error: ${e.message}`, ts: Date.now() }])
    }
    setLoading(false)
  }, [input, messages, rawText, functional, nonFunctional, loading, analyzing, session, upgraded])

  // ── Full analysis when all gaps resolved ─────────────────────────────────
  const triggerAnalysis = async (text, msgs) => {
    setAnalyzing(true)
    setMessages(m => [...m, {
      role: 'ai',
      text: 'All essential information collected. Running multi-agent extraction pipeline...',
      ts: Date.now(),
    }])
    try {
      const result = await analyzeConvo({
        conversation: text,
        provider:     session.provider,
        persona:      session.persona,
        project_name: session.project_name,
        client_name:  session.client_name,
        domain:       session.domain,
        signals:      session.signals || {},
      })
      setFunctional(result.functional || [])
      setNFR(result.non_functional || [])
      onComplete({
        conversation: text,
        messages:     msgs,
        analysis:     result,
        gapReport:    result.gap_report,
        prd_type:     result.prd_type || session.prd_type,
      })
    } catch (e) {
      setMessages(m => [...m, { role: 'system', text: `Analysis error: ${e.message}`, ts: Date.now() }])
      setAnalyzing(false)
    }
  }

  // ── Mic — Web Speech API, 100 % local, no API key ─────────────────────────
  const toggleMic = () => {
    setMicError('')

    // STOP if already listening
    if (listening) {
      recRef.current?.stop()
      // onend will fire → setListening(false)
      return
    }

    if (!SR_CLASS) {
      setMicError('Your browser does not support speech recognition. Try Chrome or Edge.')
      return
    }

    const rec = new SR_CLASS()
    rec.lang            = 'en-US'
    rec.continuous      = true   // keep listening until we stop()
    rec.interimResults  = true   // show live partial results

    rec.onstart = () => setListening(true)

    rec.onresult = (e) => {
      let finalText  = ''
      let interimText = ''
      for (let i = 0; i < e.results.length; i++) {
        const r = e.results[i]
        if (r.isFinal) {
          finalText += r[0].transcript + ' '
        } else {
          interimText += r[0].transcript
        }
      }
      // Combine committed finals + current interim, then show in input
      const combined = (interimRef.current + finalText).trim()
      if (finalText) interimRef.current = combined
      setInput((combined + (interimText ? ' ' + interimText : '')).trim())
    }

    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'permission-denied') {
        setMicError('Microphone permission denied. Allow mic access in your browser settings.')
      } else if (e.error === 'no-speech') {
        setMicError("No speech detected. Make sure your mic is on and speak clearly.")
      } else if (e.error !== 'aborted') {
        setMicError(`Mic error: ${e.error}`)
      }
      setListening(false)
    }

    rec.onend = () => {
      setListening(false)
      // Focus input so user can edit/send
      setTimeout(() => inputRef.current?.focus(), 100)
    }

    recRef.current = rec
    rec.start()
  }

  // ── Audio file upload → mock/server transcription ─────────────────────────
  const handleAudioUpload = async (file) => {
    setAudioFile(file)
    setTranscribing(true)
    setMessages(m => [...m, { role: 'system', text: `Uploading "${file.name}" for transcription...`, ts: Date.now() }])

    try {
      // Use FormData + fetch directly so we don't need the Gemini key
      const form = new FormData()
      form.append('file', file)
      form.append('provider', 'mock')   // always mock — no API key needed

      const r = await fetch('/api/transcribe', { method: 'POST', body: form })
      if (!r.ok) throw new Error(await r.text())
      const res = await r.json()

      const transcript = res.transcript
      setRawText(transcript)
      setMessages(m => [...m, {
        role: 'ai',
        text: `Audio transcribed (${res.word_count} words). Detected PRD type: **${res.prd_type}**.\n\nI've analysed the transcript. Here's my first gap-filling question:\n\n${res.gap_report?.next_question || 'Tell me more about the project.'}`,
        ts: Date.now(),
      }])
      setGapReport(res.gap_report)
      onUpdate({
        gapReport:  res.gap_report,
        prd_type:   res.prd_type,
        completion: Math.round((res.gap_report?.completion_score || 0) * 100),
      })

      if (res.gap_report?.is_complete) {
        setTimeout(() => triggerAnalysis(transcript, messages), 800)
      }
    } catch (e) {
      setMessages(m => [...m, { role: 'system', text: `Transcription failed: ${e.message}`, ts: Date.now() }])
    }
    setTranscribing(false)
    setShowAudioMode(false)
  }

  const canFinish = gapReport && gapReport.critical_open === 0
  const scoreColor = !gapReport ? 'var(--text3)'
    : gapReport.is_complete    ? 'var(--green)'
    : gapReport.critical_open > 0 ? 'var(--red)'
    : 'var(--orange)'

  return (
    <div className={styles.layout}>
      {/* ── Chat panel ── */}
      <div className={styles.chatPanel}>

        {/* Header */}
        <div className={styles.chatHeader}>
          <div className={styles.agentInfo}>
            <div className={styles.agentAvatar}><AgentIcon /></div>
            <div>
              <div className={styles.agentName}>AI Solutions Architect</div>
              <div className={styles.agentStatus} style={{
                color: analyzing ? 'var(--orange)' : loading ? 'var(--accent2)' : 'var(--green)',
              }}>
                {analyzing ? 'Extracting requirements...' : loading ? 'Thinking...' : 'Active'}
              </div>
            </div>
          </div>
          <div className={styles.headerMeta}>
            {upgraded && <span className={styles.upgradedTag}>Tech Mode</span>}
            {gapReport && (
              <div className={styles.scoreChip} style={{ color: scoreColor, borderColor: scoreColor }}>
                {Math.round((gapReport.completion_score || 0) * 100)}% complete
              </div>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className={styles.messages}>
          {messages.map((m, i) => <Message key={i} msg={m} />)}
          {(loading || analyzing || transcribing) && <TypingDots />}
          <div ref={bottomRef} />
        </div>

        {/* Audio file mode banner */}
        {showAudioMode && (
          <div className={styles.audioBanner}>
            <div className={styles.audioBannerLeft}>
              <AudioFileIcon />
              <div>
                <div className={styles.audioBannerTitle}>Upload Audio File</div>
                <div className={styles.audioBannerSub}>
                  Upload a .wav / .mp3 recording of your requirements discussion
                </div>
              </div>
            </div>
            <div className={styles.audioBannerRight}>
              <button className={styles.uploadFileBtn} onClick={() => fileRef.current?.click()}>
                <UploadIcon /> Choose File
              </button>
              <input ref={fileRef} type="file" accept="audio/*" style={{ display: 'none' }}
                onChange={e => { if (e.target.files[0]) handleAudioUpload(e.target.files[0]) }} />
              {audioFile && <span className={styles.fileChip}>{audioFile.name}</span>}
              <button className={styles.closeBannerBtn} onClick={() => setShowAudioMode(false)}>✕</button>
            </div>
          </div>
        )}

        {/* Input area */}
        {!analyzing && (
          <div className={styles.inputArea}>

            {/* mic error banner */}
            {micError && (
              <div className={styles.micErrorBar}>
                <span>⚠ {micError}</span>
                <button onClick={() => setMicError('')}>✕</button>
              </div>
            )}

            <div className={styles.inputRow}>
              {/* Live mic indicator */}
              {listening && (
                <div className={styles.listeningBadge}>
                  <WaveAnim />
                  <span>Listening… speak now</span>
                </div>
              )}

              <textarea
                ref={inputRef}
                className={`${styles.chatInput} ${listening ? styles.chatInputListening : ''}`}
                value={input}
                onChange={e => { setInput(e.target.value); interimRef.current = '' }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
                }}
                placeholder={listening
                  ? 'Speak now — text appears here as you talk…'
                  : 'Type your answer… (Enter to send, Shift+Enter for newline)'
                }
                rows={2}
                disabled={loading || analyzing}
              />

              <div className={styles.inputButtons}>
                {/* Mic button — always shown, error shown below if unsupported */}
                <MicButton listening={listening} onClick={toggleMic} />

                {/* Upload audio file */}
                <button
                  className={styles.audioUploadBtn}
                  onClick={() => setShowAudioMode(v => !v)}
                  title="Upload audio file"
                >
                  <AudioFileIcon />
                </button>

                <SendButton
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || loading || analyzing}
                />
              </div>
            </div>

            {/* Tip when mic is listening */}
            {listening && (
              <div className={styles.micTip}>
                Press the mic button again to stop, then press Send (or Enter)
              </div>
            )}

            {canFinish && !gapReport.is_complete && (
              <button className={styles.finishEarlyBtn}
                onClick={() => triggerAnalysis(rawText, messages)}>
                Critical gaps resolved — Generate PRD now →
              </button>
            )}
          </div>
        )}
      </div>

      {/* Gap sidebar */}
      <GapSidebar gapReport={gapReport} loading={loading} />
    </div>
  )
}

// ── Message bubble ────────────────────────────────────────────────────────────
function Message({ msg }) {
  const isAI     = msg.role === 'ai'
  const isSystem = msg.role === 'system'
  const render = (text) => text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .split('\n')
    .map(l => `<span>${l || '&nbsp;'}</span>`)
    .join('<br/>')
  return (
    <div className={`${styles.msgWrap} ${isAI ? styles.msgWrapAI : isSystem ? styles.msgWrapSys : styles.msgWrapUser}`}>
      {isAI && <div className={styles.msgAvatar}><AgentIcon /></div>}
      <div className={`${styles.bubble} ${isAI ? styles.bubbleAI : isSystem ? styles.bubbleSys : styles.bubbleUser}`}
        dangerouslySetInnerHTML={{ __html: render(msg.text) }} />
    </div>
  )
}

function TypingDots() {
  return (
    <div className={`${styles.msgWrap} ${styles.msgWrapAI}`}>
      <div className={styles.msgAvatar}><AgentIcon /></div>
      <div className={`${styles.bubble} ${styles.bubbleAI}`}>
        <div className={styles.dots}><span /><span /><span /></div>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────
function MicButton({ listening, onClick }) {
  return (
    <button
      className={`${styles.micBtn} ${listening ? styles.micBtnActive : ''}`}
      onClick={onClick}
      title={listening ? 'Stop recording' : 'Start voice input (browser speech recognition)'}
    >
      {listening ? <StopIcon /> : <MicIconSvg />}
      {listening && <span className={styles.micRing} />}
    </button>
  )
}

function WaveAnim() {
  return (
    <div className={styles.wave}>
      {[0.1, 0.2, 0.3, 0.2, 0.1].map((d, i) => (
        <span key={i} style={{ animationDelay: `${d}s` }} />
      ))}
    </div>
  )
}

// ── Icons ─────────────────────────────────────────────────────────────────────
function AgentIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent2)" strokeWidth="1.8"><path d="M12 2a9 9 0 0 1 9 9v3a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v-3a9 9 0 0 1 9-9z" /><path d="M9 14v2M15 14v2M8 9h.01M16 9h.01" /></svg>
}
function MicIconSvg() {
  return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
}
function StopIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
}
function SendIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
}
function UploadIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
}
function AudioFileIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></svg>
}
function SendButton({ onClick, disabled }) {
  return (
    <button className={styles.sendBtn} onClick={onClick} disabled={disabled}>
      <SendIcon />
    </button>
  )
}
