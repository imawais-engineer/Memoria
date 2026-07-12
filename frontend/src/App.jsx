import { useCallback, useState } from 'react'
import Auth from './components/Auth.jsx'
import Chat from './components/Chat.jsx'
import MemoryGraph from './components/MemoryGraph.jsx'

// Fixed demo token expected by the backend for destructive actions.
export const DEMO_TOKEN = 'memoria-demo-token'

const AUTH_STORAGE_KEY = 'memoria_auth'

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
  }, [])

  if (!isLoggedIn && !guestMode) {
    return <Auth onAuth={handleAuth} onGuest={() => setGuestMode(true)} />
  }

  return (
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
        <Chat userId={userId} />
      ) : (
        <MemoryGraph userId={userId} />
      )}
    </div>
  )
}
