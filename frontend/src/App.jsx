import { useCallback, useEffect, useState } from 'react'
import Auth from './components/Auth.jsx'
import Chat from './components/Chat.jsx'
import MemoryGraph from './components/MemoryGraph.jsx'
import Sidebar from './components/Sidebar.jsx'

// Fixed demo token expected by the backend for destructive actions.
export const DEMO_TOKEN = 'memoria-demo-token'

const AUTH_STORAGE_KEY = 'memoria_auth'

function sessionStorageKey(userId) {
  return `memoria_active_session_${userId}`
}

function randomUserId() {
  return 'user-' + Math.random().toString(36).slice(2, 8)
}

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed?.user_id && parsed?.username) return parsed
  } catch {
    // ignore corrupt storage
  }
  return null
}

export default function App() {
  const [tab, setTab] = useState('chat')
  const [auth, setAuth] = useState(loadStoredAuth)
  const [guestMode, setGuestMode] = useState(false)
  const [legacyUserId, setLegacyUserId] = useState(randomUserId)
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState('')

  const isLoggedIn = Boolean(auth?.user_id)
  const userId = isLoggedIn ? auth.user_id : legacyUserId

  const handleAuth = useCallback((user) => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user))
    setAuth(user)
    setGuestMode(false)
  }, [])

  const handleLogout = useCallback(() => {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    setAuth(null)
    setGuestMode(false)
    setLegacyUserId(randomUserId())
    setSessions([])
    setActiveSessionId(null)
  }, [])

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true)
    setSessionsError('')
    try {
      const res = await fetch(`/sessions?user_id=${encodeURIComponent(userId)}`)
      if (!res.ok) throw new Error(`Failed to load sessions (${res.status})`)
      const data = await res.json()
      setSessions(data)
      return data
    } catch (e) {
      setSessionsError(e.message || 'Failed to load chat sessions')
      return []
    } finally {
      setSessionsLoading(false)
    }
  }, [userId])

  const createSession = useCallback(async () => {
    const res = await fetch('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    })
    if (!res.ok) throw new Error(`Failed to create session (${res.status})`)
    const session = await res.json()
    setSessions((current) => [session, ...current.filter((s) => s.session_id !== session.session_id)])
    setActiveSessionId(session.session_id)
    localStorage.setItem(sessionStorageKey(userId), session.session_id)
    return session
  }, [userId])

  useEffect(() => {
    if (!isLoggedIn && !guestMode) return

    let cancelled = false

    async function bootstrapSessions() {
      const existing = await loadSessions()
      if (cancelled) return

      const savedId = localStorage.getItem(sessionStorageKey(userId))
      const savedSession = savedId
        ? existing.find((session) => session.session_id === savedId)
        : null

      if (savedSession) {
        setActiveSessionId(savedSession.session_id)
        return
      }

      if (existing.length > 0) {
        setActiveSessionId(existing[0].session_id)
        localStorage.setItem(sessionStorageKey(userId), existing[0].session_id)
        return
      }

      try {
        await createSession()
      } catch (e) {
        if (!cancelled) setSessionsError(e.message || 'Failed to create chat session')
      }
    }

    bootstrapSessions()
    return () => {
      cancelled = true
    }
  }, [userId, isLoggedIn, guestMode, loadSessions, createSession])

  const handleSelectSession = useCallback(
    (sessionId) => {
      setActiveSessionId(sessionId)
      localStorage.setItem(sessionStorageKey(userId), sessionId)
      setTab('chat')
    },
    [userId],
  )

  const handleNewChat = useCallback(async () => {
    try {
      await createSession()
      setTab('chat')
    } catch (e) {
      setSessionsError(e.message || 'Failed to create chat session')
    }
  }, [createSession])

  const handleDeleteSession = useCallback(
    async (sessionId) => {
      setSessionsError('')
      try {
        const res = await fetch(
          `/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`,
          { method: 'DELETE' },
        )
        if (!res.ok) throw new Error(`Failed to delete session (${res.status})`)

        const remaining = sessions.filter((session) => session.session_id !== sessionId)
        setSessions(remaining)

        if (activeSessionId === sessionId) {
          if (remaining.length > 0) {
            handleSelectSession(remaining[0].session_id)
          } else {
            await createSession()
          }
        }
      } catch (e) {
        setSessionsError(e.message || 'Failed to delete chat session')
      }
    },
    [userId, sessions, activeSessionId, handleSelectSession, createSession],
  )

  const handleSessionUpdated = useCallback(async () => {
    await loadSessions()
  }, [loadSessions])

  if (!isLoggedIn && !guestMode) {
    return <Auth onAuth={handleAuth} onGuest={() => setGuestMode(true)} />
  }

  return (
    <div className="app-shell">
      <div className="app">
        <div className="header">
          <div className="logo">M</div>
          <div>
            <div className="title">Memoria</div>
            <div className="subtitle">Personal AI with long-term memory</div>
          </div>
          {isLoggedIn ? (
            <div className="header-actions">
              <span className="user-greeting">@{auth.username}</span>
              <button type="button" className="logout-btn" onClick={handleLogout}>
                Logout
              </button>
            </div>
          ) : null}
        </div>

        {!isLoggedIn && guestMode && (
          <div className="userbar">
            <label htmlFor="uid">User ID</label>
            <input
              id="uid"
              value={legacyUserId}
              onChange={(e) => setLegacyUserId(e.target.value)}
              placeholder="user id"
            />
          </div>
        )}

        <div className="workspace">
          <Sidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            loading={sessionsLoading}
            onSelect={handleSelectSession}
            onNewChat={handleNewChat}
            onDelete={handleDeleteSession}
          />

          <div className="main-panel">
            <div className="tabs">
              <button
                className={`tab ${tab === 'chat' ? 'active' : ''}`}
                onClick={() => setTab('chat')}
              >
                Chat
              </button>
              <button
                className={`tab ${tab === 'memory' ? 'active' : ''}`}
                onClick={() => setTab('memory')}
              >
                Memory
              </button>
            </div>

            {tab === 'chat' ? (
              <Chat
                userId={userId}
                sessionId={activeSessionId}
                onSessionUpdated={handleSessionUpdated}
              />
            ) : (
              <MemoryGraph userId={userId} />
            )}
            {sessionsError && <div className="error">{sessionsError}</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
