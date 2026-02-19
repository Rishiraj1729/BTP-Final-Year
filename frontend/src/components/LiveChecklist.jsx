/**
 * LiveChecklist
 * The signature feature — animated gate checklist that turns green
 * only when SMART criteria are satisfied for each category.
 */
import styles from './LiveChecklist.module.css'

const GATES = [
  { key: 'features',     label: 'Core Features',       icon: '⬡', desc: 'FR with acceptance criteria' },
  { key: 'roles',        label: 'Roles & Actors',       icon: '◈', desc: 'All actors identified' },
  { key: 'performance',  label: 'Performance (SMART)',  icon: '◉', desc: 'Response time quantified' },
  { key: 'security',     label: 'Security (SMART)',     icon: '◈', desc: 'Auth + compliance defined' },
  { key: 'scalability',  label: 'Scalability (SMART)',  icon: '◉', desc: 'User volume specified' },
  { key: 'availability', label: 'Availability (SMART)', icon: '◆', desc: 'SLA + RTO/RPO defined' },
]

export default function LiveChecklist({ audit, architecture, loading }) {
  const gates = audit?.gate_status || {}
  const score = audit ? Math.round((audit.overall_smart_score || 0) * 100) : 0
  const allPass = GATES.every(g => gates[g.key] === 'pass')

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>SMART Gates</span>
        {!loading && audit && (
          <span className={`${styles.scoreBadge} ${score >= 70 ? styles.scoreGood : score >= 40 ? styles.scoreMid : styles.scoreBad}`}>
            {score}%
          </span>
        )}
      </div>

      <div className={styles.gateList}>
        {GATES.map(gate => {
          const status = loading ? 'pending' : (gates[gate.key] || 'pending')
          return (
            <GateItem
              key={gate.key}
              gate={gate}
              status={status}
            />
          )
        })}
      </div>

      {allPass && !loading && (
        <div className={styles.clearBanner}>
          <span className={styles.clearIcon}>✓</span>
          <div>
            <div className={styles.clearTitle}>All Gates Clear!</div>
            <div className={styles.clearSub}>Ready for PRD generation</div>
          </div>
        </div>
      )}

      {architecture && !loading && (
        <>
          <div className={styles.divider} />
          <div className={styles.archSummary}>
            <div className={styles.archTitle}>Architecture</div>
            <ArchRow icon="🗄" label="Database" value={architecture.database_primary} />
            <ArchRow icon="☁" label="Hosting"  value={architecture.hosting_platform?.split(' ')[0]} />
            <ArchRow icon="🔐" label="Auth"     value={architecture.auth_method?.split(' ')[0]} />
            <ArchRow icon="⚡" label="API"      value={architecture.api_style} />
            <ArchRow icon="🏗" label="Pattern"  value={architecture.architecture_pattern} />
            <div className={styles.scaleTier}>
              <span>Scale tier:</span>
              <ScaleBadge tier={architecture.scale_tier} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function GateItem({ gate, status }) {
  const isPending = status === 'pending'
  const isPass    = status === 'pass'
  const isFail    = status === 'fail'

  return (
    <div className={`${styles.gate} ${isPass ? styles.gatePass : isFail ? styles.gateFail : ''}`}>
      <div className={styles.gateLeft}>
        <div className={`${styles.gateIcon} ${isPass ? styles.gateIconPass : isFail ? styles.gateIconFail : styles.gateIconPending}`}>
          {isPending ? <PendingDot /> : isPass ? <CheckMark /> : <CrossMark />}
        </div>
        <div className={styles.gateInfo}>
          <div className={styles.gateName}>{gate.label}</div>
          <div className={styles.gateDesc}>{gate.desc}</div>
        </div>
      </div>
      <div className={`${styles.gateStatus} ${isPass ? styles.statusPass : isFail ? styles.statusFail : styles.statusPending}`}>
        {isPass ? 'PASS' : isFail ? 'FAIL' : '...'}
      </div>
    </div>
  )
}

function ArchRow({ icon, label, value }) {
  return (
    <div className={styles.archRow}>
      <span className={styles.archRowIcon}>{icon}</span>
      <span className={styles.archRowLabel}>{label}</span>
      <span className={styles.archRowValue}>{value || '—'}</span>
    </div>
  )
}

function ScaleBadge({ tier }) {
  const colors = {
    small:      { bg: 'rgba(34,197,94,.12)',  fg: '#22c55e' },
    medium:     { bg: 'rgba(245,158,11,.12)', fg: '#f59e0b' },
    large:      { bg: 'rgba(239,68,68,.12)',  fg: '#ef4444' },
    enterprise: { bg: 'rgba(168,85,247,.12)', fg: '#a855f7' },
  }
  const c = colors[tier] || colors.small
  return (
    <span className={styles.scaleBadge} style={{ background: c.bg, color: c.fg }}>
      {tier?.toUpperCase() || 'SMALL'}
    </span>
  )
}

function PendingDot() {
  return <span className={styles.pendingDot} />
}

function CheckMark() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}

function CrossMark() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <line x1="18" y1="6" x2="6" y2="18"/>
      <line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  )
}

