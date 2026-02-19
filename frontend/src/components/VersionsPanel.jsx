/**
 * VersionsPanel — slide-over showing all saved PRD versions
 * with load, compare, and regenerate actions.
 */
import { useState, useEffect } from 'react'
import { fetchVersions, loadVersion } from '../api'
import styles from './VersionsPanel.module.css'

export default function VersionsPanel({ onClose, session, onLoadVersion }) {
  const [versions, setVersions] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [loadingV, setLoadingV] = useState(null)
  const [error,    setError]    = useState('')

  useEffect(() => {
    fetchVersions()
      .then(data => setVersions(Array.isArray(data) ? data : data.versions || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleLoad = async (version) => {
    setLoadingV(version)
    try {
      const data = await loadVersion(version)
      onLoadVersion(data)
    } catch(e) {
      setError(e.message)
    }
    setLoadingV(null)
  }

  return (
    <div className={styles.overlay} onClick={e=>{ if(e.target===e.currentTarget) onClose() }}>
      <div className={styles.panel}>
        <div className={styles.header}>
          <div>
            <div className={styles.title}>Version History</div>
            <div className={styles.sub}>All saved PRD versions</div>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        {loading && (
          <div className={styles.loading}><Spin/> Loading versions...</div>
        )}
        {error && <div className={styles.errBox}>{error}</div>}

        {!loading && versions.length === 0 && (
          <div className={styles.empty}>
            <EmptyIcon/>
            <div>No saved versions yet</div>
            <div style={{fontSize:'.78rem',color:'var(--text4)'}}>Run the pipeline to create your first PRD</div>
          </div>
        )}

        <div className={styles.list}>
          {versions.map(v => (
            <VersionCard
              key={v.version || v.id}
              v={v}
              onLoad={handleLoad}
              loadingV={loadingV}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function VersionCard({ v, onLoad, loadingV }) {
  const vNum     = v.version || v.id || '?'
  const ts       = v.timestamp ? new Date(v.timestamp).toLocaleString() : '—'
  const project  = v.project_name || v.project || 'Unknown'
  const score    = v.completion?.overall_score
  const frCount  = v.functional_count
  const nfrCount = v.nfr_count
  const isLoading = loadingV === vNum

  return (
    <div className={styles.card}>
      <div className={styles.cardLeft}>
        <div className={styles.vBadge}>v{vNum}</div>
        <div>
          <div className={styles.cardProject}>{project}</div>
          <div className={styles.cardMeta}>
            <span>{ts}</span>
            {frCount !== undefined && <><Dot/><span>{frCount} FRs</span></>}
            {nfrCount !== undefined && <><Dot/><span>{nfrCount} NFRs</span></>}
          </div>
        </div>
      </div>
      <div className={styles.cardRight}>
        {score !== undefined && (
          <div className={styles.scoreTag}
            style={{color: score>=0.7?'var(--green)':score>=0.4?'var(--orange)':'var(--red)'}}>
            {Math.round(score*100)}%
          </div>
        )}
        <button className={styles.loadBtn} onClick={()=>onLoad(vNum)} disabled={isLoading}>
          {isLoading ? <Spin/> : 'Load'}
        </button>
      </div>
    </div>
  )
}

function Dot()     { return <span style={{color:'var(--text4)',fontSize:'.6rem'}}>•</span> }
function EmptyIcon(){ return <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text4)" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="13" y2="13"/></svg> }
function Spin()    { return <span style={{width:13,height:13,border:'2px solid var(--border2)',borderTopColor:'var(--accent)',borderRadius:'50%',display:'inline-block',animation:'spin .7s linear infinite'}}/> }

