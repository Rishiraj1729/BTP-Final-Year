import styles from './VersionHistory.module.css'

export default function VersionHistory({ versions, loading, onLoad, onRefresh }) {
  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>Version History</span>
        <button className={styles.refreshBtn} onClick={onRefresh} title="Refresh versions">
          <RefreshIcon spin={loading} />
        </button>
      </div>

      {loading && <p className={styles.hint}>Loading...</p>}

      {!loading && versions.length === 0 && (
        <p className={styles.hint}>No versions saved yet.</p>
      )}

      {versions.length > 0 && (
        <ul className={styles.list}>
          {[...versions].reverse().map(v => (
            <li key={v.version} className={styles.item}>
              <div className={styles.itemLeft}>
                <span className={styles.ver}>v{v.version}</span>
                <div className={styles.meta}>
                  <span className={styles.project}>{v.project}</span>
                  <span className={styles.ts}>{formatTs(v.timestamp)}</span>
                </div>
              </div>
              <button className={styles.loadBtn} onClick={() => onLoad(v.version)}>
                Load
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function formatTs(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    })
  } catch { return ts }
}

function RefreshIcon({ spin }) {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
      style={{ animation: spin ? 'spin3 .8s linear infinite' : 'none' }}>
      <style>{`@keyframes spin3 { to { transform: rotate(360deg); } }`}</style>
      <polyline points="23 4 23 10 17 10"/>
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>
  )
}

