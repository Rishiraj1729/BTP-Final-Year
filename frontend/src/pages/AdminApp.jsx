/**
 * AdminApp.jsx — Admin dashboard
 * Left: PRD list with user breakdown
 * Right: Selected PRD view + discussion thread + actions
 *   - View PRD markdown
 *   - Chat with user about the PRD
 *   - Request changes → generates updated version (non-destructive)
 *   - Share PRD with user(s) for approval
 */
import { useState, useEffect, useRef } from 'react'
import styles from './AdminApp.module.css'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const post = async (path, body) => {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail || JSON.stringify(data))
  return data
}
const get = async (path) => {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(`Error ${r.status}`)
  return r.json()
}

export default function AdminApp({ session, onLogout }) {
  const [prds,      setPrds]    = useState([])
  const [users,     setUsers]   = useState([])
  const [selected,  setSelected] = useState(null)   // full PRD object
  const [loadingPrd, setLoadingPrd] = useState(false)
  const [rightTab,  setRightTab] = useState('prd')  // 'prd' | 'discuss' | 'share'
  const [discussion, setDiscussion] = useState([])
  const [chatMsg,   setChatMsg]  = useState('')
  const [sending,   setSending]  = useState(false)
  const [shareUsers, setShareUsers] = useState([])   // selected user names to share with
  const [shareNote, setShareNote] = useState('')
  const [sharing,   setSharing]  = useState(false)
  const [shareResult, setShareResult] = useState('')
  const [updateInstr, setUpdateInstr] = useState('')
  const [updating,  setUpdating] = useState(false)
  const [updatedPrd, setUpdatedPrd] = useState(null)
  const [filterUser, setFilterUser] = useState('all')
  const chatEndRef  = useRef(null)

  useEffect(() => { loadPrds(); loadUsers() }, [])
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [discussion])

  const loadPrds = async () => {
    try {
      const d = await get('/api/admin/prds')
      setPrds(d.prds || [])
    } catch { /* silent */ }
  }

  const loadUsers = async () => {
    try {
      const d = await get('/api/admin/users')
      setUsers(d.users || [])
    } catch { /* silent */ }
  }

  const selectPrd = async (prd) => {
    setLoadingPrd(true)
    setUpdatedPrd(null)
    setShareResult('')
    setUpdateInstr('')
    setShareUsers([])
    try {
      const d = await get(`/api/admin/prd/${prd.id}`)
      setSelected(d)
      setDiscussion(d.discussion || [])
      setRightTab('prd')
    } catch (e) { alert(e.message) }
    setLoadingPrd(false)
  }

  const sendMessage = async () => {
    if (!chatMsg.trim() || !selected) return
    setSending(true)
    try {
      const d = await post('/api/discussion/send', {
        prd_id:      selected.id,
        sender_name: session.name,
        sender_role: 'admin',
        message:     chatMsg.trim(),
      })
      setDiscussion(d.thread)
      setChatMsg('')
    } catch (e) { alert(e.message) }
    setSending(false)
  }

  const requestUpdate = async () => {
    if (!updateInstr.trim() || !selected) return
    setUpdating(true)
    try {
      const d = await post('/api/admin/update-from-discussion', {
        prd_id:              selected.id,
        admin_name:          session.name,
        change_instructions: updateInstr.trim(),
      })
      setUpdatedPrd(d)
      setUpdateInstr('')
      setDiscussion(prev => [...prev, {
        sender_name: session.name, sender_role: 'admin',
        message: `Updated PRD generated (v${d.new_version}).`,
        timestamp: new Date().toISOString(),
      }])
      loadPrds() // refresh list
    } catch (e) { alert(e.message) }
    setUpdating(false)
  }

  const sharePrd = async () => {
    if (!shareUsers.length || !selected) return
    setSharing(true)
    try {
      await post('/api/admin/share-prd', {
        prd_id:     selected.id,
        user_names: shareUsers,
        note:       shareNote,
      })
      setShareResult(`PRD shared with: ${shareUsers.join(', ')}`)
      setShareUsers([])
      setShareNote('')
    } catch (e) { setShareResult('Error: ' + e.message) }
    setSharing(false)
  }

  const toggleShareUser = (name) => {
    setShareUsers(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    )
  }

  const filteredPrds = filterUser === 'all'
    ? prds
    : prds.filter(p => p.user_name === filterUser)

  const uniqueUsers = [...new Set(prds.map(p => p.user_name).filter(Boolean))]

  return (
    <div className={styles.root}>
      {/* Top bar */}
      <header className={styles.topBar}>
        <div className={styles.brand}><LogoMark /> Admin Dashboard</div>
        <div className={styles.topMeta}>
          <span className={styles.statChip}>{prds.length} PRDs</span>
          <span className={styles.statChip}>{uniqueUsers.length} Users</span>
        </div>
        <div className={styles.topRight}>
          <div className={styles.adminChip}><StarIcon /> {session.name}</div>
          <button className={styles.logoutBtn} onClick={onLogout}>Sign out</button>
        </div>
      </header>

      <div className={styles.body}>
        {/* ── Left: PRD list ── */}
        <aside className={styles.sidebar}>
          <div className={styles.sidebarHead}>
            <span className={styles.sidebarTitle}>All PRDs</span>
            <button className={styles.refreshBtn} onClick={loadPrds} title="Refresh">⟳</button>
          </div>

          {/* User filter */}
          <div className={styles.filterRow}>
            <button
              className={`${styles.filterChip} ${filterUser === 'all' ? styles.filterActive : ''}`}
              onClick={() => setFilterUser('all')}
            >All</button>
            {uniqueUsers.map(u => (
              <button key={u}
                className={`${styles.filterChip} ${filterUser === u ? styles.filterActive : ''}`}
                onClick={() => setFilterUser(u)}
              >{u}</button>
            ))}
          </div>

          <div className={styles.prdList}>
            {filteredPrds.length === 0 && (
              <div className={styles.emptyList}>No PRDs yet. Users will appear here after submitting their requirements.</div>
            )}
            {filteredPrds.map(p => (
              <button key={p.id}
                className={`${styles.prdItem} ${selected?.id === p.id ? styles.prdItemActive : ''}`}
                onClick={() => selectPrd(p)}
              >
                <div className={styles.prdItemTop}>
                  <span className={styles.prdItemName}>{p.project_name || 'Unnamed'}</span>
                  <span className={styles.prdItemVer}>v{p.version}</span>
                </div>
                <div className={styles.prdItemMeta}>
                  <UserDot /> {p.user_name || '—'}
                  <span style={{marginLeft:'auto', opacity:.7}}>{fmtDate(p.timestamp)}</span>
                </div>
                {p.prd_md && (
                  <div className={styles.prdItemPreview}>{p.prd_md.slice(0, 80)}…</div>
                )}
              </button>
            ))}
          </div>
        </aside>

        {/* ── Right: PRD detail + actions ── */}
        <main className={styles.rightPanel}>
          {loadingPrd ? (
            <div className={styles.loadingCenter}><Spinner /></div>
          ) : !selected ? (
            <div className={styles.placeholder}>
              <PlaceholderIcon />
              <div className={styles.placeholderTitle}>Select a PRD to review</div>
              <div className={styles.placeholderSub}>Click any PRD from the left panel to view it, discuss with the user, request changes, or share for approval.</div>
            </div>
          ) : (
            <>
              {/* PRD header */}
              <div className={styles.prdHeader}>
                <div>
                  <div className={styles.prdTitle}>{selected.project_name}</div>
                  <div className={styles.prdMeta}>
                    <UserDot /> {selected.user_name}
                    &nbsp;·&nbsp; v{selected.version}
                    &nbsp;·&nbsp; {fmtDate(selected.timestamp)}
                  </div>
                </div>
                <div className={styles.prdActions}>
                  <button className={styles.dlBtn}
                    onClick={() => downloadMd(selected.prd_md, selected.project_name)}>
                    ↓ .md
                  </button>
                </div>
              </div>

              {/* Tab bar */}
              <div className={styles.tabBar}>
                {[
                  { id: 'prd',     label: 'PRD',     icon: <DocIcon /> },
                  { id: 'discuss', label: 'Discussion', icon: <ChatIcon />, badge: discussion.length },
                  { id: 'update',  label: 'Update PRD', icon: <EditIcon /> },
                  { id: 'share',   label: 'Share',    icon: <ShareIcon /> },
                ].map(t => (
                  <button key={t.id}
                    className={`${styles.tab} ${rightTab === t.id ? styles.tabActive : ''}`}
                    onClick={() => setRightTab(t.id)}
                  >
                    {t.icon} {t.label}
                    {t.badge > 0 && <span className={styles.tabBadge}>{t.badge}</span>}
                  </button>
                ))}
              </div>

              <div className={styles.tabContent}>

                {/* ── PRD tab ── */}
                {rightTab === 'prd' && (
                  <div className={styles.prdBody}>
                    {updatedPrd && (
                      <div className={styles.updateBanner}>
                        ✓ Updated PRD (v{updatedPrd.new_version}) generated.{' '}
                        <button onClick={() => setSelected({...selected, prd_md: updatedPrd.prd_markdown, version: updatedPrd.new_version})}>
                          View updated version
                        </button>
                      </div>
                    )}
                    <MarkdownRenderer md={selected.prd_md} />
                  </div>
                )}

                {/* ── Discussion tab ── */}
                {rightTab === 'discuss' && (
                  <div className={styles.discussPanel}>
                    <div className={styles.discussThread}>
                      {discussion.length === 0 && (
                        <div className={styles.emptyThread}>
                          No messages yet. Start the conversation with the client about their requirements.
                        </div>
                      )}
                      {discussion.map((m, i) => (
                        <div key={i}
                          className={`${styles.msg} ${m.sender_role === 'admin' ? styles.msgAdmin : styles.msgUser}`}
                        >
                          <div className={styles.msgMeta}>
                            <strong>{m.sender_name}</strong>
                            <span className={styles.roleTag}>{m.sender_role}</span>
                            <span className={styles.msgTime}>{fmtTime(m.timestamp)}</span>
                          </div>
                          <div className={styles.msgText}>{m.message}</div>
                        </div>
                      ))}
                      <div ref={chatEndRef} />
                    </div>
                    <div className={styles.chatInput}>
                      <textarea
                        className={styles.chatTextarea}
                        value={chatMsg}
                        onChange={e => setChatMsg(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
                        placeholder="Message the client about their PRD… (Enter to send)"
                        rows={3}
                      />
                      <button className={styles.sendBtn} onClick={sendMessage} disabled={!chatMsg.trim() || sending}>
                        {sending ? '…' : 'Send'} <SendIcon />
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Update tab ── */}
                {rightTab === 'update' && (
                  <div className={styles.updatePanel}>
                    <div className={styles.panelTitle}>Request PRD Update</div>
                    <div className={styles.panelSub}>
                      Describe what should change. A new version will be created — the original is preserved.
                    </div>
                    <textarea
                      className={styles.updateTextarea}
                      value={updateInstr}
                      onChange={e => setUpdateInstr(e.target.value)}
                      placeholder="e.g. Add a vendor management module. Change authentication from email/password to Google SSO. Expand performance requirements to support 50k users."
                      rows={6}
                    />
                    {updatedPrd && (
                      <div className={styles.successMsg}>
                        ✓ New version v{updatedPrd.new_version} created (PRD id: {updatedPrd.new_prd_id}).{' '}
                        <button onClick={() => { loadPrds(); setRightTab('prd') }}>View in list</button>
                      </div>
                    )}
                    <button className={styles.primaryBtn} onClick={requestUpdate}
                      disabled={!updateInstr.trim() || updating}>
                      {updating ? <><Spinner small /> Generating…</> : '⟳ Generate Updated PRD'}
                    </button>
                  </div>
                )}

                {/* ── Share tab ── */}
                {rightTab === 'share' && (
                  <div className={styles.sharePanel}>
                    <div className={styles.panelTitle}>Share PRD for Approval</div>
                    <div className={styles.panelSub}>
                      Select user(s) who should review and approve this PRD.
                    </div>

                    <div className={styles.userCheckList}>
                      {users.length === 0 && (
                        <div className={styles.emptyThread}>No registered users found.</div>
                      )}
                      {users.map(u => (
                        <label key={u.name} className={styles.userCheck}>
                          <input type="checkbox"
                            checked={shareUsers.includes(u.name)}
                            onChange={() => toggleShareUser(u.name)}
                          />
                          <UserDot />&nbsp; {u.name}
                        </label>
                      ))}
                    </div>

                    <label className={styles.noteLabel}>Add a note (optional)</label>
                    <textarea
                      className={styles.noteInput}
                      value={shareNote}
                      onChange={e => setShareNote(e.target.value)}
                      placeholder="e.g. Please review section 3 and confirm the integration requirements."
                      rows={3}
                    />

                    {shareResult && (
                      <div className={shareResult.startsWith('Error') ? styles.errorMsg : styles.successMsg}>
                        {shareResult}
                      </div>
                    )}

                    {selected.shares?.length > 0 && (
                      <div className={styles.existingShares}>
                        <div className={styles.existingSharesTitle}>Previous shares</div>
                        {selected.shares.map((s, i) => (
                          <div key={i} className={styles.shareRow}>
                            <span>{s.user_name}</span>
                            <StatusBadge status={s.status} />
                            {s.note && <span className={styles.shareNote}>"{s.note}"</span>}
                          </div>
                        ))}
                      </div>
                    )}

                    <button className={styles.primaryBtn} onClick={sharePrd}
                      disabled={!shareUsers.length || sharing}>
                      {sharing ? 'Sharing…' : `Share with ${shareUsers.length || 0} user${shareUsers.length !== 1 ? 's' : ''} →`}
                    </button>
                  </div>
                )}

              </div>
            </>
          )}
        </main>
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
function fmtTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}
function downloadMd(md, name) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([md || ''], { type: 'text/markdown' }))
  a.download = `${(name || 'prd').replace(/\s+/g, '_')}_PRD.md`
  a.click()
}

function MarkdownRenderer({ md }) {
  if (!md) return <div className={styles.emptyThread}>No PRD content yet.</div>
  const html = md
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n{2,}/g, '</p><p>')
  return <div className={styles.mdBody} dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }} />
}

function StatusBadge({ status }) {
  const map = {
    pending:           { label: 'Pending',           color: 'var(--orange)' },
    approved:          { label: '✓ Approved',         color: 'var(--green)'  },
    changes_requested: { label: '✎ Changes Requested', color: 'var(--red)'   },
  }
  const s = map[status] || { label: status, color: 'var(--text3)' }
  return <span className={styles.statusBadge} style={{ color: s.color, borderColor: s.color }}>{s.label}</span>
}

function Spinner({ small }) {
  const s = small ? 14 : 28
  return <div style={{ width:s, height:s, border:`2px solid var(--border)`, borderTop:`2px solid var(--accent)`, borderRadius:'50%', animation:'spin 1s linear infinite', display:'inline-block' }} />
}

// ── Icons ─────────────────────────────────────────────────────────────────────
function LogoMark() {
  return <svg width="26" height="26" viewBox="0 0 40 40" fill="none" style={{marginRight:8}}>
    <rect width="40" height="40" rx="10" fill="rgba(67,97,238,.15)" stroke="rgba(67,97,238,.4)" strokeWidth="1.5"/>
    <polygon points="20,7 31,13 31,27 20,33 9,27 9,13" fill="none" stroke="#4361ee" strokeWidth="1.8"/>
    <circle cx="20" cy="20" r="5" fill="#4361ee"/>
  </svg>
}
function UserDot() { return <span style={{display:'inline-block',width:7,height:7,borderRadius:'50%',background:'var(--green)',marginRight:4}} /> }
function StarIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> }
function DocIcon()  { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> }
function ChatIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> }
function EditIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> }
function ShareIcon(){ return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg> }
function SendIcon() { return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> }
function PlaceholderIcon() { return <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text4)" strokeWidth="1.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> }

