import { useState } from 'react'

export default function Sidebar({
  sessions,
  activeSessionId,
  loading,
  onSelect,
  onNewChat,
  onDelete,
}) {
  const [pendingDelete, setPendingDelete] = useState(null)
  const [memorylessChecked, setMemorylessChecked] = useState(false)
  const [pendingMemoryless, setPendingMemoryless] = useState(false)

  function confirmDelete() {
    if (pendingDelete) {
      onDelete(pendingDelete)
      setPendingDelete(null)
    }
  }

  function handleNewChatClick() {
    if (memorylessChecked) {
      setPendingMemoryless(true)
      return
    }
    onNewChat(false)
  }

  function confirmMemoryless() {
    setPendingMemoryless(false)
    setMemorylessChecked(false)
    onNewChat(true)
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-new-row">
        <button type="button" className="btn sidebar-new" onClick={handleNewChatClick}>
          + New Chat
        </button>
      </div>

      <label className="memoryless-toggle">
        <input
          type="checkbox"
          checked={memorylessChecked}
          onChange={(e) => setMemorylessChecked(e.target.checked)}
        />
        <span>MemoryLess Mode</span>
      </label>

      <div className="sidebar-list">
        {loading && <div className="sidebar-empty">Loading chats…</div>}
        {!loading && sessions.length === 0 && (
          <div className="sidebar-empty">No chats yet</div>
        )}
        {!loading &&
          sessions.map((session) => (
            <div
              key={session.session_id}
              className={`sidebar-item ${session.session_id === activeSessionId ? 'active' : ''} ${session.is_memoryless ? 'memoryless' : ''}`}
            >
              <button
                type="button"
                className="sidebar-item-btn"
                onClick={() => onSelect(session.session_id)}
                title={session.title}
              >
                {session.is_memoryless && (
                  <span className="sidebar-icon" aria-hidden="true">
                    🕶️
                  </span>
                )}
                <span className="sidebar-item-title">{session.title}</span>
              </button>
              <button
                type="button"
                className="sidebar-delete"
                onClick={() => setPendingDelete(session.session_id)}
                aria-label={`Delete ${session.title}`}
                title="Delete chat"
              >
                ×
              </button>
            </div>
          ))}
      </div>

      {pendingDelete && (
        <div className="modal-backdrop" onClick={() => setPendingDelete(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Delete chat?</h3>
            <p className="modal-text">
              This will permanently delete the chat and all memories extracted from it.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn cancel"
                onClick={() => setPendingDelete(null)}
              >
                Cancel
              </button>
              <button type="button" className="modal-btn danger" onClick={confirmDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingMemoryless && (
        <div className="modal-backdrop" onClick={() => setPendingMemoryless(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Start MemoryLess session?</h3>
            <p className="modal-text">
              This session will not use or store any memories. Your conversation will be
              completely private and won&apos;t be remembered.
            </p>
            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn cancel"
                onClick={() => setPendingMemoryless(false)}
              >
                Cancel
              </button>
              <button type="button" className="modal-btn danger" onClick={confirmMemoryless}>
                Start private chat
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
