import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

const SCROLL_THRESHOLD_PX = 50
const TEXTAREA_MAX_VH = 40

const VOICE_STATUS_MESSAGES = [
  '🔄 Running voice generation…',
  '🔍 Analyzing session context…',
  '📝 Creating text overview…',
  '🎙️ Synthesizing voice…',
]

const SLASH_COMMANDS = [
  {
    prefix: '/imagine',
    type: 'image',
    endpoint: '/api/generate/image',
    color: '#4ade80',
    hint: 'Image generation',
    modelLabel: 'Image Generation (wan2.1-t2i-plus)',
  },
  {
    prefix: '/gen_video',
    type: 'video',
    endpoint: '/api/generate/video',
    color: '#60a5fa',
    hint: 'Video generation',
    modelLabel: 'Video Generation (wan2.1-t2v-turbo)',
  },
  {
    prefix: '/gen_voice',
    type: 'voice',
    endpoint: '/api/generate/voice',
    color: '#c084fc',
    hint: 'Voice overview',
    modelLabel: 'Voice Generation (qwen3-tts-flash)',
  },
]

function parseMediaCommand(text) {
  const trimmed = text.trim()
  for (const command of SLASH_COMMANDS) {
    if (trimmed.startsWith(command.prefix)) {
      const prompt = trimmed.slice(command.prefix.length).trim()
      if (!prompt) return null
      return { ...command, prompt }
    }
  }
  return null
}

function detectActiveSlashCommand(text) {
  if (!text.startsWith('/')) return null
  for (const command of SLASH_COMMANDS) {
    if (text === command.prefix || text.startsWith(`${command.prefix} `)) {
      return command
    }
  }
  return null
}

function getSlashMenuItems(input) {
  if (!input.startsWith('/')) return []
  const query = input.slice(1).toLowerCase()
  if (input.includes(' ') && SLASH_COMMANDS.some((c) => input.startsWith(`${c.prefix} `))) {
    return []
  }
  return SLASH_COMMANDS.filter(
    (cmd) => query === '' || cmd.prefix.slice(1).toLowerCase().startsWith(query),
  )
}

function getInputHighlight(input) {
  for (const command of SLASH_COMMANDS) {
    if (input.startsWith(command.prefix)) {
      const rest = input.slice(command.prefix.length)
      if (rest === '' || rest.startsWith(' ')) {
        return { command: command.prefix, rest, color: command.color }
      }
    }
  }
  return null
}

function normalizeAssistantMarkdown(content) {
  let text = content
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/&lt;br\s*\/?&gt;/gi, '\n')
    .replace(/,([dxyzdtuv])/g, ' \\,$1')

  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, expr) => `$$\n${expr.trim()}\n$$`)
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, expr) => `$${expr.trim()}$`)
  text = text.replace(/\$\$\s*([\s\S]+?)\s*\$\$/g, (_, expr) => `$$\n${expr.trim()}\n$$`)
  text = text.replace(
    /(^|[^$])\$\s+([^\n$]+?)\s+\$(?!\$)/g,
    (_, before, expr) => `${before}$${expr.trim()}$`,
  )

  return text
}

function isNearBottom(element) {
  return (
    element.scrollHeight - element.scrollTop - element.clientHeight <=
    SCROLL_THRESHOLD_PX
  )
}

function extractNodeText(node) {
  if (node == null) return ''
  if (typeof node === 'string') return node
  if (Array.isArray(node)) return node.map(extractNodeText).join('')
  if (node.props?.children) return extractNodeText(node.props.children)
  return ''
}

async function copyToClipboard(text) {
  await navigator.clipboard.writeText(text)
}

function CopyButton({ text, className = 'copy-msg-btn', label = 'Copy' }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    if (!text?.trim()) return
    try {
      await copyToClipboard(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      // clipboard may be unavailable
    }
  }

  return (
    <button
      type="button"
      className={`${className}${copied ? ' copied' : ''}`}
      onClick={handleCopy}
      title={copied ? 'Copied!' : label}
      aria-label={copied ? 'Copied' : label}
    >
      {copied ? '✓' : '📋'}
      <span className="copy-btn-label">{copied ? 'Copied!' : label}</span>
    </button>
  )
}

function CodeBlock({ children, ...props }) {
  const [copied, setCopied] = useState(false)
  const code = extractNodeText(children).replace(/\n$/, '')

  async function handleCopy() {
    if (!code) return
    try {
      await copyToClipboard(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      // ignore
    }
  }

  return (
    <div className="code-block-wrap">
      <button type="button" className="copy-code-btn" onClick={handleCopy}>
        {copied ? 'Copied!' : 'Copy code'}
      </button>
      <pre {...props}>{children}</pre>
    </div>
  )
}

const markdownComponents = {
  pre: CodeBlock,
}

function getMessageCopyText(message) {
  if (message.kind === 'voice') return message.voiceOverview || ''
  if (message.kind === 'image' || message.kind === 'video') {
    return message.prompt || message.content || ''
  }
  return message.content || ''
}

function MessageBody({ message }) {
  if (message.kind === 'image' && message.mediaUrl) {
    return (
      <div className="chat-media-block">
        <img src={message.mediaUrl} alt={message.prompt || 'Generated image'} className="chat-media" />
      </div>
    )
  }

  if (message.kind === 'video' && message.mediaUrl) {
    return (
      <div className="chat-media-block">
        <video src={message.mediaUrl} controls className="chat-media" />
      </div>
    )
  }

  if (message.kind === 'voice') {
    return (
      <div className="chat-voice-block">
        <div className="chat-voice-overview">{message.voiceOverview}</div>
        {message.audioSrc && <audio controls src={message.audioSrc} className="chat-audio" />}
      </div>
    )
  }

  if (message.role === 'assistant') {
    return (
      <div className="markdown-content">
        <ReactMarkdown
          remarkPlugins={[
            remarkGfm,
            [
              remarkMath,
              {
                inlineMath: [
                  ['$', '$'],
                  ['\\(', '\\)'],
                ],
                displayMath: [
                  ['$$', '$$'],
                  ['\\[', '\\]'],
                ],
              },
            ],
          ]}
          rehypePlugins={[rehypeKatex]}
          components={markdownComponents}
        >
          {normalizeAssistantMarkdown(message.content)}
        </ReactMarkdown>
      </div>
    )
  }

  return message.content
}

export default function Chat({
  userId,
  sessionId,
  isPendingSession = false,
  isMemoryless = false,
  onSessionCreated,
  onSessionTitleUpdate,
}) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [selectedModel, setSelectedModel] = useState('qwen-plus')
  const [models, setModels] = useState([])
  const [sending, setSending] = useState(false)
  const [mediaGenType, setMediaGenType] = useState(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState('')
  const [showScrollDown, setShowScrollDown] = useState(false)
  const [slashMenuOpen, setSlashMenuOpen] = useState(false)
  const [slashHighlight, setSlashHighlight] = useState(0)
  const windowRef = useRef(null)
  const textareaRef = useRef(null)
  const stickToBottomRef = useRef(true)

  const slashMenuItems = useMemo(() => getSlashMenuItems(input), [input])
  const activeSlashCommand = useMemo(() => detectActiveSlashCommand(input), [input])
  const inputHighlight = useMemo(() => getInputHighlight(input), [input])
  const mediaModelOverride = useMemo(() => {
    if (mediaGenType) {
      return SLASH_COMMANDS.find((c) => c.type === mediaGenType) || null
    }
    return activeSlashCommand
  }, [mediaGenType, activeSlashCommand])

  const adjustTextareaHeight = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const maxPx = Math.floor((window.innerHeight * TEXTAREA_MAX_VH) / 100)
    el.style.height = `${Math.min(el.scrollHeight, maxPx)}px`
  }, [])

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    const element = windowRef.current
    if (!element) return
    element.scrollTo({ top: element.scrollHeight, behavior })
    stickToBottomRef.current = true
    setShowScrollDown(false)
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadModels() {
      try {
        const res = await fetch('/api/models')
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) setModels(data)
      } catch {
        // model list is optional on load failure
      }
    }
    loadModels()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const element = windowRef.current
    if (!element) return undefined

    function handleScroll() {
      const atBottom = isNearBottom(element)
      stickToBottomRef.current = atBottom
      setShowScrollDown(!atBottom)
    }

    element.addEventListener('scroll', handleScroll, { passive: true })
    return () => element.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    if (!sessionId || isPendingSession) {
      setMessages([])
      setLoadingHistory(false)
      stickToBottomRef.current = true
      setShowScrollDown(false)
      return
    }

    let cancelled = false
    async function loadHistory() {
      setLoadingHistory(true)
      setError('')
      stickToBottomRef.current = true
      try {
        const res = await fetch(
          `/sessions/${encodeURIComponent(sessionId)}/history?user_id=${encodeURIComponent(userId)}`,
        )
        if (!res.ok) throw new Error(`Failed to load history (${res.status})`)
        const data = await res.json()
        if (!cancelled) {
          setMessages(
            data.map((item) => ({
              role: item.role,
              content: item.content,
              kind: 'text',
              memory_ids: [],
              feedback: null,
            })),
          )
        }
      } catch (e) {
        if (!cancelled) {
          setMessages([])
          setError(e.message || 'Failed to load chat history')
        }
      } finally {
        if (!cancelled) setLoadingHistory(false)
      }
    }

    loadHistory()
    return () => {
      cancelled = true
    }
  }, [userId, sessionId, isPendingSession])

  useEffect(() => {
    if (!stickToBottomRef.current) return
    const element = windowRef.current
    if (!element) return
    element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' })
  }, [messages, sending, loadingHistory])

  useEffect(() => {
    adjustTextareaHeight()
  }, [input, adjustTextareaHeight])

  useEffect(() => {
    setSlashMenuOpen(slashMenuItems.length > 0)
    setSlashHighlight(0)
  }, [slashMenuItems.length, input])

  function insertSlashCommand(command) {
    setInput(`${command.prefix} `)
    setSlashMenuOpen(false)
    requestAnimationFrame(() => {
      textareaRef.current?.focus()
      adjustTextareaHeight()
    })
  }

  function resetTextarea() {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  async function sendFeedback(messageIndex, rating) {
    const message = messages[messageIndex]
    if (!message?.memory_ids?.length || message.feedback) return

    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          memory_ids: message.memory_ids,
          rating,
        }),
      })
      if (!res.ok) throw new Error(`Feedback failed (${res.status})`)
      setMessages((current) =>
        current.map((item, index) =>
          index === messageIndex ? { ...item, feedback: rating } : item,
        ),
      )
    } catch (e) {
      setError(e.message || 'Failed to submit feedback')
    }
  }

  function applySessionResponse(data) {
    const resolvedId = data.session_id || sessionId
    if (data.title && resolvedId) {
      onSessionTitleUpdate?.(resolvedId, data.title)
    }
    if (isPendingSession && resolvedId) {
      onSessionCreated?.(resolvedId, { isMemoryless, title: data.title })
    }
  }

  async function sendMediaCommand(command) {
    const { type, prompt, endpoint } = command
    setMessages((current) => [
      ...current,
      { role: 'user', content: `${command.prefix} ${prompt}`, kind: 'text' },
    ])

    if (type === 'voice') {
      const statusMessages = VOICE_STATUS_MESSAGES.map((content) => ({
        role: 'assistant',
        content,
        kind: 'voice-status',
      }))
      setMessages((current) => [...current, ...statusMessages])

      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: userId,
            session_id: sessionId,
            prompt,
            is_memoryless: isMemoryless,
          }),
        })

        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || `Voice generation failed (${res.status})`)
        }

        const data = await res.json()
        applySessionResponse(data)
        setMessages((current) => {
          const withoutStatus = current.filter((item) => item.kind !== 'voice-status')
          return [
            ...withoutStatus,
            {
              role: 'assistant',
              content: '',
              kind: 'voice',
              voiceOverview: data.overview_text,
              audioSrc: data.audio_data_uri,
            },
          ]
        })
      } catch (e) {
        setMessages((current) => current.filter((item) => item.kind !== 'voice-status'))
        setError(e.message || 'Voice generation failed')
      }
      return
    }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          session_id: sessionId,
          prompt,
          is_memoryless: isMemoryless,
        }),
      })

      if (res.status === 429) {
        setError(
          type === 'image'
            ? 'Image generation limit reached (5 max).'
            : 'Video generation limit reached (2 max).',
        )
        return
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Generation failed (${res.status})`)
      }

      const data = await res.json()
      applySessionResponse(data)
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: '',
          kind: type,
          mediaUrl: data.url,
          prompt,
        },
      ])
    } catch (e) {
      setError(e.message || 'Generation failed')
    }
  }

  async function sendChatMessage(text) {
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          message: text,
          session_id: sessionId,
          is_memoryless: isMemoryless,
          model: selectedModel,
        }),
      })
      if (!res.ok) throw new Error(`Backend returned ${res.status}`)
      const data = await res.json()
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: data.reply,
          kind: 'text',
          memory_ids: data.memory_ids || [],
          feedback: null,
        },
      ])
      applySessionResponse(data)
    } catch (e) {
      setError(e.message || 'Failed to send message')
    }
  }

  async function send() {
    const text = input.trim()
    if (!text || sending || !sessionId) return
    setError('')
    setInput('')
    setSlashMenuOpen(false)
    resetTextarea()
    stickToBottomRef.current = true
    setShowScrollDown(false)

    const mediaCommand = parseMediaCommand(text)
    if (mediaCommand) {
      setSending(true)
      setMediaGenType(mediaCommand.type)
      try {
        await sendMediaCommand(mediaCommand)
      } finally {
        setSending(false)
        setMediaGenType(null)
      }
      return
    }

    setMessages((m) => [...m, { role: 'user', content: text, kind: 'text' }])
    setSending(true)
    try {
      await sendChatMessage(text)
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(e) {
    if (slashMenuOpen && slashMenuItems.length > 0) {
      if (e.key === 'Escape') {
        e.preventDefault()
        setSlashMenuOpen(false)
        return
      }
      if (e.key === 'Tab') {
        e.preventDefault()
        insertSlashCommand(slashMenuItems[slashHighlight] || slashMenuItems[0])
        return
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlashHighlight((i) => (i + 1) % slashMenuItems.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlashHighlight((i) => (i - 1 + slashMenuItems.length) % slashMenuItems.length)
        return
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const modelOptions = models.length
    ? models
    : [{ id: 'qwen-plus', name: 'Qwen Plus (balanced)' }]

  return (
    <div className="panel">
      {isMemoryless && (
        <div className="memoryless-banner">
          MemoryLess Session – nothing will be remembered.
        </div>
      )}
      <div className="chat-hints">
        Type <code>/</code> for commands — <span className="slash-hint slash-hint--imagine">/imagine</span>,{' '}
        <span className="slash-hint slash-hint--video">/gen_video</span>,{' '}
        <span className="slash-hint slash-hint--voice">/gen_voice</span>
      </div>
      <div className="chat-window-wrap">
        <div className="chat-window" ref={windowRef}>
          {loadingHistory && (
            <div className="empty">
              <span className="spinner spinner-inline" aria-hidden="true" />
              Loading conversation…
            </div>
          )}
          {!loadingHistory && messages.length === 0 && !sending && (
            <div className="empty">Say hello — I&apos;ll remember what matters.</div>
          )}
          {!loadingHistory &&
            messages.map((m, i) => {
              const copyText = getMessageCopyText(m)
              const showCopy =
                m.role === 'assistant' &&
                m.kind !== 'voice-status' &&
                copyText.trim()
              const showFeedback = m.role === 'assistant' && m.memory_ids?.length > 0

              return (
                <div
                  key={i}
                  className={`bubble-row ${m.role === 'user' ? 'user-row' : 'assistant-row'}`}
                >
                  <div className={`bubble ${m.role}${m.kind === 'voice' ? ' voice-bubble' : ''}`}>
                    <MessageBody message={m} />
                  </div>
                  {(showCopy || showFeedback) && (
                    <div className="message-actions">
                      {showCopy ? <CopyButton text={copyText} label="Copy" /> : null}
                      {showFeedback ? (
                        <>
                          <button
                            type="button"
                            className={`feedback-btn ${m.feedback === 'positive' ? 'selected positive' : ''}`}
                            onClick={() => sendFeedback(i, 'positive')}
                            disabled={Boolean(m.feedback)}
                            title="Helpful response"
                            aria-label="Thumbs up"
                          >
                            👍
                          </button>
                          <button
                            type="button"
                            className={`feedback-btn ${m.feedback === 'negative' ? 'selected negative' : ''}`}
                            onClick={() => sendFeedback(i, 'negative')}
                            disabled={Boolean(m.feedback)}
                            title="Unhelpful response"
                            aria-label="Thumbs down"
                          >
                            👎
                          </button>
                        </>
                      ) : null}
                    </div>
                  )}
                </div>
              )
            })}
          {sending && !messages.some((m) => m.kind === 'voice-status') && !mediaGenType && (
            <div className="bubble assistant typing">
              <span className="spinner spinner-inline" aria-hidden="true" />
              Thinking…
            </div>
          )}
        </div>
        {showScrollDown && (
          <button
            type="button"
            className="scroll-to-bottom"
            onClick={() => scrollToBottom('smooth')}
            aria-label="Scroll to latest messages"
            title="Scroll to bottom"
          >
            ↓
          </button>
        )}
      </div>

      <div className="composer">
        {mediaModelOverride ? (
          <div
            className={`model-select model-select--media model-select--fade-in${
              mediaModelOverride.color ? ` model-select--${mediaModelOverride.type}` : ''
            }`}
            style={{ '--media-accent': mediaModelOverride.color }}
            aria-live="polite"
          >
            <span className="model-select-media-label">{mediaModelOverride.modelLabel}</span>
            {sending && mediaGenType ? (
              <span className="spinner spinner-inline model-select-spinner" aria-hidden="true" />
            ) : null}
          </div>
        ) : (
          <select
            className="model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={sending}
            aria-label="Chat model"
            title="Chat model"
          >
            {modelOptions.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        )}

        <div className="composer-input-area">
          {slashMenuOpen && slashMenuItems.length > 0 && (
            <ul className="slash-menu" role="listbox" aria-label="Slash commands">
              {slashMenuItems.map((cmd, index) => (
                <li key={cmd.prefix}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={index === slashHighlight}
                    className={`slash-menu-item${index === slashHighlight ? ' active' : ''}`}
                    style={{ '--cmd-color': cmd.color }}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      insertSlashCommand(cmd)
                    }}
                  >
                    <span className="slash-menu-cmd">{cmd.prefix}</span>
                    <span className="slash-menu-hint">{cmd.hint}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="composer-input-wrap">
            {inputHighlight && (
              <div className="composer-input-mirror" aria-hidden="true">
                <span style={{ color: inputHighlight.color }}>{inputHighlight.command}</span>
                <span>{inputHighlight.rest}</span>
              </div>
            )}
            <textarea
              ref={textareaRef}
              className={`composer-textarea${inputHighlight ? ' composer-textarea--highlight' : ''}`}
              value={input}
              rows={1}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Type a message… (/ for commands, Shift+Enter for newline)"
              disabled={sending || !sessionId}
            />
          </div>
        </div>

        <button className="btn" onClick={send} disabled={sending || !input.trim() || !sessionId}>
          {sending ? 'Sending…' : 'Send'}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  )
}
