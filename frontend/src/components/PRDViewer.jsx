import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import styles from './PRDViewer.module.css'

export default function PRDViewer({ markdown }) {
  if (!markdown) return <p style={{ color: 'var(--muted)' }}>No PRD generated yet.</p>

  const handleCopy = () => {
    navigator.clipboard.writeText(markdown).catch(() => {})
  }

  const handleDownload = () => {
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'prd.md'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className={styles.container}>
      <div className={styles.toolbar}>
        <span className={styles.toolbarTitle}>Generated PRD</span>
        <div className={styles.toolbarActions}>
          <button className={styles.toolbarBtn} onClick={handleCopy}>
            <CopyIcon /> Copy
          </button>
          <button className={styles.toolbarBtn} onClick={handleDownload}>
            <DownloadIcon /> Download .md
          </button>
        </div>
      </div>
      <div className={`${styles.body} md-body`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {markdown}
        </ReactMarkdown>
      </div>
    </div>
  )
}

function CopyIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  )
}

