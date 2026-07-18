import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import ModelDropdown from './ModelDropdown.jsx'
import MemoriaLogo from './MemoriaLogo.jsx'
import {
  IconCheck,
  IconCopy,
  IconSend,
  IconThumbsDown,
  IconThumbsUp,
} from './Icons.jsx'

const SCROLL_THRESHOLD_PX = 50
const TEXTAREA_MAX_VH = 40

const PI_INFO =
  'When enabled, I can access all your memories across chats. When disabled, I only see this session\'s context and essential facts.'

const MEMORYLESS_INFO =
  'This session will not use or store any memories. Your conversation will be completely private and won\'t be remembered.'

const VOICE_STATUS_MESSAGES = [
  'Running voice generation…',
  'Analyzing session context…',
  'Creating text overview…',
  'Synthesizing voice…',
]

const SLASH_COMMANDS = [
  {
    prefix: '/imagine',
    type: 'image',
    endpoint: '/api/generate/image',
    color: '#22c55e',
    hint: 'Image generation',
    modelLabel: 'Image Generation (wan2.1-t2i-plus)',
  },
  {
    prefix: '/gen_video',
    type: 'video',
    endpoint: '/api/generate/video',
    color: '#3b82f6',
    hint: 'Video generation',
    modelLabel: 'Video Generation (wan2.1-t2v-turbo)',
  },
  {
    prefix: '/gen_voice',
    type: 'voice',
    endpoint: '/api/generate/voice',
    color: '#a855f7',
    hint: 'Voice overview',
    modelLabel: 'Voice Generation (qwen3-tts-flash)',
  },
]

function parseCreateTask(text) {
  const trimmed = text.trim()
  if (!trimmed.startsWith('/create_task')) return null
  const title = trimmed.slice('/create_task'.length).trim()
  if (!title) return null
  return title
}

function isShowTasksCommand(text) {
  return text.trim() === '/show_tasks'
}

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
      {copied ? <IconCheck /> : <IconCopy />}
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
  globalMemoryEnabled = true,
  defaultChatModel = 'qwen-plus',
  prefsSaving = false,
  sidebarOpen = true,
  creatingChat = false,
  injectMedia = null,
  onSessionCreated,
  onSessionTitleUpdate,
  onGlobalMemoryToggle,
  onMemorylessChange,
  onNewChat,
}) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [selectedModel, setSelectedModel] = useState(defaultChatModel)
  const [models, setModels] = useState([])
  const [sending, setSending] = useState(false)
  const [mediaGenType, setMediaGenType] = useState(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState('')
  const [showScrollDown, setShowScrollDown] = useState(false)
  const [slashMenuOpen, setSlashMenuOpen] = useState(false)
  const [slashHighlight, setSlashHighlight] = useState(0)
  const [infoDialog, setInfoDialog] = useState(null)
  const windowRef = useRef(null)
  const textareaRef = useRef(null)
  const stickToBottomRef = useRef(true)
  const lastInjectNonce = useRef(null)

  const slashMenuItems = useMemo(() => getSlashMenuItems(input), [input])
  const activeSlashCommand = useMemo(() => detectActiveSlashCommand(input), [input])
  const inputHighlight = useMemo(() => getInputHighlight(input), [input])
  const mediaModelOverride = useMemo(() => {
    if (mediaGenType) {
      return SLASH_COMMANDS.find((c) => c.type === mediaGenType) || null
    }
    return activeSlashCommand
  }, [mediaGenType, activeSlashCommand])

  const showMemorylessToggle = isPendingSession && messages.length === 0 && !sending
  const isStreaming = messages.some((m) => m.streaming)

  useEffect(() => {
    setSelectedModel(defaultChatModel || 'qwen-plus')
  }, [defaultChatModel])

  useEffect(() => {
    if (!infoDialog) return undefined
    const timer = setTimeout(() => setInfoDialog(null), 4500)
    return () => clearTimeout(timer)
  }, [infoDialog])

  async function handlePiToggle() {
    if (isMemoryless || prefsSaving) return
    const turningOn = !globalMemoryEnabled
    await onGlobalMemoryToggle?.()
    if (turningOn) setInfoDialog('pi')
  }

  async function handleMemorylessToggle() {
    const turningOn = !isMemoryless
    await onMemorylessChange?.(turningOn)
    if (turningOn) setInfoDialog('memoryless')
  }

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
    if (!injectMedia || injectMedia.nonce === lastInjectNonce.current) return
    lastInjectNonce.current = injectMedia.nonce

    const kind = injectMedia.type === 'voice' || injectMedia.type === 'audio'
      ? 'voice'
      : injectMedia.type

    setMessages((current) => [
      ...current,
      {
        role: 'assistant',
        content: '',
        kind: kind === 'image' || kind === 'video' ? kind : 'voice',
        mediaUrl: kind === 'image' || kind === 'video' ? injectMedia.url : undefined,
        audioSrc: kind === 'voice' ? injectMedia.url : undefined,
        voiceOverview: kind === 'voice' ? injectMedia.prompt : undefined,
        prompt: injectMedia.prompt,
      },
    ])
    stickToBottomRef.current = true
  }, [injectMedia])

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

  async function sendChatMessageStream(text) {
    const res = await fetch('/chat/stream', {
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

    setMessages((m) => [
      ...m,
      {
        role: 'assistant',
        content: '',
        kind: 'text',
        memory_ids: [],
        feedback: null,
        streaming: true,
      },
    ])

    const reader = res.body?.getReader()
    if (!reader) throw new Error('Streaming not supported')

    const decoder = new TextDecoder()
    let buffer = ''
    let finalData = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        let data
        try {
          data = JSON.parse(line.slice(6))
        } catch {
          continue
        }
        if (data.error) throw new Error(data.error)
        if (data.token) {
          setMessages((current) => {
            const copy = [...current]
            const last = copy[copy.length - 1]
            if (last?.role === 'assistant' && last.streaming) {
              copy[copy.length - 1] = {
                ...last,
                content: last.content + data.token,
              }
            }
            return copy
          })
        }
        if (data.done) {
          finalData = data
        }
      }
    }

    setMessages((current) => {
      const copy = [...current]
      const last = copy[copy.length - 1]
      if (last?.role === 'assistant' && last.streaming) {
        copy[copy.length - 1] = {
          ...last,
          streaming: false,
          memory_ids: finalData?.memory_ids || [],
        }
      }
      return copy
    })

    if (finalData) {
      applySessionResponse(finalData)
    }
  }

  async function sendCreateTask(title) {
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, title }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || `Failed to create task (${res.status})`)
    }
    const task = await res.json()
    setMessages((current) => [
      ...current,
      {
        role: 'assistant',
        content: `✅ Task created: **${task.title}**`,
        kind: 'text',
        memory_ids: [],
        feedback: null,
      },
    ])
  }

  async function sendShowTasks() {
    const res = await fetch(`/api/tasks?user_id=${encodeURIComponent(userId)}`)
    if (!res.ok) throw new Error(`Failed to load tasks (${res.status})`)
    const tasks = await res.json()
    let content
    if (!tasks.length) {
      content = 'You have no tasks yet. Create one with `/create_task Buy groceries`.'
    } else {
      const lines = tasks.map((task) => {
        const mark = task.status === 'completed' ? '✓' : '○'
        return `- ${mark} ${task.title}`
      })
      content = `**Your tasks:**\n\n${lines.join('\n')}`
    }
    setMessages((current) => [
      ...current,
      {
        role: 'assistant',
        content,
        kind: 'text',
        memory_ids: [],
        feedback: null,
      },
    ])
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

    const createTaskTitle = parseCreateTask(text)
    if (createTaskTitle) {
      setMessages((m) => [...m, { role: 'user', content: text, kind: 'text' }])
      setSending(true)
      try {
        await sendCreateTask(createTaskTitle)
      } catch (e) {
        setError(e.message || 'Failed to create task')
      } finally {
        setSending(false)
      }
      return
    }

    if (isShowTasksCommand(text)) {
      setMessages((m) => [...m, { role: 'user', content: text, kind: 'text' }])
      setSending(true)
      try {
        await sendShowTasks()
      } catch (e) {
        setError(e.message || 'Failed to load tasks')
      } finally {
        setSending(false)
      }
      return
    }

    const mediaCommand = parseMediaCommand(text)
    if (mediaCommand) {
      if (isMemoryless) {
        setError('Media generation is disabled in MemoryLess sessions.')
        return
      }
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
      await sendChatMessageStream(text)
    } catch (e) {
      setMessages((m) => m.filter((item) => !item.streaming))
      setError(e.message || 'Failed to send message')
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

  const hasText = Boolean(input.trim())

  return (
    <div className="chat-view">
      <div className={`chat-toolbar${sidebarOpen ? '' : ' chat-toolbar--sidebar-closed'}`}>
        <div className="chat-toolbar-left">
          {!sidebarOpen && (
            <div className="collapsed-top-bar">
              <MemoriaLogo size="sm" showName nameClassName="collapsed-brand" />
              <button
                type="button"
                className="collapsed-new-chat"
                onClick={onNewChat}
                disabled={creatingChat}
              >
                {creatingChat ? 'Starting…' : '+ New Chat'}
              </button>
            </div>
          )}

          {mediaModelOverride ? (
            <div
              className="model-select model-select--media"
              style={{ '--media-accent': mediaModelOverride.color }}
              aria-live="polite"
            >
              <span className="model-select-media-label">{mediaModelOverride.modelLabel}</span>
              {sending && mediaGenType ? (
                <span className="spinner spinner-inline" aria-hidden="true" />
              ) : null}
            </div>
          ) : (
            <ModelDropdown
              options={modelOptions}
              value={selectedModel}
              onChange={setSelectedModel}
              disabled={sending}
            />
          )}
        </div>

        <div className="toggle-card-stack">
          <div className="toggle-card">
            <label className={`toggle-card-row${isMemoryless ? ' disabled' : ''}`}>
              <span className="toggle-card-label">Personal Intelligence</span>
              <button
                type="button"
                className={`pi-switch-track ${globalMemoryEnabled ? 'on' : 'off'}`}
                onClick={handlePiToggle}
                disabled={prefsSaving || isMemoryless}
                aria-pressed={globalMemoryEnabled}
                aria-label="Personal Intelligence"
              >
                {globalMemoryEnabled ? 'ON' : 'OFF'}
              </button>
            </label>

            {showMemorylessToggle && (
              <label className="toggle-card-row">
                <span className="toggle-card-label">Memoryless</span>
                <button
                  type="button"
                  className={`pi-switch-track ${isMemoryless ? 'on memoryless-on' : 'off'}`}
                  onClick={handleMemorylessToggle}
                  aria-pressed={isMemoryless}
                  aria-label="Memoryless session"
                >
                  {isMemoryless ? 'ON' : 'OFF'}
                </button>
              </label>
            )}
          </div>

          {infoDialog && (
            <div className="toggle-info-dialog" role="status">
              <p>{infoDialog === 'pi' ? PI_INFO : MEMORYLESS_INFO}</p>
              <button
                type="button"
                className="toggle-info-dismiss"
                onClick={() => setInfoDialog(null)}
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          )}
        </div>
      </div>

      {isMemoryless && !showMemorylessToggle && (
        <div className="memoryless-banner">
          MemoryLess Session – nothing will be remembered.
        </div>
      )}

      <div className="chat-window-wrap">
        <div className="chat-window" ref={windowRef}>
          {loadingHistory && (
            <div className="empty">
              <span className="spinner spinner-inline" aria-hidden="true" />
              Loading conversation…
            </div>
          )}
          {!loadingHistory && messages.length === 0 && !sending && (
            <div className="empty">Ask anything — I&apos;ll remember what matters.</div>
          )}
          {!loadingHistory &&
            messages.map((m, i) => {
              const copyText = getMessageCopyText(m)
              const showCopy =
                (m.role === 'assistant' || m.role === 'user') &&
                m.kind !== 'voice-status' &&
                copyText.trim()
              const showFeedback =
                m.role === 'assistant' &&
                m.memory_ids?.length > 0 &&
                !m.streaming

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
                            <IconThumbsUp />
                          </button>
                          <button
                            type="button"
                            className={`feedback-btn ${m.feedback === 'negative' ? 'selected negative' : ''}`}
                            onClick={() => sendFeedback(i, 'negative')}
                            disabled={Boolean(m.feedback)}
                            title="Unhelpful response"
                            aria-label="Thumbs down"
                          >
                            <IconThumbsDown />
                          </button>
                        </>
                      ) : null}
                    </div>
                  )}
                </div>
              )
            })}
          {sending && !isStreaming && !messages.some((m) => m.kind === 'voice-status') && !mediaGenType && (
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

      <div className="omni-wrap">
        <div className="omni-bar">
          <button type="button" className="omni-plus" aria-label="Attachments" tabIndex={-1}>
            +
          </button>

          <div className="omni-input-area">
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
                placeholder="Ask anything or type / for commands…"
                disabled={sending || !sessionId}
              />
            </div>
          </div>

          <button
            type="button"
            className={`omni-send${hasText ? ' has-text' : ''}`}
            onClick={send}
            disabled={sending || !hasText || !sessionId}
            aria-label="Send"
            title="Send"
          >
            <IconSend />
          </button>
        </div>

        <div className="action-chips">
          {SLASH_COMMANDS.map((cmd) => (
            <button
              key={cmd.prefix}
              type="button"
              className={`action-chip${isMemoryless ? ' disabled' : ''}`}
              style={{ '--chip-color': cmd.color }}
              onClick={() => {
                if (isMemoryless) {
                  setError('Media generation is disabled in MemoryLess sessions.')
                  return
                }
                insertSlashCommand(cmd)
              }}
              disabled={isMemoryless}
            >
              {cmd.prefix}
            </button>
          ))}
        </div>

        {error && <div className="error">{error}</div>}
      </div>
    </div>
  )
}
