import styles from './ArchPanel.module.css'

export default function ArchPanel({ arch }) {
  if (!arch) return <p style={{ color: 'var(--muted)' }}>No architecture hints available.</p>

  const sections = [
    { label: 'System Layers',      items: arch.suggested_layers,    icon: '⬡', color: '#6366f1' },
    { label: 'Suggested Tech',     items: arch.suggested_tech,      icon: '⬢', color: '#3b82f6' },
    { label: 'Integration Points', items: arch.integration_points,  icon: '⟳', color: '#f59e0b' },
    { label: 'Deployment Notes',   items: arch.deployment_notes,    icon: '⬖', color: '#22c55e' },
  ]

  return (
    <div className={styles.grid}>
      {sections.map(s => (
        <div key={s.label} className={styles.card}>
          <div className={styles.cardTitle} style={{ color: s.color }}>
            <span>{s.icon}</span> {s.label}
          </div>
          {s.items?.length > 0 ? (
            <ul className={styles.list}>
              {s.items.map((item, i) => (
                <li key={i} className={styles.item}>
                  <span className={styles.dot} style={{ background: s.color }} />
                  {item}
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>Not detected — to be defined.</p>
          )}
        </div>
      ))}
    </div>
  )
}

