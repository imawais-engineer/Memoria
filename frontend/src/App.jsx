import { useCallback, useEffect, useState } from 'react'
import Auth from './components/Auth.jsx'
import Chat from './components/Chat.jsx'
import Landing from './components/Landing.jsx'
import MemoryGraph from './components/MemoryGraph.jsx'
import Persona from './components/Persona.jsx'
import Sidebar from './components/Sidebar.jsx'

// Fixed demo token expected by the backend for destructive actions.
export const DEMO_TOKEN = 'memoria-demo-token'

const AUTH_STORAGE_KEY = 'memoria_auth'

function sessionStorageKey(userId) {
  return `memoria_active_session_${userId}`
}

function newPendingSession(isMemoryless = false) {
  return { sessionId: crypto.randomUUID(), isMemoryless }
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
  const [authView, setAuthView] = useState('landing')
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [pendingSession, setPendingSession] = useState(null)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState('')
  const [creatingChat, setCreatingChat] = useState(false)
  const [globalMemoryEnabled, setGlobalMemoryEnabled] = useState(true)
  const [persona, setPersona] = useState(null)
  const [prefsSaving, setPrefsSaving] = useState(false)

  const isLoggedIn = Boolean(auth?.user_id)
  const userId = auth?.user_id
  const activeSession = sessions.find((session) => session.session_id === activeSessionId)
  const isPendingSession = Boolean(
    pendingSession && pendingSession.sessionId === activeSessionId,
  )
  const isMemoryless = isPendingSession
    ? pendingSession.isMemoryless
    : Boolean(activeSession?.is_memoryless)

  const handleAuth = useCallback((user) => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user))
    setAuth(user)
    setGlobalMemoryEnabled(user.global_memory_enabled ?? true)
    setPersona(user.persona ?? null)
    setAuthView('app')
  }, [])

  const handleLogout = useCallback(() => {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    setAuth(null)
    setSessions([])
    setActiveSessionId(null)
    setPendingSession(null)
    setGlobalMemoryEnabled(true)
    setPersona(null)
    setTab('chat')
    setAuthView('landing')
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
    if (!userId) return []
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

  const startPendingChat = useCallback((isMemoryless = false) => {
    const pending = newPendingSession(isMemoryless)
    setPendingSession(pending)
    setActiveSessionId(pending.sessionId)
    if (!isMemoryless) {
      localStorage.setItem(sessionStorageKey(userId), pending.sessionId)
    } else {
      localStorage.removeItem(sessionStorageKey(userId))
    }
    setTab('chat')
  }, [userId])

  useEffect(() => {
    if (!isLoggedIn || !userId) return

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
        setPendingSession(null)
        setActiveSessionId(savedSession.session_id)
        return
      }

      if (cleaned.length > 0) {
        setPendingSession(null)
        setActiveSessionId(cleaned[0].session_id)
        localStorage.setItem(sessionStorageKey(userId), cleaned[0].session_id)
        return
      }

      const pending = newPendingSession(false)
      setPendingSession(pending)
      setActiveSessionId(pending.sessionId)
    }

    bootstrapSessions()
    return () => {
      cancelled = true
    }
  }, [userId, isLoggedIn, loadSessions, cleanupMemorylessSessions])

  const handleSelectSession = useCallback(
    async (sessionId) => {
      if (
        activeSession?.is_memoryless &&
        activeSessionId &&
        sessionId !== activeSessionId &&
        !isPendingSession
      ) {
        await deleteSessionById(activeSessionId, { quiet: true })
      }

      const target = sessions.find((session) => session.session_id === sessionId)
      setPendingSession(null)
      setActiveSessionId(sessionId)
      if (!target?.is_memoryless) {
        localStorage.setItem(sessionStorageKey(userId), sessionId)
      } else {
        localStorage.removeItem(sessionStorageKey(userId))
      }
      setTab('chat')
    },
    [
      activeSession,
      activeSessionId,
      deleteSessionById,
      isPendingSession,
      sessions,
      userId,
    ],
  )

  const handleNewChat = useCallback(async () => {
    setSessionsError('')
    setCreatingChat(true)
    try {
      if (
        activeSession?.is_memoryless &&
        activeSessionId &&
        !isPendingSession
      ) {
        await deleteSessionById(activeSessionId, { quiet: true })
      }
      startPendingChat(false)
    } catch (e) {
      setSessionsError(e.message || 'Failed to start chat')
    } finally {
      setCreatingChat(false)
    }
  }, [
    activeSession,
    activeSessionId,
    deleteSessionById,
    isPendingSession,
    startPendingChat,
  ])

  const handleNewMemorylessChat = useCallback(async () => {
    setSessionsError('')
    setCreatingChat(true)
    try {
      if (
        activeSession?.is_memoryless &&
        activeSessionId &&
        !isPendingSession
      ) {
        await deleteSessionById(activeSessionId, { quiet: true })
      }
      startPendingChat(true)
    } catch (e) {
      setSessionsError(e.message || 'Failed to start memoryless chat')
    } finally {
      setCreatingChat(false)
    }
  }, [
    activeSession,
    activeSessionId,
    deleteSessionById,
    isPendingSession,
    startPendingChat,
  ])

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
            startPendingChat(false)
          }
        }
      } catch (e) {
        setSessionsError(e.message || 'Failed to delete chat session')
      }
    },
    [
      activeSessionId,
      deleteSessionById,
      handleSelectSession,
      sessions,
      startPendingChat,
    ],
  )

  const handleSessionCreated = useCallback(
    async (sessionId, { isMemoryless: createdMemoryless }) => {
      setPendingSession(null)
      setActiveSessionId(sessionId)
      if (!createdMemoryless) {
        localStorage.setItem(sessionStorageKey(userId), sessionId)
      }
      await loadSessions()
    },
    [loadSessions, userId],
  )

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
    if (!activeSession?.is_memoryless || !activeSessionId || isPendingSession) {
      return undefined
    }

    function cleanupOnUnload() {
      const url = `/sessions/${encodeURIComponent(activeSessionId)}?user_id=${encodeURIComponent(userId)}`
      fetch(url, { method: 'DELETE', keepalive: true }).catch(() => {})
    }

    window.addEventListener('beforeunload', cleanupOnUnload)
    return () => window.removeEventListener('beforeunload', cleanupOnUnload)
  }, [activeSession?.is_memoryless, activeSessionId, isPendingSession, userId])

  if (!isLoggedIn) {
    if (authView === 'landing') {
      return <Landing onLaunch={() => setAuthView('auth')} />
    }
    return <Auth onAuth={handleAuth} />
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
          <div className="header-actions">
            <span className="user-greeting">@{auth.username}</span>
            <button type="button" className="logout-btn" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </div>

        <div className="workspace">
          <Sidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            loading={sessionsLoading}
            globalMemoryEnabled={globalMemoryEnabled}
            prefsSaving={prefsSaving}
            isMemoryless={isMemoryless}
            creatingChat={creatingChat}
            onSelect={handleSelectSession}
            onNewChat={handleNewChat}
            onNewMemorylessChat={handleNewMemorylessChat}
            onDelete={handleDeleteSession}
            onGlobalMemoryToggle={handleGlobalMemoryToggle}
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
              <button
                className={`tab ${tab === 'persona' ? 'active' : ''}`}
                onClick={() => setTab('persona')}
              >
                Persona
              </button>
            </div>

            {tab === 'chat' ? (
              <Chat
                userId={userId}
                sessionId={activeSessionId}
                isPendingSession={isPendingSession}
                isMemoryless={isMemoryless}
                onSessionCreated={handleSessionCreated}
              />
            ) : tab === 'memory' ? (
              <MemoryGraph userId={userId} sessionId={activeSessionId} />
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
