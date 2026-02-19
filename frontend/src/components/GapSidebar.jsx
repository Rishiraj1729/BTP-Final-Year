/**
 * GapSidebar — live gap tracking panel
 * Shows critical / important gates, completion score, and what's still missing.
 */
import styles from './GapSidebar.module.css'

const PRIORITY_META = {
  critical:     { color:'var(--red)',    label:'Critical', bg:'rgba(239,68,68,.08)',   border:'rgba(239,68,68,.2)'   },
  important:    { color:'var(--orange)', label:'Important', bg:'rgba(245,158,11,.08)', border:'rgba(245,158,11,.2)'  },
  nice_to_have: { color:'var(--text3)',  label:'Optional',  bg:'rgba(255,255,255,.03)', border:'var(--border)'        },
}

export default function GapSidebar({ gapReport, loading }) {
  const score = Math.round((gapReport?.completion_score || 0) * 100)
  const isComplete = gapReport?.is_complete
  const openGaps   = gapReport?.open_gaps || []
  const resolved   = gapReport?.resolved_gaps || []

  const critOpen  = openGaps.filter(g => g.priority === 'critical')
  const impOpen   = openGaps.filter(g => g.priority === 'important')

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHeader}>
        <div className={styles.sidebarTitle}>Requirements Gaps</div>
        {loading && <div className={styles.sidebarLoading}><Spin/></div>}
      </div>

      {/* Score arc */}
      <div className={styles.scoreSection}>
        <ScoreArc score={score} isComplete={isComplete} />
        <div className={styles.scoreStats}>
          <StatChip label="Critical" value={critOpen.length} color="var(--red)"    />
          <StatChip label="Important" value={impOpen.length} color="var(--orange)" />
          <StatChip label="Resolved" value={resolved.length} color="var(--green)"  />
        </div>
      </div>

      {isComplete && (
        <div className={styles.completeBanner}>
          <CheckCircle /> All critical gates cleared — ready for PRD generation!
        </div>
      )}

      {/* Gap list */}
      <div className={styles.gapList}>
        {critOpen.length > 0 && (
          <GapGroup title="Critical Gaps" gaps={critOpen} meta={PRIORITY_META.critical} />
        )}
        {impOpen.length > 0 && (
          <GapGroup title="Important" gaps={impOpen} meta={PRIORITY_META.important} />
        )}
        {resolved.length > 0 && (
          <ResolvedGroup gates={resolved} />
        )}
        {!gapReport && (
          <div className={styles.emptyState}>
            <EmptyIcon/>
            <span>Gap analysis updates as you chat</span>
          </div>
        )}
      </div>

      {/* PRD type */}
      {gapReport?.prd_type_detected && (
        <div className={styles.typeDetected}>
          <span className={styles.typeLabel}>Detected Type</span>
          <span className={styles.typeValue}>{gapReport.prd_type_detected.replace('_',' ').toUpperCase()}</span>
        </div>
      )}
    </aside>
  )
}

function GapGroup({ title, gaps, meta }) {
  return (
    <div className={styles.gapGroup}>
      <div className={styles.gapGroupTitle} style={{color:meta.color}}>{title}</div>
      {gaps.map(g => (
        <div key={g.id} className={styles.gapCard}
          style={{background:meta.bg, borderColor:meta.border}}
        >
          <div className={styles.gapCardTop}>
            <span className={styles.gapId} style={{color:meta.color}}>{g.id}</span>
            <span className={styles.gapGate}>{g.gate.replace('_',' ')}</span>
          </div>
          <div className={styles.gapQuestion}>{g.question}</div>
        </div>
      ))}
    </div>
  )
}

function ResolvedGroup({ gates }) {
  return (
    <div className={styles.gapGroup}>
      <div className={styles.gapGroupTitle} style={{color:'var(--green)'}}>Resolved ({gates.length})</div>
      <div className={styles.resolvedList}>
        {gates.map(g => (
          <div key={g} className={styles.resolvedChip}>
            <span className={styles.checkMark}>✓</span>
            {g.replace('_',' ')}
          </div>
        ))}
      </div>
    </div>
  )
}

function ScoreArc({ score, isComplete }) {
  const r     = 38
  const circ  = 2 * Math.PI * r
  const fill  = circ * (1 - score / 100)
  const color = isComplete ? 'var(--green)' : score >= 60 ? 'var(--orange)' : 'var(--red)'

  return (
    <div className={styles.arc}>
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--surface3)" strokeWidth="7"/>
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="7"
          strokeDasharray={circ} strokeDashoffset={fill}
          strokeLinecap="round" transform="rotate(-90 50 50)"
          style={{transition:'stroke-dashoffset .7s ease'}}
        />
        <text x="50" y="46" textAnchor="middle" fill={color} fontSize="16" fontWeight="900">{score}%</text>
        <text x="50" y="60" textAnchor="middle" fill="var(--text3)" fontSize="9" fontWeight="600">COMPLETE</text>
      </svg>
    </div>
  )
}

function StatChip({ label, value, color }) {
  return (
    <div className={styles.statChip}>
      <span className={styles.statVal} style={{color}}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}

function CheckCircle() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
}
function EmptyIcon() {
  return <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text4)" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
}
function Spin() {
  return <span style={{width:14,height:14,border:'2px solid var(--border2)',borderTopColor:'var(--accent)',borderRadius:'50%',display:'inline-block',animation:'spin .7s linear infinite'}}/>
}

