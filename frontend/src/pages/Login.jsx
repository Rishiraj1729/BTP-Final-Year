/**
 * Login.jsx
 *
 * Admin access is protected two ways:
 *   1. Google sign-in email on ADMIN_EMAILS whitelist → auto admin
 *   2. Manual entry → must enter ADMIN_PIN set in backend .env
 */
import { useState, useEffect } from 'react'
import { useGoogleLogin } from '@react-oauth/google'
import styles from './Login.module.css'

const BASE       = import.meta.env.VITE_API_URL || 'http://localhost:8001'
const HAS_GOOGLE = !!(import.meta.env.VITE_GOOGLE_CLIENT_ID || '').trim()

export default function Login({ onLogin }) {
  const [name,        setName]       = useState('')
  const [role,        setRole]       = useState('')
  const [pin,         setPin]        = useState('')
  const [loading,     setLoading]    = useState(false)
  const [error,       setError]      = useState('')
  const [googleUser,  setGoogleUser] = useState(null)   // {name,email,picture}
  const [autoAdmin,   setAutoAdmin]  = useState(false)  // whitelisted email

  // When Google user is set, check if their email is a whitelisted admin
  useEffect(() => {
    if (!googleUser?.email) { setAutoAdmin(false); return }
    fetch(`${BASE}/api/check-admin-email?email=${encodeURIComponent(googleUser.email)}`)
      .then(r => r.json())
      .then(d => {
        setAutoAdmin(!!d.is_admin)
        if (d.is_admin) setRole('admin')   // auto-select
      })
      .catch(() => setAutoAdmin(false))
  }, [googleUser?.email])

  const handleGoogleSuccess = (info) => {
    setGoogleUser(info)
    setName(info.name)
    setError('')
  }

  const submit = async () => {
    if (!name.trim()) return setError('Please enter your name.')
    if (!role)        return setError('Please choose how you want to sign in.')
    // PIN required for admin when not auto-approved via Google email
    if (role === 'admin' && !autoAdmin && !pin.trim()) {
      return setError('Admin PIN is required.')
    }
    setError('')
    setLoading(true)
    try {
      const r = await fetch(`${BASE}/api/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name:    name.trim(),
          role,
          email:   googleUser?.email   || '',
          picture: googleUser?.picture || '',
          pin:     role === 'admin' ? pin.trim() : '',
        }),
      })
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        throw new Error(data.detail || 'Login failed.')
      }
      const user = await r.json()
      onLogin({ ...user, picture: googleUser?.picture || '', email: googleUser?.email || '' })
    } catch (e) {
      setError(e.message || 'Login failed — is the server running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.orb1} />
      <div className={styles.orb2} />

      <div className={styles.card}>
        <div className={styles.logo}><LogoIcon /></div>
        <h1 className={styles.title}>Requirements Engine</h1>
        <p className={styles.subtitle}>
          Turn your product idea into a professional requirements document.
        </p>

        {/* ── Google Sign-In ── */}
        {HAS_GOOGLE ? (
          <>
            {googleUser ? (
              <div className={styles.googleConnected}>
                {googleUser.picture && (
                  <img src={googleUser.picture} alt="" className={styles.avatar} />
                )}
                <div>
                  <div className={styles.googleName}>{googleUser.name}</div>
                  <div className={styles.googleEmail}>{googleUser.email}</div>
                  {autoAdmin && (
                    <div className={styles.adminTag}><StarIcon /> Admin access granted</div>
                  )}
                </div>
                <button className={styles.googleSwitch}
                  onClick={() => { setGoogleUser(null); setName(''); setAutoAdmin(false); setRole('') }}>
                  Switch
                </button>
              </div>
            ) : (
              <GoogleLoginBtn onSuccess={handleGoogleSuccess} onError={setError} />
            )}
            <div className={styles.divider}><span>or enter name manually</span></div>
          </>
        ) : (
          <div className={styles.googleNote}>
            <InfoIcon />
            <span>
              Add <code>VITE_GOOGLE_CLIENT_ID=your_id</code> to{' '}
              <code>frontend/.env</code> to enable Google Sign-In.
            </span>
          </div>
        )}

        {/* Name */}
        <label className={styles.label}>Your name</label>
        <input
          className={styles.input}
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !role && undefined}
          placeholder="e.g. Rahul, Alice…"
          autoFocus={!googleUser}
        />

        {/* Role cards — hide if auto-admin detected */}
        {!autoAdmin && (
          <>
            <label className={styles.label} style={{ marginTop: 20 }}>Sign in as</label>
            <div className={styles.roleGrid}>
              <RoleCard
                active={role === 'user'}
                onClick={() => { setRole('user'); setPin('') }}
                icon={<UserRoleIcon />}
                title="Product Owner / Client"
                desc="Describe your idea, answer questions, get a PRD"
              />
              <RoleCard
                active={role === 'admin'}
                onClick={() => setRole('admin')}
                icon={<AdminRoleIcon />}
                title="Admin / Business Analyst"
                desc="Review PRDs, discuss with clients, manage versions"
              />
            </div>
          </>
        )}

        {/* Admin auto-grant banner */}
        {autoAdmin && (
          <div className={styles.autoAdminBanner}>
            <StarIcon />
            Signed in as <strong>Admin / Business Analyst</strong>
            <span className={styles.autoAdminSub}>Your email is on the admin whitelist</span>
          </div>
        )}

        {/* PIN field — only shown for admin without Google whitelist */}
        {role === 'admin' && !autoAdmin && (
          <div className={styles.pinSection}>
            <label className={styles.label}>
              <LockIcon /> Admin PIN
            </label>
            <input
              className={`${styles.input} ${styles.pinInput}`}
              type="password"
              value={pin}
              onChange={e => setPin(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submit()}
              placeholder="Enter admin PIN"
              autoFocus
            />
            <div className={styles.pinHint}>
              Contact your system administrator for the PIN.
            </div>
          </div>
        )}

        {error && <div className={styles.error}>{error}</div>}

        <button
          className={styles.btn}
          onClick={submit}
          disabled={loading || !name.trim() || (!role && !autoAdmin)}
        >
          {loading ? 'Connecting…' : 'Continue →'}
        </button>
      </div>
    </div>
  )
}

/* ── Google button (hook isolated here) ── */
function GoogleLoginBtn({ onSuccess, onError }) {
  const [busy, setBusy] = useState(false)
  const login = useGoogleLogin({
    flow: 'implicit',
    onSuccess: async (tok) => {
      setBusy(true)
      try {
        const r = await fetch('https://www.googleapis.com/oauth2/v3/userinfo',
          { headers: { Authorization: `Bearer ${tok.access_token}` } })
        if (!r.ok) throw new Error('Could not fetch Google profile.')
        const info = await r.json()
        onSuccess({ name: info.name, email: info.email, picture: info.picture })
      } catch (e) { onError('Google sign-in failed: ' + e.message) }
      setBusy(false)
    },
    onError: () => onError('Google sign-in was cancelled.'),
  })
  return (
    <button className={styles.googleBtn} onClick={() => login()} disabled={busy}>
      <GoogleIcon /> {busy ? 'Connecting…' : 'Sign in with Google'}
    </button>
  )
}

/* ── Role card ── */
function RoleCard({ active, onClick, icon, title, desc }) {
  return (
    <button className={`${styles.roleCard} ${active ? styles.roleCardActive : ''}`} onClick={onClick}>
      <div className={styles.roleIcon}>{icon}</div>
      <div className={styles.roleTitle}>{title}</div>
      <div className={styles.roleDesc}>{desc}</div>
      {active && <div className={styles.roleCheck}><CheckIcon /></div>}
    </button>
  )
}

/* ── Icons ── */
function LogoIcon() {
  return <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
    <rect width="40" height="40" rx="12" fill="rgba(67,97,238,.15)" stroke="rgba(67,97,238,.4)" strokeWidth="1.5"/>
    <polygon points="20,7 31,13 31,27 20,33 9,27 9,13" fill="none" stroke="#4361ee" strokeWidth="1.8"/>
    <circle cx="20" cy="20" r="5" fill="#4361ee"/>
  </svg>
}
function GoogleIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
}
function CheckIcon()    { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg> }
function StarIcon()     { return <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> }
function LockIcon()     { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> }
function InfoIcon()     { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> }
function UserRoleIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> }
function AdminRoleIcon(){ return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> }
