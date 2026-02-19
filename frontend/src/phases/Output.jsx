/**
 * Output — Phase 3
 * Shows PRD with syntax highlighting, export, version management,
 * and the Update / Refine flow.
 */
import { useState, useEffect, useRef } from 'react'
import { generatePRD, updatePRD } from '../api'
import styles from './Output.module.css'

export default function Output({ session, onUpdate, onBack, onNewVersion }) {
  const [prdMd,     setPrdMd]   = useState(session.prdResult?.prd_markdown || '')
  const [loading,   setLoading] = useState(!prdMd)
  const [error,     setError]   = useState('')
  const [copied,    setCopied]  = useState(false)
  const [tab,       setTab]     = useState('prd')   // 'prd' | 'arch' | 'gaps' | 'completion'
  const [updateMode, setUpdateMode] = useState(false)
  const [updateText, setUpdateText] = useState('')
  const [updateType, setUpdateType] = useState('refine')  // 'refine' | 'new'
  const [updatePersona, setUpdatePersona] = useState(session.persona || 'PM')
  const [updating,  setUpdating] = useState(false)
  const printRef   = useRef(null)

  const prdResult = session.prdResult || {}
  const completion = prdResult.completion || {}
  const arch       = prdResult.architecture || {}
  const gapReport  = prdResult.gap_report || {}
  const audit      = prdResult.audit || {}

  useEffect(() => {
    if (!prdMd && !loading) return
    if (!prdMd) { generate() }
  }, [])

  const generate = async () => {
    setLoading(true); setError('')
    try {
      const res = await generatePRD({
        conversation:  session.conversation || '',
        provider:      session.provider,
        persona:       session.persona,
        project_name:  session.project_name,
        client_name:   session.client_name,
        domain:        session.domain,
        signals:       session.signals || {},
        audit_report:  session.auditReport,
        architecture:  session.architecture,
      })
      setPrdMd(res.prd_markdown)
      onUpdate({ prdResult: res, completion: Math.round((res.completion?.overall_score||0)*100) })
    } catch(e) { setError(e.message) }
    setLoading(false)
  }

  const handleUpdate = async () => {
    if (!updateText.trim()) return
    setUpdating(true)
    try {
      const res = await updatePRD({
        version_id:      prdResult.version || 1,
        new_conversation: updateText,
        user_type:       updatePersona,
        provider:        session.provider,
        project_name:    session.project_name,
        change_type:     updateType,
      })
      setPrdMd(res.prd_markdown)
      onUpdate({ prdResult: res, completion: Math.round((res.completion?.overall_score||0)*100) })
      setUpdateMode(false)
      setUpdateText('')
    } catch(e) { setError(e.message) }
    setUpdating(false)
  }

  const copyToClipboard = () => {
    navigator.clipboard.writeText(prdMd).then(() => { setCopied(true); setTimeout(()=>setCopied(false),2000) })
  }

  const downloadMd = () => {
    const blob = new Blob([prdMd], { type:'text/markdown' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `PRD_v${prdResult.version||1}_${session.persona}.md`
    a.click(); URL.revokeObjectURL(url)
  }

  const printPrd = () => window.print()

  const isComplete = completion.is_complete
  const score      = Math.round((completion.overall_score||0)*100)

  return (
    <div className={styles.page}>
      {/* Left — PRD viewer */}
      <div className={styles.prdPanel}>
        {/* Toolbar */}
        <div className={styles.toolbar}>
          <div className={styles.toolbarLeft}>
            <div className={styles.versionBadge}>
              v{prdResult.version || '—'}
            </div>
            <div className={styles.personaBadge}>{session.persona}</div>
            {score > 0 && (
              <div className={styles.scoreBadge} style={{
                color: isComplete?'var(--green)':score>=60?'var(--orange)':'var(--red)',
                borderColor: isComplete?'rgba(16,185,129,.3)':score>=60?'rgba(245,158,11,.3)':'rgba(239,68,68,.3)',
                background:  isComplete?'rgba(16,185,129,.07)':score>=60?'rgba(245,158,11,.07)':'rgba(239,68,68,.07)',
              }}>
                {score}% complete
              </div>
            )}
          </div>
          <div className={styles.toolTabs}>
            {['prd','arch','gaps','completion'].map(t => (
              <button key={t} className={`${styles.toolTab} ${tab===t?styles.toolTabActive:''}`} onClick={()=>setTab(t)}>
                {t.charAt(0).toUpperCase()+t.slice(1)}
              </button>
            ))}
          </div>
          <div className={styles.toolbarActions}>
            <button className={styles.toolBtn} onClick={copyToClipboard}>
              {copied ? <CheckIcon/> : <CopyIcon/>} {copied?'Copied!':'Copy'}
            </button>
            <button className={styles.toolBtn} onClick={downloadMd}>
              <DownloadIcon/> Export
            </button>
            <button className={styles.toolBtnPrimary} onClick={()=>setUpdateMode(u=>!u)}>
              <EditIcon/> Update PRD
            </button>
          </div>
        </div>

        {/* Loading */}
        {loading && <GeneratingScreen />}

        {/* Error */}
        {error && (
          <div className={styles.errorWrap}>
            <div className={styles.errBox}>{error}</div>
            <button className={styles.retryBtn} onClick={generate}>Retry</button>
          </div>
        )}

        {/* Content tabs */}
        {!loading && !error && (
          <div className={styles.content} ref={printRef}>
            {tab === 'prd' && <MarkdownView markdown={prdMd} />}
            {tab === 'arch' && <ArchView arch={arch} />}
            {tab === 'gaps' && <GapsView gapReport={gapReport} />}
            {tab === 'completion' && <CompletionView completion={completion} />}
          </div>
        )}
      </div>

      {/* Right panel — actions */}
      <div className={styles.rightPanel}>
        {/* Update PRD panel */}
        {updateMode ? (
          <div className={styles.updatePanel}>
            <div className={styles.updateHeader}>
              <span className={styles.updateTitle}>Update PRD</span>
              <button className={styles.closeBtn} onClick={()=>setUpdateMode(false)}>✕</button>
            </div>

            <div className={styles.updateTypeRow}>
              <button className={`${styles.typeBtn} ${updateType==='refine'?styles.typeBtnActive:''}`}
                onClick={()=>setUpdateType('refine')}>
                Refine v{prdResult.version||1}
              </button>
              <button className={`${styles.typeBtn} ${updateType==='new'?styles.typeBtnActive:''}`}
                onClick={()=>setUpdateType('new')}>
                New PRD
              </button>
            </div>

            <div className={styles.updatePersonaRow}>
              <label className={styles.updLabel}>Your role (context for the update):</label>
              <div className={styles.updatePersonaGrid}>
                {['PM','CTO','Dev','QA','Investor','Client'].map(p => (
                  <button key={p}
                    className={`${styles.personaMiniBtn} ${updatePersona===p?styles.personaMiniBtnActive:''}`}
                    onClick={()=>setUpdatePersona(p)}>{p}</button>
                ))}
              </div>
            </div>

            <label className={styles.updLabel}>New requirements or changes:</label>
            <textarea className={styles.updateTextarea} value={updateText}
              onChange={e=>setUpdateText(e.target.value)}
              placeholder={updateType==='refine'
                ? "Describe what changed, was added, or removed. The AI will update the PRD accordingly."
                : "Describe the new requirements from scratch for a fresh PRD."
              }
              rows={6}
            />

            <button className={styles.updateSubmitBtn} disabled={!updateText.trim()||updating} onClick={handleUpdate}>
              {updating ? <><Spin/> Updating...</> : `${updateType==='refine'?'Refine':'Generate New'} PRD →`}
            </button>
          </div>
        ) : (
          <div className={styles.actionsPanel}>
            <div className={styles.actionsPanelTitle}>Actions</div>

            <ActionCard icon="✏️" title="Refine this PRD" desc="Add new requirements or scope changes to this version"
              onClick={()=>{ setUpdateType('refine'); setUpdateMode(true) }} />
            <ActionCard icon="🆕" title="New PRD version" desc="Start fresh with new conversation, keep this as history"
              onClick={onNewVersion} />
            <ActionCard icon="⬅️" title="Back to Audit" desc="Go back and adjust the extracted requirements"
              onClick={onBack} />
            <ActionCard icon="📥" title="Download .md" desc="Export the PRD as a Markdown file"
              onClick={downloadMd} />

            {/* Stats */}
            <div className={styles.statsBox}>
              <StatRow label="Functional Reqs"    value={prdResult.functional?.length||0}    />
              <StatRow label="Non-Functional"      value={prdResult.non_functional?.length||0} />
              <StatRow label="Follow-up Questions" value={prdResult.follow_up_questions?.length||0} />
              <StatRow label="Gaps Identified"     value={prdResult.gaps?.length||0}           />
              <StatRow label="SMART Score"         value={`${Math.round((audit.overall_smart_score||0)*100)}%`} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function MarkdownView({ markdown }) {
  if (!markdown) return <div className={styles.noContent}>No PRD generated yet</div>
  // Simple markdown render — convert to HTML
  const html = markdownToHtml(markdown)
  return <div className={`${styles.mdBody} md-body`} dangerouslySetInnerHTML={{__html: html}} />
}

function markdownToHtml(md) {
  return md
    .replace(/^(#{1,6})\s(.+)/gm, (_, h, t) => `<h${h.length}>${t}</h${h.length}>`)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^>\s(.+)/gm, '<blockquote>$1</blockquote>')
    .replace(/^\s*[-*]\s(.+)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>(\n|$))+/g, m => `<ul>${m}</ul>`)
    .replace(/^\d+\.\s(.+)/gm, '<li>$1</li>')
    .replace(/\|(.+)\|/g, (line) => {
      const cells = line.split('|').filter(c=>c.trim()&&!c.match(/^[-: ]+$/))
      return cells.length ? `<tr>${cells.map(c=>`<td>${c.trim()}</td>`).join('')}</tr>` : ''
    })
    .replace(/(<tr>.*<\/tr>(\n|$))+/g, m => `<table>${m}</table>`)
    .replace(/^---$/gm, '<hr/>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[h1-6liuolthrpb])/gm, '')
}

function ArchView({ arch }) {
  if (!arch || !arch.decision_log) return <Empty text="No architecture data" />
  return (
    <div className={styles.archView}>
      <div className={styles.archMeta}>
        <MetaBadge label="Scale" value={arch.scale_tier} color="var(--accent2)" />
        <MetaBadge label="Pattern" value={arch.architecture_pattern} color="var(--purple)" />
        <MetaBadge label="Est. Users" value={arch.peak_users_estimated?.toLocaleString()} color="var(--cyan)" />
      </div>
      {arch.decision_log.map((d,i) => (
        <div key={i} className={styles.archDecision}>
          <div className={styles.archDecCat}>{d.category}</div>
          <div className={styles.archDecChoice}>{d.choice}</div>
          <div className={styles.archDecReason}>{d.reason}</div>
        </div>
      ))}
    </div>
  )
}

function GapsView({ gapReport }) {
  if (!gapReport?.open_gaps) return <Empty text="No gap data" />
  const openGaps = gapReport.open_gaps || []
  const resolved = gapReport.resolved_gaps || []
  return (
    <div className={styles.gapsView}>
      <div className={styles.gapScore} style={{color: gapReport.is_complete?'var(--green)':'var(--orange)'}}>
        {Math.round((gapReport.completion_score||0)*100)}% — {gapReport.is_complete?'COMPLETE':'In Progress'}
      </div>
      {openGaps.map(g => (
        <div key={g.id} className={styles.gapRow}
          style={{borderColor: g.priority==='critical'?'rgba(239,68,68,.25)':'rgba(245,158,11,.2)'}}>
          <span className={styles.gapId} style={{color:g.priority==='critical'?'var(--red)':'var(--orange)'}}>{g.id}</span>
          <span className={styles.gapQ}>{g.question}</span>
        </div>
      ))}
      {resolved.length > 0 && (
        <div className={styles.resolvedSection}>
          <div className={styles.resolvedTitle}>Resolved ({resolved.length})</div>
          <div className={styles.resolvedChips}>{resolved.map(r=><span key={r} className={styles.resChip}>✓ {r}</span>)}</div>
        </div>
      )}
    </div>
  )
}

function CompletionView({ completion }) {
  const fields = [
    { label:'Functional Score',     value:Math.round((completion.functional||completion.functional_score||0)*100) },
    { label:'Non-Functional Score', value:Math.round((completion.non_functional||completion.non_functional_score||0)*100) },
    { label:'Constraints Score',    value:Math.round((completion.constraints||completion.constraints_score||0)*100) },
    { label:'Assumptions Score',    value:Math.round((completion.assumptions||completion.assumptions_score||0)*100) },
    { label:'Overall Score',        value:Math.round((completion.overall_score||0)*100), bold:true },
  ]
  return (
    <div className={styles.completionView}>
      {fields.map(f => (
        <div key={f.label} className={`${styles.compRow} ${f.bold?styles.compRowBold:''}`}>
          <span className={styles.compLabel}>{f.label}</span>
          <div className={styles.compBarWrap}>
            <div className={styles.compBarBg}>
              <div className={styles.compBarFill}
                style={{width:`${f.value}%`, background: f.value>=70?'var(--green)':f.value>=40?'var(--orange)':'var(--red)'}}
              />
            </div>
            <span className={styles.compVal}>{f.value}%</span>
          </div>
        </div>
      ))}
      <div className={`${styles.compStatus} ${completion.is_complete?styles.compStatusOk:styles.compStatusWarn}`}>
        {completion.is_complete ? '✓ Requirements are complete' : '⚠ Some information still missing'}
      </div>
    </div>
  )
}

function GeneratingScreen() {
  const steps = ['Analyzing conversation...','Extracting requirements...','Running SMART validation...','Building architecture decisions...','Generating PRD document...']
  const [step, setStep] = useState(0)
  useEffect(() => {
    const t = setInterval(()=>setStep(s=>(s+1)%steps.length),1800)
    return ()=>clearInterval(t)
  }, [])
  return (
    <div className={styles.generating}>
      <div className={styles.genOrb}/>
      <div className={styles.genSpinner}/>
      <div className={styles.genText}>{steps[step]}</div>
      <div className={styles.genSub}>This takes 10-30 seconds</div>
    </div>
  )
}

function ActionCard({ icon, title, desc, onClick }) {
  return (
    <button className={styles.actionCard} onClick={onClick}>
      <span className={styles.actionIcon}>{icon}</span>
      <div>
        <div className={styles.actionTitle}>{title}</div>
        <div className={styles.actionDesc}>{desc}</div>
      </div>
    </button>
  )
}

function StatRow({ label, value }) {
  return (
    <div className={styles.statRow}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
    </div>
  )
}

function MetaBadge({ label, value, color }) {
  return <div className={styles.metaBadge}><span style={{color}}>{value}</span><span>{label}</span></div>
}

function Empty({ text }) { return <div className={styles.noContent}>{text}</div> }

function CheckIcon()    { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg> }
function CopyIcon()     { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> }
function DownloadIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> }
function EditIcon()     { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> }
function Spin()         { return <span style={{width:14,height:14,border:'2px solid rgba(255,255,255,.2)',borderTopColor:'#fff',borderRadius:'50%',display:'inline-block',animation:'spin .7s linear infinite'}}/> }
