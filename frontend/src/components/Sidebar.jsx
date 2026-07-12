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

  function confirmDelete() {
    if (pendingDelete) {
      onDelete(pendingDelete)
      setPendingDelete(null)
    }
  }

  return (
    <aside className="sidebar">
      <button type="button" className="btn sidebar-new" onClick={onNewChat}>
        + New Chat
      </button>

      <div className="sidebar-list">
        {loading && <div className="sidebar-empty">Loading chats…</div>}
        {!loading && sessions.length === 0 && (
          <div className="sidebar-empty">No chats yet</div>
        )}
        {!loading &&
          sessions.map((session) => (
            <div
              key={session.session_id}
              className={`sidebar-item ${session.session_id === activeSessionId ? 'active' : ''}`}
            >
              <button
                type="button"
                className="sidebar-item-btn"
                onClick={() => onSelect(session.session_id)}
                title={session.title}
              >
                {session.title}
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
    </aside>
  )
}
