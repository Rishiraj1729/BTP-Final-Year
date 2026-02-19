import styles from './GapsPanel.module.css'

const SEV_COLOR = {
  high:   { bg: 'rgba(239,68,68,.12)',  text: '#ef4444', border: 'rgba(239,68,68,.3)' },
  medium: { bg: 'rgba(245,158,11,.12)', text: '#f59e0b', border: 'rgba(245,158,11,.3)' },
  low:    { bg: 'rgba(34,197,94,.12)',  text: '#22c55e', border: 'rgba(34,197,94,.3)' },
}

const CAT_LABEL = {
  missing_detail:       'Missing Detail',
  conflict:             'Conflict',
  vague_term:           'Vague Term',
  implicit_requirement: 'Implicit',
}

export default function GapsPanel({ gaps }) {
  if (!gaps?.length) {
    return (
      <div className={styles.empty}>
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10"/>
          <path d="m9 12 2 2 4-4"/>
        </svg>
        <p>No gaps detected — requirements look complete!</p>
      </div>
    )
  }

  const high   = gaps.filter(g => g.severity === 'high')
  const medium = gaps.filter(g => g.severity === 'medium')
  const low    = gaps.filter(g => g.severity === 'low')

  return (
    <div className={styles.container}>
      <div className={styles.summary}>
        <SevCount label="High" count={high.length} color="#ef4444" />
        <SevCount label="Medium" count={medium.length} color="#f59e0b" />
        <SevCount label="Low" count={low.length} color="#22c55e" />
      </div>
      <div className={styles.list}>
        {[...high, ...medium, ...low].map((g, i) => {
          const sev = SEV_COLOR[g.severity] || SEV_COLOR.medium
          return (
            <div key={i} className={styles.card}
              style={{ borderLeft: `3px solid ${sev.text}` }}>
              <div className={styles.cardHeader}>
                <span className={styles.gapId}>{g.id}</span>
                <span className={styles.catBadge}
                  style={{ background: sev.bg, color: sev.text, border: `1px solid ${sev.border}` }}>
                  {CAT_LABEL[g.category] || g.category}
                </span>
                <span className={styles.sevBadge}
                  style={{ color: sev.text }}>
                  {g.severity?.toUpperCase()}
                </span>
                {g.resolved && <span className={styles.resolved}>Resolved</span>}
              </div>
              <p className={styles.desc}>{g.description}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SevCount({ label, count, color }) {
  if (!count) return null
  return (
    <div className={styles.sevCount}>
      <span style={{ color, fontSize: '1.4rem', fontWeight: 700 }}>{count}</span>
      <span style={{ fontSize: '.75rem', color: '#64748b' }}>{label}</span>
    </div>
  )
}

