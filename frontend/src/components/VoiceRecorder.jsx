/**
 * VoiceRecorder — uses Web Speech API for browser-native voice-to-text.
 * Falls back gracefully if the browser doesn't support it.
 */
import { useState, useRef } from 'react'
import styles from './VoiceRecorder.module.css'

export default function VoiceRecorder({ onTranscript }) {
  const [listening, setListening] = useState(false)
  const [supported] = useState(() => 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window)
  const recRef = useRef(null)

  const toggle = () => {
    if (!supported) return
    if (listening) {
      recRef.current?.stop()
      setListening(false)
      return
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.maxAlternatives = 1
    rec.continuous = false

    rec.onresult = (e) => {
      const transcript = e.results[0][0].transcript
      onTranscript(transcript)
      setListening(false)
    }
    rec.onerror  = () => setListening(false)
    rec.onend    = () => setListening(false)

    recRef.current = rec
    rec.start()
    setListening(true)
  }

  if (!supported) return null

  return (
    <button
      className={`${styles.btn} ${listening ? styles.listening : ''}`}
      onClick={toggle}
      title={listening ? 'Click to stop' : 'Click to speak'}
      type="button"
    >
      {listening ? <StopIcon /> : <MicIcon />}
      {listening && <span className={styles.pulse} />}
    </button>
  )
}

function MicIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  )
}

function StopIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2"/>
    </svg>
  )
}

