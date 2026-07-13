import { useCallback, useEffect, useState } from 'react'
import Auth from './components/Auth.jsx'
import Chat from './components/Chat.jsx'
import MemoryGraph from './components/MemoryGraph.jsx'
import Persona from './components/Persona.jsx'
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
  const [globalMemoryEnabled, setGlobalMemoryEnabled] = useState(true)
  const [persona, setPersona] = useState(null)
  const [prefsSaving, setPrefsSaving] = useState(false)

  const isLoggedIn = Boolean(auth?.user_id)
  const userId = isLoggedIn ? auth.user_id : legacyUserId
  const activeSession = sessions.find((session) => session.session_id === activeSessionId)
  const isMemoryless = Boolean(activeSession?.is_memoryless)

  const handleAuth = useCallback((user) => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user))
    setAuth(user)
    setGlobalMemoryEnabled(user.global_memory_enabled ?? true)
    setPersona(user.persona ?? null)
    setGuestMode(false)
  }, [])

  const handleLogout = useCallback(() => {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    setAuth(null)
    setGuestMode(false)
    setLegacyUserId(randomUserId())
    setSessions([])
    setActiveSessionId(null)
    setGlobalMemoryEnabled(true)
    setPersona(null)
    setTab('chat')
  }, [])

  const fetchPreferences = useCallback(async () => {
    if (!isLoggedIn) return
    try {
      const res = await fetch(
        `/auth/preferences?user_id=${encodeURIComponent(auth.user_id)}`,
      )
      if (!res.ok) return
      const data = await res.json()
      setGlobalMemoryEnabled(data.global_memory_enabled)
      setPersona(data.persona ?? null)
      setAuth((current) => {
        const next = {
          ...current,
          global_memory_enabled: data.global_memory_enabled,
          persona: data.persona,
        }
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(next))
        return next
      })
    } catch {
      // preferences are optional on load failure
    }
  }, [isLoggedIn, auth?.user_id])

  useEffect(() => {
    if (isLoggedIn) {
      setGlobalMemoryEnabled(auth.global_memory_enabled ?? true)
      fetchPreferences()
    }
  }, [isLoggedIn, auth?.user_id, auth?.global_memory_enabled, fetchPreferences])

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

  const deleteSessionById = useCallback(
    async (sessionId, { quiet = false } = {}) => {
      const res = await fetch(
        `/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`,
        { method: 'DELETE' },
      )
      if (!res.ok) {
        if (!quiet) throw new Error(`Failed to delete session (${res.status})`)
        return false
      }
      setSessions((current) =>
        current.filter((session) => session.session_id !== sessionId),
      )
      return true
    },
    [userId],
  )

  const cleanupMemorylessSessions = useCallback(
    async (sessionList) => {
      const stale = sessionList.filter((session) => session.is_memoryless)
      await Promise.all(
        stale.map((session) => deleteSessionById(session.session_id, { quiet: true })),
      )
      return sessionList.filter((session) => !session.is_memoryless)
    },
    [deleteSessionById],
  )

  const createSession = useCallback(
    async (isMemoryless = false) => {
      const res = await fetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, is_memoryless: isMemoryless }),
      })
      if (!res.ok) throw new Error(`Failed to create session (${res.status})`)
      const session = await res.json()
      setSessions((current) => [
        session,
        ...current.filter((item) => item.session_id !== session.session_id),
      ])
      setActiveSessionId(session.session_id)
      if (!isMemoryless) {
        localStorage.setItem(sessionStorageKey(userId), session.session_id)
      }
      return session
    },
    [userId],
  )

  useEffect(() => {
    if (!isLoggedIn && !guestMode) return

    let cancelled = false

    async function bootstrapSessions() {
      const existing = await loadSessions()
      if (cancelled) return

      const cleaned = await cleanupMemorylessSessions(existing)
      if (cancelled) return
      setSessions(cleaned)

      const savedId = localStorage.getItem(sessionStorageKey(userId))
      const savedSession = savedId
        ? cleaned.find((session) => session.session_id === savedId)
        : null

      if (savedSession) {
        setActiveSessionId(savedSession.session_id)
        return
      }

      if (cleaned.length > 0) {
        setActiveSessionId(cleaned[0].session_id)
        localStorage.setItem(sessionStorageKey(userId), cleaned[0].session_id)
        return
      }

      try {
        await createSession(false)
      } catch (e) {
        if (!cancelled) setSessionsError(e.message || 'Failed to create chat session')
      }
    }

    bootstrapSessions()
    return () => {
      cancelled = true
    }
  }, [userId, isLoggedIn, guestMode, loadSessions, createSession, cleanupMemorylessSessions])

  const handleSelectSession = useCallback(
    async (sessionId) => {
      if (
        activeSession?.is_memoryless &&
        activeSessionId &&
        sessionId !== activeSessionId
      ) {
        await deleteSessionById(activeSessionId, { quiet: true })
      }

      const target = sessions.find((session) => session.session_id === sessionId)
      setActiveSessionId(sessionId)
      if (!target?.is_memoryless) {
        localStorage.setItem(sessionStorageKey(userId), sessionId)
      } else {
        localStorage.removeItem(sessionStorageKey(userId))
      }
      setTab('chat')
    },
    [activeSession, activeSessionId, deleteSessionById, sessions, userId],
  )

  const handleNewChat = useCallback(
    async (isMemoryless = false) => {
      try {
        if (
          activeSession?.is_memoryless &&
          activeSessionId
        ) {
          await deleteSessionById(activeSessionId, { quiet: true })
        }
        await createSession(isMemoryless)
        setTab('chat')
      } catch (e) {
        setSessionsError(e.message || 'Failed to create chat session')
      }
    },
    [activeSession, activeSessionId, createSession, deleteSessionById],
  )

  const handleDeleteSession = useCallback(
    async (sessionId) => {
      setSessionsError('')
      try {
        await deleteSessionById(sessionId)

        if (activeSessionId === sessionId) {
          const remaining = sessions.filter((session) => session.session_id !== sessionId)
          if (remaining.length > 0) {
            await handleSelectSession(remaining[0].session_id)
          } else {
            await createSession(false)
          }
        }
      } catch (e) {
        setSessionsError(e.message || 'Failed to delete chat session')
      }
    },
    [
      activeSessionId,
      createSession,
      deleteSessionById,
      handleSelectSession,
      sessions,
    ],
  )

  const handleSessionUpdated = useCallback(async () => {
    await loadSessions()
  }, [loadSessions])

  const handlePersonaSaved = useCallback((data) => {
    setPersona(data.persona ?? null)
    setAuth((current) => {
      const updated = {
        ...current,
        persona: data.persona,
      }
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(updated))
      return updated
    })
  }, [])

  const handleGlobalMemoryToggle = useCallback(async () => {
    if (!isLoggedIn || prefsSaving) return
    const nextValue = !globalMemoryEnabled
    setPrefsSaving(true)
    setSessionsError('')
    try {
      const res = await fetch('/auth/preferences', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: auth.user_id,
          global_memory_enabled: nextValue,
        }),
      })
      if (!res.ok) throw new Error(`Failed to update preference (${res.status})`)
      const data = await res.json()
      setGlobalMemoryEnabled(data.global_memory_enabled)
      setAuth((current) => {
        const updated = {
          ...current,
          global_memory_enabled: data.global_memory_enabled,
        }
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(updated))
        return updated
      })
    } catch (e) {
      setSessionsError(e.message || 'Failed to update Personal Intelligence setting')
    } finally {
      setPrefsSaving(false)
    }
  }, [auth?.user_id, globalMemoryEnabled, isLoggedIn, prefsSaving])

  useEffect(() => {
    if (!activeSession?.is_memoryless || !activeSessionId) return undefined

    function cleanupOnUnload() {
      const url = `/sessions/${encodeURIComponent(activeSessionId)}?user_id=${encodeURIComponent(userId)}`
      fetch(url, { method: 'DELETE', keepalive: true }).catch(() => {})
    }

    window.addEventListener('beforeunload', cleanupOnUnload)
    return () => window.removeEventListener('beforeunload', cleanupOnUnload)
  }, [activeSession?.is_memoryless, activeSessionId, userId])

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
              <label
                className={`pref-toggle ${isMemoryless ? 'disabled' : ''}`}
                title={
                  isMemoryless
                    ? 'Personal Intelligence is unavailable during MemoryLess sessions'
                    : 'When ON, the agent recalls Personal Memories and summaries from all chats. When OFF, only Session Memory and essential (core) facts are used.'
                }
              >
                <input
                  type="checkbox"
                  checked={globalMemoryEnabled}
                  onChange={handleGlobalMemoryToggle}
                  disabled={prefsSaving || isMemoryless}
                />
                <span>Personal Intelligence</span>
              </label>
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
              {isLoggedIn && (
                <button
                  className={`tab ${tab === 'persona' ? 'active' : ''}`}
                  onClick={() => setTab('persona')}
                >
                  Persona
                </button>
              )}
            </div>

            {tab === 'chat' ? (
              <Chat
                userId={userId}
                sessionId={activeSessionId}
                isMemoryless={isMemoryless}
                onSessionUpdated={handleSessionUpdated}
              />
            ) : tab === 'memory' ? (
              <MemoryGraph userId={userId} />
            ) : (
              <Persona
                userId={auth.user_id}
                persona={persona}
                onSaved={handlePersonaSaved}
              />
            )}
            {sessionsError && <div className="error">{sessionsError}</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
