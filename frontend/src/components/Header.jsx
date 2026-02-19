import styles from './Header.module.css'

export default function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2.2">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
        <span className={styles.title}>Agentic PRD Generator</span>
        <span className={styles.badge}>v2.0</span>
      </div>
      <div className={styles.right}>
        <span className={styles.tag}>5 AI Agents</span>
        <span className={styles.tag}>Persona-Aware</span>
        <span className={styles.tag}>Version-Controlled</span>
      </div>
    </header>
  )
}

