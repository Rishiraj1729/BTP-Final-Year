/**
 * Phase 1 — Discovery
 * Guided interview with voice + text input.
 * Steps through master_reference discovery questions one by one.
 * Auto-detects jargon mid-session to upgrade persona silently.
 */
import { useState, useEffect, useRef } from 'react'
import { fetchDiscovery, detectTone, analyzeConvo } from '../api'
import VoiceRecorder from '../components/VoiceRecorder'
import styles from './Discovery.module.css'

export default function Discovery({ session, onComplete, onUpdate }) {
  const [questions,   setQuestions]   = useState([])
  const [qIndex,      setQIndex]      = useState(0)
  const [answers,     setAnswers]     = useState({})
  const [currentText, setCurrentText] = useState('')
  const [messages,    setMessages]    = useState(session.messages || [])
  const [loading,     setLoading]     = useState(false)
  const [analyzing,   setAnalyzing]   = useState(false)
  const [jargonBadge, setJargonBadge] = useState(null)   // null | "upgraded"
  const endRef = useRef(null)

  useEffect(() => {
    fetchDiscovery()
      .then(d => {
        setQuestions(d.questions || [])
        // Push first question as AI message
        const first = d.questions?.[0]
        if (first) {
          setMessages(prev => [...prev, { role: 'ai', text: first.question, ts: Date.now() }])
        }
      })
      .catch(() => setQuestions([]))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const currentQ = questions[qIndex]

  const handleSend = async (text) => {
    const trimmed = (text || currentText).trim()
    if (!trimmed) return

    const userMsg = { role: 'user', text: trimmed, ts: Date.now() }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setCurrentText('')
    setLoading(true)

    // Record answer
    const updatedAnswers = { ...answers }
    if (currentQ) {
      updatedAnswers[currentQ.gate] = trimmed
      setAnswers(updatedAnswers)
    }

    // Tone check mid-session
    try {
      const toneRes = await detectTone({ message: trimmed, stated_level: session.level })
      if (toneRes.detected_level === 'technical' && session.level === 'business' && toneRes.jargon_count >= 2) {
        setJargonBadge('upgraded')
        onUpdate({ level: 'technical', persona: 'CTO' })
        setMessages(m => [...m, {
          role: 'system',
          text: "I've detected technical vocabulary — upgrading our conversation to architect-level depth.",
          ts: Date.now()
        }])
      }
    } catch { /* ignore */ }

    // Move to next question or finish
    const nextIndex = qIndex + 1
    if (nextIndex < questions.length) {
      const nextQ = questions[nextIndex]
      setQIndex(nextIndex)
      setTimeout(() => {
        setMessages(m => [...m, { role: 'ai', text: nextQ.question, ts: Date.now() }])
        setLoading(false)
      }, 600)
    } else {
      // All questions answered — run analysis
      setLoading(false)
      await runAnalysis(newMessages, updatedAnswers)
    }
  }

  const runAnalysis = async (msgs, ans) => {
    setAnalyzing(true)
    setMessages(m => [...m, {
      role: 'ai',
      text: "Excellent! I have enough to start extracting requirements. Running analysis...",
      ts: Date.now()
    }])

    const fullConvo = msgs
      .filter(m => m.role === 'user')
      .map(m => `Client: ${m.text}`)
      .join('\n')

    // Extract signals from answers
    const signals = buildSignals(ans, fullConvo)

    try {
      const result = await analyzeConvo({
        conversation: fullConvo,
        provider: session.provider,
        persona: session.persona,
        project_name: session.project_name,
        client_name:  session.client_name,
        domain:       session.domain,
        signals,
      })
      onComplete({
        conversation: fullConvo,
        messages: msgs,
        signals,
        analysis: result,
      })
    } catch (e) {
      setMessages(m => [...m, { role: 'system', text: `Analysis error: ${e.message}`, ts: Date.now() }])
      setAnalyzing(false)
    }
  }

  const handleSkip = () => {
    if (qIndex < questions.length - 1) {
      const nextQ = questions[qIndex + 1]
      setQIndex(qIndex + 1)
      setMessages(m => [...m, { role: 'ai', text: nextQ.question, ts: Date.now() }])
    }
  }

  const handleFinishEarly = async () => {
    const fullConvo = messages
      .filter(m => m.role === 'user')
      .map(m => `Client: ${m.text}`)
      .join('\n')
    if (fullConvo.trim()) {
      await runAnalysis(messages, answers)
    }
  }

  const progress = questions.length ? Math.round((qIndex / questions.length) * 100) : 0

  return (
    <div className={styles.page}>
      {/* Progress bar */}
      <div className={styles.progressBar}>
        <div className={styles.progressFill} style={{ width: `${progress}%` }} />
      </div>

      <div className={styles.layout}>
        {/* Chat panel */}
        <div className={styles.chatPanel}>
          {/* Header */}
          <div className={styles.chatHeader}>
            <div className={styles.aiAvatar}><AIIcon /></div>
            <div>
              <div className={styles.aiName}>Solutions Architect AI</div>
              <div className={styles.aiStatus}>
                {analyzing ? 'Analyzing...' : loading ? 'Thinking...' : 'Active'}
              </div>
            </div>
            <div className={styles.headerRight}>
              {jargonBadge && <span className={styles.upgradedBadge}>Tech Upgraded</span>}
              <span className={styles.qCount}>{Math.min(qIndex + 1, questions.length)} / {questions.length}</span>
            </div>
          </div>

          {/* Messages */}
          <div className={styles.messages}>
            {messages.map((m, i) => (
              <ChatBubble key={i} msg={m} />
            ))}
            {(loading || analyzing) && <TypingIndicator />}
            <div ref={endRef} />
          </div>

          {/* Input */}
          {!analyzing && (
            <div className={styles.inputArea}>
              <div className={styles.inputRow}>
                <textarea
                  className={styles.chatInput}
                  value={currentText}
                  onChange={e => setCurrentText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                  placeholder="Type your answer... (Enter to send, Shift+Enter for newline)"
                  rows={2}
                  disabled={loading}
                />
                <VoiceRecorder onTranscript={t => setCurrentText(t)} />
                <button
                  className={styles.sendBtn}
                  onClick={() => handleSend()}
                  disabled={!currentText.trim() || loading}
                >
                  <SendIcon />
                </button>
              </div>
              <div className={styles.inputActions}>
                {qIndex < questions.length - 1 && (
                  <button className={styles.skipBtn} onClick={handleSkip}>Skip question</button>
                )}
                {qIndex > 2 && (
                  <button className={styles.finishBtn} onClick={handleFinishEarly}>
                    I've covered everything — analyze now
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Side panel */}
        <aside className={styles.sidePanel}>
          <div className={styles.sessionCard}>
            <h3 className={styles.sideTitle}>Session</h3>
            <InfoRow label="Project" value={session.project_name} />
            <InfoRow label="Domain"  value={session.domain} />
            <InfoRow label="Persona" value={session.persona} />
            <InfoRow label="Provider" value={session.provider} />
          </div>
          <div className={styles.sessionCard}>
            <h3 className={styles.sideTitle}>Gates Collected</h3>
            {questions.map((q, i) => (
              <GateRow key={q.id} label={q.gate.replace(/_/g, ' ')} done={i < qIndex} />
            ))}
          </div>
        </aside>
      </div>
    </div>
  )
}

function ChatBubble({ msg }) {
  const isAI     = msg.role === 'ai'
  const isSystem = msg.role === 'system'
  return (
    <div className={`${styles.bubble} ${isAI ? styles.bubbleAI : isSystem ? styles.bubbleSystem : styles.bubbleUser}`}>
      <div className={styles.bubbleText}>{msg.text}</div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className={`${styles.bubble} ${styles.bubbleAI}`}>
      <div className={styles.typing}>
        <span/><span/><span/>
      </div>
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className={styles.infoRow}>
      <span className={styles.infoLabel}>{label}</span>
      <span className={styles.infoValue}>{value || '—'}</span>
    </div>
  )
}

function GateRow({ label, done }) {
  return (
    <div className={styles.gateRow}>
      <span className={`${styles.gateDot} ${done ? styles.gateDotDone : ''}`}>{done ? '✓' : ''}</span>
      <span className={`${styles.gateLabel} ${done ? styles.gateLabelDone : ''}`}>{label}</span>
    </div>
  )
}

function buildSignals(answers, fullText) {
  const text = fullText.toLowerCase()
  return {
    has_realtime:    /real.?time|live|websocket|socket/.test(text),
    has_payments:    /pay|payment|stripe|razorpay|billing/.test(text),
    has_media:       /upload|image|video|media|file/.test(text),
    mobile_required: /mobile|ios|android|app/.test(text),
    dashboard_heavy: /dashboard|analytics|chart|report|graph/.test(text),
    has_search:      /search|filter|find/.test(text),
    has_pii:         /personal|pii|medical|health|finance|gdpr/.test(text),
    scale_answer:    answers['scale'] || '',
    features_answer: answers['features'] || '',
  }
}

function AIIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#7c9bff" strokeWidth="1.8">
      <path d="M12 2a9 9 0 0 1 9 9v4a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2 7 7 0 1 0-14 0 2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v-4a9 9 0 0 1 9-9z"/>
    </svg>
  )
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
      <line x1="22" y1="2" x2="11" y2="13"/>
      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>
  )
}

