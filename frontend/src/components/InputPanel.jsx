import { useState, useEffect } from 'react'
import { fetchPersonas } from '../api'
import styles from './InputPanel.module.css'

const PROVIDERS = [
  { value: 'mock',   label: 'Mock (offline)', icon: '⚡' },
  { value: 'groq',   label: 'Groq',           icon: '🦙' },
  { value: 'gemini', label: 'Gemini',          icon: '✦' },
]

export default function InputPanel({ form, onChange, onRun, loading }) {
  const [personas, setPersonas] = useState([])

  useEffect(() => {
    fetchPersonas()
      .then(d => setPersonas(d.personas || []))
      .catch(() => setPersonas([
        { name: 'PM' }, { name: 'CTO' }, { name: 'Dev' },
        { name: 'QA' }, { name: 'Investor' }, { name: 'Client' },
      ]))
  }, [])

  const set = (key, val) => onChange(prev => ({ ...prev, [key]: val }))

  return (
    <div className={styles.panel}>
      <div className={styles.section}>
        <label className={styles.label}>Conversation / Transcript</label>
        <textarea
          className={styles.textarea}
          value={form.conversation}
          onChange={e => set('conversation', e.target.value)}
          placeholder="Paste client conversation here..."
          rows={10}
        />
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label}>Project</label>
          <input className={styles.input} value={form.project_name} onChange={e => set('project_name', e.target.value)} placeholder="Project name" />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Client</label>
          <input className={styles.input} value={form.client_name} onChange={e => set('client_name', e.target.value)} placeholder="Client name" />
        </div>
      </div>

      <div className={styles.field}>
        <label className={styles.label}>Domain / Industry</label>
        <input className={styles.input} value={form.domain} onChange={e => set('domain', e.target.value)} placeholder="e.g. FinTech, HealthCare" />
      </div>

      <div className={styles.field}>
        <label className={styles.label}>LLM Provider</label>
        <div className={styles.providerGrid}>
          {PROVIDERS.map(p => (
            <button
              key={p.value}
              className={`${styles.providerBtn} ${form.provider === p.value ? styles.providerActive : ''}`}
              onClick={() => set('provider', p.value)}
              type="button"
            >
              <span>{p.icon}</span>
              <span>{p.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className={styles.field}>
        <label className={styles.label}>Output Persona</label>
        <div className={styles.personaGrid}>
          {personas.map(p => (
            <button
              key={p.name}
              className={`${styles.personaBtn} ${form.persona === p.name ? styles.personaActive : ''}`}
              onClick={() => set('persona', p.name)}
              type="button"
              title={p.focus?.join(', ')}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      <button
        className={styles.runBtn}
        onClick={onRun}
        disabled={loading || !form.conversation.trim()}
      >
        {loading
          ? <><Spin /> Generating...</>
          : <><RocketIcon /> Generate PRD</>
        }
      </button>
    </div>
  )
}

function Spin() {
  return (
    <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(255,255,255,.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin2 .7s linear infinite' }}>
      <style>{`@keyframes spin2 { to { transform: rotate(360deg); } }`}</style>
    </span>
  )
}

function RocketIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>
    </svg>
  )
}

