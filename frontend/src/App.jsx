import { useState } from 'react'
import Chat from './components/Chat.jsx'
import MemoryGraph from './components/MemoryGraph.jsx'

// Fixed demo token expected by the backend for destructive actions.
export const DEMO_TOKEN = 'memoria-demo-token'

function randomUserId() {
  return 'user-' + Math.random().toString(36).slice(2, 8)
}

export default function App() {
  const [tab, setTab] = useState('chat')
  const [userId, setUserId] = useState(randomUserId)

  return (
    <div className="app">
      <div className="header">
        <div className="logo">M</div>
        <div>
          <div className="title">Memoria</div>
          <div className="subtitle">Personal AI with long-term memory</div>
        </div>
      </div>

      <div className="userbar">
        <label htmlFor="uid">User ID</label>
        <input
          id="uid"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="user id"
        />
      </div>

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
