export default function HelpPage() {
  return (
    <div className="panel page-panel help-page">
      <div className="page-header">
        <h2 className="page-title">Help</h2>
        <p className="page-subtitle">A quick guide to Memoria&apos;s key features.</p>
      </div>

      <div className="help-content">
        <section className="help-section">
          <h3>Personal Intelligence</h3>
          <p>
            Toggle Personal Intelligence (PI) in the chat toolbar. When ON, Memoria can
            access memories across all your chats. When OFF, only this session&apos;s
            context and essential facts are used.
          </p>
        </section>

        <section className="help-section">
          <h3>MemoryLess mode</h3>
          <p>
            When starting a new chat, you can enable MemoryLess. In this mode, no memories
            are stored or retrieved — your conversation stays completely private. Media
            generation commands are disabled in MemoryLess sessions.
          </p>
        </section>

        <section className="help-section">
          <h3>Memories</h3>
          <p>
            Memoria automatically extracts memories from your conversations. You can also
            add memories manually via the Memorize page, or ask the AI to forget specific
            facts in chat. View and manage all memories on the Memories tab.
          </p>
        </section>

        <section className="help-section">
          <h3>Media generation</h3>
          <p>Use these slash commands in chat (normal sessions only):</p>
          <ul>
            <li><code>/imagine</code> — generate an image from a text prompt</li>
            <li><code>/gen_video</code> — generate a short video</li>
            <li><code>/gen_voice</code> — create a spoken overview of your session</li>
          </ul>
          <p>View all generated assets on the Media page.</p>
        </section>

        <section className="help-section">
          <h3>Tasks</h3>
          <p>
            Create tasks in chat with <code>/create_task Buy groceries</code>. View all
            tasks on the Tasks page, or type <code>/tasks_list</code> to list pending
            tasks inline, and <code>/task_complete 01</code> to mark one done.
          </p>
        </section>

        <section className="help-section">
          <h3>Other commands</h3>
          <p>
            Type <code>/</code> in the chat input to see available slash commands. Use the
            model selector in the toolbar to switch between Qwen models.
          </p>
        </section>
      </div>
    </div>
  )
}
