export default function CompletionMeter({ score }) {
  const pct = Math.round((score || 0) * 100)
  const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginLeft: 'auto' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
        <span style={{ fontSize: '.65rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '.05em' }}>Completeness</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 80, height: 6, background: '#1e2436', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width .5s ease' }} />
          </div>
          <span style={{ fontSize: '.85rem', fontWeight: 700, color }}>{pct}%</span>
        </div>
      </div>
    </div>
  )
}

