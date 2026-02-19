import { useState, useEffect } from 'react'
import { calibrate, fetchPrdTypes } from '../api'
import styles from './Calibration.module.css'

const LEVELS = [
  { id:'business', emoji:'📊', title:'Business / Product',
    desc:'I have a vision. I know what to build, not how.',
    hint:'I\'ll ask product-focused questions about value and outcomes.',
    color:'#f59e0b' },
  { id:'technical', emoji:'⚙️', title:'Technical / Engineering',
    desc:'I\'m an engineer or architect. Let\'s talk stacks and SLAs.',
    hint:'We\'ll go deep on architecture, NFRs, and technical constraints.',
    color:'#4361ee' },
]

const PROVIDERS = [
  { value:'mock',   label:'Mock — offline, instant',       badge:'No API key',  color:'var(--green)' },
  { value:'groq',   label:'Groq — Llama 3.3 70B',         badge:'GROQ_API_KEY', color:'#f59e0b' },
  { value:'gemini', label:'Gemini 1.5 Flash',              badge:'GEMINI_API_KEY', color:'#4285f4' },
]

export default function Calibration({ session, onComplete, onUpdate }) {
  const [level,       setLevel]      = useState(session.level || '')
  const [provider,    setProvider]   = useState(session.provider || 'mock')
  const [projectName, setProject]    = useState(session.project_name || '')
  const [clientName,  setClient]     = useState(session.client_name || '')
  const [domain,      setDomain]     = useState(session.domain || '')
  const [prdType,     setPrdType]    = useState(session.prd_type || '')
  const [intro,       setIntro]      = useState('')
  const [prdTypes,    setPrdTypes]   = useState([])
  const [loading,     setLoading]    = useState(false)
  const [error,       setError]      = useState('')
  const [step,        setStep]       = useState(0)  // 0=level, 1=project, 2=provider

  useEffect(() => {
    fetchPrdTypes().then(d => setPrdTypes(d.types || [])).catch(()=>{})
  }, [])

  const canNext0 = !!level
  const canNext1 = !!projectName.trim() && !!domain.trim()
  const canSubmit = canNext0 && canNext1

  const handleStart = async () => {
    setLoading(true); setError('')
    try {
      let persona = level === 'technical' ? 'CTO' : 'PM'
      let detectedType = prdType
      if (intro.trim()) {
        const res = await calibrate({ message: intro + ' ' + projectName + ' ' + domain, stated_level: level })
        if (res.auto_upgrade) persona = res.recommended_persona
        if (!detectedType && res.detected_prd_type) detectedType = res.detected_prd_type
      } else if (domain || projectName) {
        const res = await calibrate({ message: domain + ' ' + projectName, stated_level: level })
        if (!detectedType && res.detected_prd_type) detectedType = res.detected_prd_type
      }
      onComplete({ level, persona, provider, project_name:projectName, client_name:clientName, domain, prd_type:detectedType })
    } catch(e) { setError(e.message); setLoading(false) }
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>

        {/* Hero */}
        <div className={styles.hero}>
          <div className={styles.heroGlow} />
          <div className={styles.heroInner}>
            <HexBadge />
            <h1 className={styles.heroTitle}>
              Turn your idea into an<br />
              <span className={styles.heroGrad}>Enterprise PRD</span>
            </h1>
            <p className={styles.heroSub}>
              I'm your AI Solutions Architect. I interview you, detect gaps,
              validate every requirement to SMART standards, and generate a
              production-ready PRD — automatically.
            </p>
            <div className={styles.heroCaps}>
              {['SMART Validation','Auto Architecture','Gap Detection','Voice Input','Version Control'].map(c=>(
                <span key={c} className={styles.heroCap}>{c}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Steps */}
        <div className={styles.steps}>
          <StepHeader n={1} label="Who are you today?" active={step>=0} done={step>0} />
          {step >= 0 && (
            <div className={`${styles.stepBody} ${styles.fadeUp}`}>
              <div className={styles.levelGrid}>
                {LEVELS.map(l => (
                  <button key={l.id}
                    className={`${styles.levelCard} ${level===l.id?styles.levelActive:''}`}
                    style={level===l.id?{borderColor:l.color,boxShadow:`0 0 0 1px ${l.color}30, 0 8px 32px ${l.color}15`}:{}}
                    onClick={()=>{setLevel(l.id);if(step===0)setStep(1)}}
                  >
                    <span className={styles.levelEmoji}>{l.emoji}</span>
                    <span className={styles.levelTitle} style={level===l.id?{color:l.color}:{}}>{l.title}</span>
                    <span className={styles.levelDesc}>{l.desc}</span>
                    {level===l.id && <span className={styles.levelHint}>{l.hint}</span>}
                  </button>
                ))}
              </div>
              {step===0 && <button className={styles.nextBtn} disabled={!canNext0} onClick={()=>setStep(1)}>Continue <Arrow/></button>}
            </div>
          )}

          <StepHeader n={2} label="Project details" active={step>=1} done={step>1} />
          {step >= 1 && (
            <div className={`${styles.stepBody} ${styles.fadeUp}`}>
              <div className={styles.fieldGrid}>
                <Field label="Project Name *" value={projectName} onChange={setProject} placeholder="e.g. LoanTrack Pro" autoFocus />
                <Field label="Client / Company" value={clientName} onChange={setClient} placeholder="e.g. FinCorp Ltd" />
                <Field label="Domain / Industry *" value={domain} onChange={setDomain} placeholder="e.g. FinTech, HealthTech, SaaS" />
              </div>

              {prdTypes.length > 0 && (
                <div className={styles.typeSelect}>
                  <label className={styles.fieldLabel}>Project Type <span className={styles.optBadge}>auto-detected</span></label>
                  <div className={styles.typeGrid}>
                    {prdTypes.map(t => (
                      <button key={t.id}
                        className={`${styles.typeBtn} ${prdType===t.id?styles.typeBtnActive:''}`}
                        onClick={()=>setPrdType(prdType===t.id?'':t.id)}
                      >{t.label}</button>
                    ))}
                  </div>
                </div>
              )}

              <div className={styles.introWrap}>
                <label className={styles.fieldLabel}>Quick description <span className={styles.optBadge}>optional — helps calibration</span></label>
                <textarea className={styles.textarea} value={intro} onChange={e=>setIntro(e.target.value)}
                  placeholder="Describe what the product does in 1-2 sentences..." rows={3} />
              </div>

              {step===1 && <button className={styles.nextBtn} disabled={!canNext1} onClick={()=>setStep(2)}>Continue <Arrow/></button>}
            </div>
          )}

          <StepHeader n={3} label="LLM Provider" active={step>=2} done={false} />
          {step >= 2 && (
            <div className={`${styles.stepBody} ${styles.fadeUp}`}>
              <div className={styles.providerGrid}>
                {PROVIDERS.map(p=>(
                  <button key={p.value}
                    className={`${styles.provCard} ${provider===p.value?styles.provActive:''}`}
                    style={provider===p.value?{borderColor:p.color,background:`${p.color}0a`}:{}}
                    onClick={()=>setProvider(p.value)}
                  >
                    <div className={styles.provTop}>
                      <span className={styles.provLabel}>{p.label}</span>
                      <span className={styles.provBadge} style={provider===p.value?{background:`${p.color}20`,color:p.color}:{}}>{p.badge}</span>
                    </div>
                    {provider===p.value && <span className={styles.provSelected}>Selected ✓</span>}
                  </button>
                ))}
              </div>

              {error && <div className={styles.errBox}>{error}</div>}

              <button className={styles.startBtn} disabled={!canSubmit||loading} onClick={handleStart}>
                {loading ? <><Spin/> Starting session...</> : <>Begin Interview Session <Arrow/></>}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StepHeader({ n, label, active, done }) {
  return (
    <div className={`${styles.stepHdr} ${active?styles.stepHdrActive:''}`}>
      <div className={`${styles.stepNum} ${active?styles.stepNumActive:''} ${done?styles.stepNumDone:''}`}>
        {done ? '✓' : n}
      </div>
      <span className={styles.stepLabel}>{label}</span>
    </div>
  )
}

function Field({ label, value, onChange, placeholder, autoFocus }) {
  return (
    <div className={styles.field}>
      <label className={styles.fieldLabel}>{label}</label>
      <input className={styles.input} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} autoFocus={autoFocus} />
    </div>
  )
}

function HexBadge() {
  return (
    <div className={styles.hexBadge}>
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <polygon points="24,4 42,14 42,34 24,44 6,34 6,14" stroke="#4361ee" strokeWidth="1.5" fill="rgba(67,97,238,.08)"/>
        <polygon points="24,10 37,17.5 37,30.5 24,38 11,30.5 11,17.5" stroke="#6080ff" strokeWidth="1" fill="rgba(67,97,238,.05)"/>
        <circle cx="24" cy="24" r="6" fill="#4361ee"/>
        <circle cx="24" cy="24" r="3" fill="#8ca8ff"/>
      </svg>
    </div>
  )
}

function Arrow() { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg> }
function Spin()  { return <span style={{width:15,height:15,border:'2px solid rgba(255,255,255,.2)',borderTopColor:'#fff',borderRadius:'50%',display:'inline-block',animation:'spin .7s linear infinite'}}/> }
