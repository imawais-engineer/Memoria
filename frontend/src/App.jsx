import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import Auth from './components/Auth.jsx'
import About from './components/About.jsx'
import Chat from './components/Chat.jsx'
import FeedbackPage from './components/FeedbackPage.jsx'
import HelpPage from './components/HelpPage.jsx'
import Landing from './components/Landing.jsx'
import MediaPage from './components/MediaPage.jsx'
import MemorizePage from './components/MemorizePage.jsx'
import MemoryGraph from './components/MemoryGraph.jsx'
import Persona from './components/Persona.jsx'
import SettingsPage from './components/SettingsPage.jsx'
import Sidebar from './components/Sidebar.jsx'
import TasksPage from './components/TasksPage.jsx'
import { IconChevronLeft, IconMenu } from './components/Icons.jsx'

// Fixed demo token expected by the backend for destructive actions.
export const DEMO_TOKEN = 'memoria-demo-token'

const AUTH_STORAGE_KEY = 'memoria_auth'
const SIDEBAR_OPEN_KEY = 'memoria_sidebar_open'

function loadSidebarOpen() {
  try {
    const stored = localStorage.getItem(SIDEBAR_OPEN_KEY)
    if (stored === null) return true
    return stored === 'true'
  } catch {
    return true
  }
}

function sessionStorageKey(userId) {
  return `memoria_active_session_${userId}`
}

/** Session id for pending chats; works on HTTP where crypto.randomUUID is missing. */
function newSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16)
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

function newPendingSession(isMemoryless = false) {
  return { sessionId: newSessionId(), isMemoryless }
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

function LandingRoute() {
  const navigate = useNavigate()
  const auth = loadStoredAuth()
  if (auth) return <Navigate to="/app" replace />
  return <Landing onGetStarted={() => navigate('/auth')} />
}

function AuthRoute({ onAuth }) {
  const navigate = useNavigate()
  const auth = loadStoredAuth()
  if (auth) return <Navigate to="/app" replace />

  return (
    <div className="auth-page">
      <Auth
        onAuth={(user) => {
          onAuth(user)
          navigate('/app', { replace: true })
        }}
      />
    </div>
  )
}

function MainApp({ auth, onAuth, onLogout }) {
  const [view, setView] = useState('chat')
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [pendingSession, setPendingSession] = useState(null)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState('')
  const [creatingChat, setCreatingChat] = useState(false)
  const [globalMemoryEnabled, setGlobalMemoryEnabled] = useState(true)
  const [defaultChatModel, setDefaultChatModel] = useState('qwen-plus')
  const [persona, setPersona] = useState(null)
  const [prefsSaving, setPrefsSaving] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(loadSidebarOpen)
  const [injectMedia, setInjectMedia] = useState(null)

  const userId = auth?.user_id
  const displayName = [auth?.first_name, auth?.last_name].filter(Boolean).join(' ')
  const activeSession = sessions.find((session) => session.session_id === activeSessionId)
  const isPendingSession = Boolean(
    pendingSession && pendingSession.sessionId === activeSessionId,
  )
  const isMemoryless = isPendingSession
    ? pendingSession.isMemoryless
    : Boolean(activeSession?.is_memoryless)

  const fetchPreferences = useCallback(async () => {
    if (!userId) return
    try {
      const res = await fetch(
        `/auth/preferences?user_id=${encodeURIComponent(userId)}`,
      )
      if (!res.ok) return
      const data = await res.json()
      setGlobalMemoryEnabled(data.global_memory_enabled)
      setDefaultChatModel(data.default_chat_model || 'qwen-plus')
      setPersona(data.persona ?? null)
      onAuth({
        ...auth,
        user_id: userId,
        username: auth.username,
        global_memory_enabled: data.global_memory_enabled,
        default_chat_model: data.default_chat_model,
        persona: data.persona,
      })
    } catch {
      // preferences are optional on load failure
    }
  }, [userId, auth, onAuth])

  useEffect(() => {
    setGlobalMemoryEnabled(auth.global_memory_enabled ?? true)
    setDefaultChatModel(auth.default_chat_model || 'qwen-plus')
    fetchPreferences()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

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

  const startPendingChat = useCallback((isMemorylessFlag = false) => {
    const pending = newPendingSession(isMemorylessFlag)
    setPendingSession(pending)
    setActiveSessionId(pending.sessionId)
    if (!isMemorylessFlag) {
      localStorage.setItem(sessionStorageKey(userId), pending.sessionId)
    } else {
      localStorage.removeItem(sessionStorageKey(userId))
    }
    setView('chat')
  }, [userId])

  useEffect(() => {
    if (!userId) return

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
  }, [userId, loadSessions, cleanupMemorylessSessions])

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
      setView('chat')
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
    async (sessionId, { isMemoryless: createdMemoryless, title }) => {
      setPendingSession(null)
      setActiveSessionId(sessionId)
      if (!createdMemoryless) {
        localStorage.setItem(sessionStorageKey(userId), sessionId)
      }
      await loadSessions()
      if (title) {
        setSessions((current) => {
          const exists = current.some((s) => s.session_id === sessionId)
          if (exists) {
            return current.map((s) =>
              s.session_id === sessionId ? { ...s, title } : s,
            )
          }
          return current
        })
      }
    },
    [loadSessions, userId],
  )

  const handleSessionTitleUpdate = useCallback((sessionId, title) => {
    setSessions((current) =>
      current.map((session) =>
        session.session_id === sessionId ? { ...session, title } : session,
      ),
    )
  }, [])

  const handleRenameSession = useCallback((sessionId, title) => {
    handleSessionTitleUpdate(sessionId, title)
  }, [handleSessionTitleUpdate])

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((open) => {
      const next = !open
      localStorage.setItem(SIDEBAR_OPEN_KEY, String(next))
      return next
    })
  }, [])

  const handlePersonaSaved = useCallback((data) => {
    setPersona(data.persona ?? null)
    onAuth({
      ...auth,
      persona: data.persona,
    })
  }, [auth, onAuth])

  const handleSettingsSaved = useCallback((data) => {
    setGlobalMemoryEnabled(data.global_memory_enabled)
    setDefaultChatModel(data.default_chat_model || 'qwen-plus')
    setPersona(data.persona ?? null)
    onAuth({
      ...auth,
      global_memory_enabled: data.global_memory_enabled,
      default_chat_model: data.default_chat_model,
      persona: data.persona,
    })
  }, [auth, onAuth])

  const disableGlobalMemory = useCallback(async () => {
    if (!globalMemoryEnabled || prefsSaving) return
    setPrefsSaving(true)
    setSessionsError('')
    try {
      const res = await fetch('/auth/preferences', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: auth.user_id,
          global_memory_enabled: false,
        }),
      })
      if (!res.ok) throw new Error(`Failed to update preference (${res.status})`)
      const data = await res.json()
      setGlobalMemoryEnabled(data.global_memory_enabled)
      onAuth({
        ...auth,
        global_memory_enabled: data.global_memory_enabled,
      })
    } catch (e) {
      setSessionsError(e.message || 'Failed to update Personal Intelligence setting')
    } finally {
      setPrefsSaving(false)
    }
  }, [auth, globalMemoryEnabled, onAuth, prefsSaving])

  const handleGlobalMemoryToggle = useCallback(async () => {
    if (prefsSaving || isMemoryless) return
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
      onAuth({
        ...auth,
        global_memory_enabled: data.global_memory_enabled,
      })
    } catch (e) {
      setSessionsError(e.message || 'Failed to update Personal Intelligence setting')
    } finally {
      setPrefsSaving(false)
    }
  }, [auth, globalMemoryEnabled, isMemoryless, onAuth, prefsSaving])

  const handleMemorylessChange = useCallback(async (enabled) => {
    if (!isPendingSession || !pendingSession) return
    setPendingSession({
      ...pendingSession,
      isMemoryless: enabled,
    })
    if (enabled) {
      localStorage.removeItem(sessionStorageKey(userId))
      if (globalMemoryEnabled) {
        await disableGlobalMemory()
      }
    } else {
      localStorage.setItem(sessionStorageKey(userId), pendingSession.sessionId)
    }
  }, [
    disableGlobalMemory,
    globalMemoryEnabled,
    isPendingSession,
    pendingSession,
    userId,
  ])

  function renderMainView() {
    switch (view) {
      case 'chat':
        return (
          <Chat
            userId={userId}
            sessionId={activeSessionId}
            isPendingSession={isPendingSession}
            isMemoryless={isMemoryless}
            globalMemoryEnabled={globalMemoryEnabled}
            defaultChatModel={defaultChatModel}
            prefsSaving={prefsSaving}
            sidebarOpen={sidebarOpen}
            creatingChat={creatingChat}
            injectMedia={injectMedia}
            onSessionCreated={handleSessionCreated}
            onSessionTitleUpdate={handleSessionTitleUpdate}
            onGlobalMemoryToggle={handleGlobalMemoryToggle}
            onMemorylessChange={handleMemorylessChange}
            onNewChat={handleNewChat}
          />
        )
      case 'memory':
        return (
          <MemoryGraph
            userId={userId}
            username={auth?.username}
            sessionId={activeSessionId}
          />
        )
      case 'persona':
        return (
          <Persona
            userId={auth.user_id}
            persona={persona}
            onSaved={handlePersonaSaved}
          />
        )
      case 'memorize':
        return <MemorizePage userId={userId} />
      case 'media':
        return <MediaPage userId={userId} />
      case 'tasks':
        return <TasksPage userId={userId} />
      case 'settings':
        return (
          <SettingsPage
            userId={userId}
            globalMemoryEnabled={globalMemoryEnabled}
            defaultChatModel={defaultChatModel}
            persona={persona}
            onSaved={handleSettingsSaved}
          />
        )
      case 'feedback':
        return <FeedbackPage userId={userId} />
      case 'help':
        return <HelpPage />
      case 'about':
        return <About />
      default:
        return null
    }
  }

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

  return (
    <div className="app-shell">
      <button
        type="button"
        className="sidebar-toggle"
        onClick={toggleSidebar}
        aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        aria-expanded={sidebarOpen}
        title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
      >
        {sidebarOpen ? <IconChevronLeft /> : <IconMenu />}
      </button>

      <div className={`app-layout${sidebarOpen ? '' : ' app-layout--sidebar-closed'}`}>
        <Sidebar
          userId={userId}
          username={auth.username}
          displayName={displayName}
          sessions={sessions}
          activeSessionId={activeSessionId}
          activeView={view}
          loading={sessionsLoading}
          open={sidebarOpen}
          creatingChat={creatingChat}
          onSelect={handleSelectSession}
          onNewChat={handleNewChat}
          onNavigate={setView}
          onDelete={handleDeleteSession}
          onRename={handleRenameSession}
          onLogout={onLogout}
        />

        <main className={`canvas${sidebarOpen ? '' : ' canvas--sidebar-closed'}`}>
          <div className="canvas-body">
            {renderMainView()}
          </div>
          {sessionsError && <div className="canvas-error">{sessionsError}</div>}
        </main>
      </div>
    </div>
  )
}

function AppRoute({ auth, onAuth, onLogout }) {
  const navigate = useNavigate()
  if (!auth?.user_id) return <Navigate to="/auth" replace />

  function handleLogout() {
    onLogout()
    navigate('/', { replace: true })
  }

  return <MainApp auth={auth} onAuth={onAuth} onLogout={handleLogout} />
}

export default function App() {
  const [auth, setAuth] = useState(loadStoredAuth)

  const handleAuth = useCallback((user) => {
    setAuth((current) => {
      if (
        current?.user_id === user.user_id &&
        current?.username === user.username &&
        current?.global_memory_enabled === user.global_memory_enabled &&
        current?.default_chat_model === user.default_chat_model &&
        current?.first_name === user.first_name &&
        current?.last_name === user.last_name &&
        JSON.stringify(current?.persona) === JSON.stringify(user.persona)
      ) {
        return current
      }
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user))
      return user
    })
  }, [])

  const handleLogout = useCallback(() => {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    setAuth(null)
  }, [])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingRoute />} />
        <Route path="/auth" element={<AuthRoute onAuth={handleAuth} />} />
        <Route
          path="/app"
          element={<AppRoute auth={auth} onAuth={handleAuth} onLogout={handleLogout} />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
