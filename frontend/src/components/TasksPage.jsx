import { useCallback, useEffect, useState } from 'react'

export default function TasksPage({ userId }) {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadTasks = useCallback(async () => {
    if (!userId) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`/api/tasks?user_id=${encodeURIComponent(userId)}`)
      if (!res.ok) throw new Error(`Failed to load tasks (${res.status})`)
      setTasks(await res.json())
    } catch (e) {
      setError(e.message || 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  async function toggleComplete(task) {
    const nextStatus = task.status === 'completed' ? 'pending' : 'completed'
    try {
      const res = await fetch(`/api/tasks/${encodeURIComponent(task.id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      })
      if (!res.ok) throw new Error(`Update failed (${res.status})`)
      const updated = await res.json()
      setTasks((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      )
    } catch (e) {
      setError(e.message || 'Failed to update task')
    }
  }

  async function deleteTask(taskId) {
    try {
      const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error(`Delete failed (${res.status})`)
      setTasks((current) => current.filter((item) => item.id !== taskId))
    } catch (e) {
      setError(e.message || 'Failed to delete task')
    }
  }

  return (
    <div className="panel page-panel tasks-page">
      <div className="page-header">
        <h2 className="page-title">Tasks</h2>
        <p className="page-subtitle">
          Manage your tasks. Create new ones in chat with /create_task.
        </p>
      </div>

      {loading && (
        <div className="page-loading">
          <span className="spinner spinner-inline" aria-hidden="true" />
          Loading tasks…
        </div>
      )}

      {!loading && error && <div className="error">{error}</div>}

      {!loading && tasks.length === 0 && (
        <div className="page-empty">
          No tasks yet. Try /create_task Buy groceries in chat.
        </div>
      )}

      {!loading && tasks.length > 0 && (
        <ul className="tasks-list">
          {[...tasks]
            .sort((a, b) => {
              if (a.status === b.status) {
                return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
              }
              return a.status === 'pending' ? -1 : 1
            })
            .map((task) => (
            <li
              key={task.id}
              className={`task-item${task.status === 'completed' ? ' completed' : ''}`}
            >
              <label className="task-checkbox-label">
                <input
                  type="checkbox"
                  checked={task.status === 'completed'}
                  onChange={() => toggleComplete(task)}
                />
                <span className="task-title">{task.title}</span>
              </label>
              {task.description && (
                <p className="task-description">{task.description}</p>
              )}
              <button
                type="button"
                className="task-delete-btn"
                onClick={() => deleteTask(task.id)}
                aria-label="Delete task"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
