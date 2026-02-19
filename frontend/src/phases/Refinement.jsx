/**
 * Refinement — Phase 2
 * Shows extracted requirements, runs audit, shows architecture decisions,
 * and prepares the PRD generation.
 */
import { useState, useEffect } from 'react'
import { runAudit } from '../api'
import styles from './Refinement.module.css'

export default function Refinement({ session, onComplete, onUpdate }) {
  const [auditResult, setAudit]   = useState(session.auditReport || null)
  const [arch,        setArch]    = useState(session.architecture || null)
  const [loading,     setLoading] = useState(false)
  const [error,       setError]   = useState('')
  const [personaChoice, setPersona] = useState(session.persona || 'PM')

  const analysis = session.analysis || {}
  const functional     = analysis.functional || []
  const nonFunctional  = analysis.non_functional || []
  const constraints    = analysis.constraints || []
  const assumptions    = analysis.assumptions || []

  useEffect(() => {
    if (!auditResult && functional.length > 0) runAuditNow()
  }, [])

  const runAuditNow = async () => {
    setLoading(true); setError('')
    try {
      const res = await runAudit({
        functional, non_functional: nonFunctional,
        raw_text: session.conversation || '',
        domain: session.domain || 'general',
        signals: session.signals || {},
      })
      setAudit(res.audit)
      setArch(res.architecture)
      onUpdate({ auditReport:res.audit, architecture:res.architecture })
    } catch(e) { setError(e.message) }
    setLoading(false)
  }

  const handleGenerate = () => {
    onComplete({ persona: personaChoice, auditReport: auditResult, architecture: arch })
  }

  const smartScore = Math.round((auditResult?.overall_smart_score || 0) * 100)

  return (
    <div className={styles.page}>
      <div className={styles.container}>

        {/* Summary header */}
        <div className={styles.summaryBar}>
          <div className={styles.summaryItem}>
            <span className={styles.summaryNum} style={{color:'var(--accent2)'}}>{functional.length}</span>
            <span className={styles.summaryLabel}>Functional Requirements</span>
          </div>
          <div className={styles.summaryDivider}/>
          <div className={styles.summaryItem}>
            <span className={styles.summaryNum} style={{color:'var(--cyan)'}}>{nonFunctional.length}</span>
            <span className={styles.summaryLabel}>Non-Functional</span>
          </div>
          <div className={styles.summaryDivider}/>
          <div className={styles.summaryItem}>
            <span className={styles.summaryNum} style={{color:'var(--orange)'}}>{constraints.length}</span>
            <span className={styles.summaryLabel}>Constraints</span>
          </div>
          <div className={styles.summaryDivider}/>
          <div className={styles.summaryItem}>
            <span className={styles.summaryNum} style={{color:auditResult?`hsl(${smartScore},80%,60%)`:'var(--text3)'}}>
              {auditResult ? `${smartScore}%` : '—'}
            </span>
            <span className={styles.summaryLabel}>SMART Score</span>
          </div>
        </div>

        <div className={styles.twoCol}>
          {/* Left — requirements */}
          <div className={styles.col}>
            <Section title="Functional Requirements" badge={functional.length} color="var(--accent2)">
              {functional.length ? functional.map(fr => (
                <ReqCard key={fr.id} item={fr} type="FR" />
              )) : <Empty text="No FRs extracted yet" />}
            </Section>

            <Section title="Non-Functional Requirements" badge={nonFunctional.length} color="var(--cyan)">
              {nonFunctional.length ? nonFunctional.map(nfr => (
                <ReqCard key={nfr.id} item={nfr} type="NFR" />
              )) : <Empty text="No NFRs extracted yet" />}
            </Section>
          </div>

          {/* Right — audit + architecture */}
          <div className={styles.col}>
            {loading && (
              <div className={styles.auditLoading}>
                <Spinner/> Running SMART audit & architecture decisions...
              </div>
            )}
            {error && <div className={styles.errBox}>{error}</div>}

            {auditResult && <AuditPanel audit={auditResult} />}
            {arch         && <ArchPanel  arch={arch}         />}
          </div>
        </div>

        {/* Persona selector + CTA */}
        <div className={styles.footer}>
          <div className={styles.personaSection}>
            <div className={styles.personaLabel}>Generate PRD for persona:</div>
            <PersonaPicker selected={personaChoice} onChange={setPersona} />
          </div>
          <div className={styles.footerActions}>
            {!auditResult && !loading && (
              <button className={styles.auditBtn} onClick={runAuditNow}>
                <AuditIcon/> Run SMART Audit
              </button>
            )}
            <button className={styles.generateBtn} onClick={handleGenerate} disabled={loading}>
              Generate PRD <Arrow/>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Section({ title, badge, color, children }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionHead}>
        <span className={styles.sectionTitle}>{title}</span>
        <span className={styles.sectionBadge} style={{background:`${color}15`,color,borderColor:`${color}30`}}>{badge}</span>
      </div>
      <div className={styles.sectionBody}>{children}</div>
    </div>
  )
}

function ReqCard({ item, type }) {
  const [open, setOpen] = useState(false)
  const color = type === 'FR' ? 'var(--accent2)' : 'var(--cyan)'
  return (
    <div className={styles.reqCard} onClick={()=>setOpen(o=>!o)}>
      <div className={styles.reqTop}>
        <span className={styles.reqId} style={{color}}>{item.id || type}</span>
        <span className={styles.reqTitle}>{item.title || item.description?.slice(0,50)}</span>
        <span className={`${styles.chevron} ${open?styles.chevronOpen:''}`}>›</span>
      </div>
      {item.priority && (
        <span className={styles.prio} style={{
          color: item.priority==='HIGH'?'var(--red)':item.priority==='MEDIUM'?'var(--orange)':'var(--text3)',
        }}>{item.priority}</span>
      )}
      {open && (
        <div className={styles.reqDetail}>
          <p>{item.description}</p>
          {item.acceptance_criteria?.length > 0 && (
            <div className={styles.acWrap}>
              <div className={styles.acLabel}>Acceptance Criteria</div>
              {item.acceptance_criteria.map((a,i) => <div key={i} className={styles.ac}>✓ {a}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AuditPanel({ audit }) {
  const score   = Math.round((audit.overall_smart_score || 0) * 100)
  const passed  = audit.passed || 0
  const rejected= audit.rejected || 0
  const warned  = audit.warned || 0
  const findings = (audit.findings || []).filter(f => f.verdict !== 'PASS')

  return (
    <div className={styles.auditPanel}>
      <div className={styles.panelHead}>
        <span className={styles.panelTitle}>SMART Audit</span>
        <div className={styles.scoreBar}>
          <div className={styles.scoreBarFill}
            style={{width:`${score}%`, background: score>=70?'var(--green)':score>=40?'var(--orange)':'var(--red)'}}
          />
          <span className={styles.scoreBarLabel}>{score}%</span>
        </div>
      </div>

      <div className={styles.auditStats}>
        <div className={styles.auditStat}><span style={{color:'var(--green)'}}>{passed}</span> passed</div>
        <div className={styles.auditStat}><span style={{color:'var(--red)'}}>{rejected}</span> rejected</div>
        <div className={styles.auditStat}><span style={{color:'var(--orange)'}}>{warned}</span> warned</div>
      </div>

      {findings.length > 0 && (
        <div className={styles.findings}>
          {findings.slice(0,4).map((f,i) => (
            <div key={i} className={styles.finding}
              style={{borderColor: f.verdict==='REJECT'?'rgba(239,68,68,.25)':'rgba(245,158,11,.2)'}}>
              <div className={styles.findingTop}>
                <span className={styles.findingId}>{f.item_id}</span>
                <span className={`${styles.verdict} ${f.verdict==='REJECT'?styles.verdictRej:styles.verdictWarn}`}>{f.verdict}</span>
              </div>
              {f.clarification_question && (
                <div className={styles.findingQ}>{f.clarification_question}</div>
              )}
              {f.smart_rewrite_example && (
                <div className={styles.findingEx}><span className={styles.exLabel}>SMART:</span> {f.smart_rewrite_example}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ArchPanel({ arch }) {
  const decisions = arch.decision_log || []
  const tier      = arch.scale_tier || '?'
  const pattern   = arch.architecture_pattern || '?'

  return (
    <div className={styles.archPanel}>
      <div className={styles.panelHead}>
        <span className={styles.panelTitle}>Architecture Decisions</span>
        <div className={styles.archBadges}>
          <span className={styles.archBadge} style={{background:'rgba(67,97,238,.1)',color:'var(--accent2)'}}>{tier}</span>
          <span className={styles.archBadge} style={{background:'rgba(139,92,246,.1)',color:'var(--purple)'}}>{pattern}</span>
        </div>
      </div>
      <div className={styles.decisionList}>
        {decisions.slice(0,6).map((d,i) => (
          <div key={i} className={styles.decision}>
            <span className={styles.decCat}>{d.category}</span>
            <span className={styles.decChoice}>{d.choice}</span>
            <span className={styles.decReason}>{d.reason}</span>
          </div>
        ))}
      </div>
      {arch.compliance_standards?.length > 0 && (
        <div className={styles.compliance}>
          <span className={styles.compLabel}>Compliance:</span>
          {arch.compliance_standards.map(c => (
            <span key={c} className={styles.compTag}>{c}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function PersonaPicker({ selected, onChange }) {
  const personas = [
    { id:'PM',       label:'Product Manager', icon:'📋' },
    { id:'CTO',      label:'CTO / Architect', icon:'⚙️' },
    { id:'Dev',      label:'Developer',        icon:'💻' },
    { id:'QA',       label:'QA Engineer',      icon:'🧪' },
    { id:'Investor', label:'Investor',          icon:'💼' },
    { id:'Client',   label:'Client',            icon:'🤝' },
  ]
  return (
    <div className={styles.personaGrid}>
      {personas.map(p => (
        <button key={p.id}
          className={`${styles.personaBtn} ${selected===p.id?styles.personaBtnActive:''}`}
          onClick={()=>onChange(p.id)}
        >
          <span>{p.icon}</span>
          <span>{p.label}</span>
        </button>
      ))}
    </div>
  )
}

function Empty({ text }) {
  return <div className={styles.empty}>{text}</div>
}

function AuditIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg> }
function Arrow()     { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg> }
function Spinner()   { return <span style={{width:16,height:16,border:'2px solid var(--border2)',borderTopColor:'var(--accent)',borderRadius:'50%',display:'inline-block',animation:'spin .7s linear infinite',flexShrink:0}}/> }
