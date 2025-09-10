import { useEffect, useMemo, useState } from 'react'
import Chat, { Message } from './components/Chat'
import { AnalyzeResult } from './api'
import Sidebar, { ChatThread } from './components/Sidebar'
import CommandPalette, { CommandItem } from './components/CommandPalette'
import { apiLlmStatus } from './api'
import SettingsModal, { Settings } from './components/SettingsModal'

export default function App() {
  const [analytics, setAnalytics] = useState<AnalyzeResult | null>(null)
  const [threads, setThreads] = useState<ChatThread[]>(() => {
    try { return JSON.parse(localStorage.getItem('threads') || '[]') } catch { return [] }
  })
  const [activeId, setActiveId] = useState<string | null>(() => {
    try { return localStorage.getItem('active_thread') } catch { return null }
  })
  const [messagesMap, setMessagesMap] = useState<Record<string, Message[]>>(() => {
    try { return JSON.parse(localStorage.getItem('messages_map') || '{}') } catch { return {} }
  })
  const [settings, setSettings] = useState<Settings>(() => {
    try {
      const s = JSON.parse(localStorage.getItem('settings') || '')
      return { streamResponses: true, saveHistory: true, reduceMotion: false, textSize: 'md', llmModel: 'gpt-4o-mini', ...(s || {}) }
    } catch {
      return { streamResponses: true, saveHistory: true, reduceMotion: false, textSize: 'md', llmModel: 'gpt-4o-mini' }
    }
  })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)

  const ensureActive = () => {
    if (activeId && threads.find(t => t.id === activeId)) return
    const id = Date.now().toString()
    const now = Date.now()
    const newThread: ChatThread = { id, title: 'New Chat', createdAt: now, updatedAt: now, pinned: false }
    setThreads(t => { const nt=[newThread, ...t]; if (settings.saveHistory) localStorage.setItem('threads', JSON.stringify(nt)); return nt })
    setActiveId(id); if (settings.saveHistory) localStorage.setItem('active_thread', id)
    setMessagesMap(m => { const nm={...m, [id]: [] as any}; if (settings.saveHistory) localStorage.setItem('messages_map', JSON.stringify(nm)); return nm })
  }

  // Initialize a default thread if none
  useEffect(() => {
    if (!activeId || !threads.find(t => t.id === activeId)) {
      ensureActive()
    }
  }, [activeId, threads])

  const activeMessages = messagesMap[activeId || ''] || []

  const updateMessages = (msgs: {role:'user'|'assistant';content:string}[]) => {
    // Ensure an active thread exists; if not, create one synchronously
    if (!activeId) {
      const id = Date.now().toString()
      const newThread: ChatThread = { id, title: 'New Chat', createdAt: Date.now() }
      setThreads(t => { const nt=[newThread, ...t]; if (settings.saveHistory) localStorage.setItem('threads', JSON.stringify(nt)); return nt })
      setActiveId(id); if (settings.saveHistory) localStorage.setItem('active_thread', id)
      setMessagesMap(m => { const nm={...m, [id]: msgs as any}; if (settings.saveHistory) localStorage.setItem('messages_map', JSON.stringify(nm)); return nm })
      return
    }
    setMessagesMap(m => { const nm={...m, [activeId]: msgs}; if(settings.saveHistory){ localStorage.setItem('messages_map', JSON.stringify(nm))}; return nm })
    // Update thread last activity time
    setThreads(ts => { const now=Date.now(); const nt = ts.map(t => t.id===activeId ? { ...t, updatedAt: now } : t); if (settings.saveHistory) localStorage.setItem('threads', JSON.stringify(nt)); return nt })
    // Derive title from first user message
    if (msgs.length > 0 && threads.find(t=>t.id===activeId)?.title === 'New Chat') {
      const first = msgs.find(m => m.role==='user')
      if (first) {
        const title = first.content.slice(0,40) + (first.content.length>40?'…':'')
        setThreads(ts => { const nt = ts.map(t => t.id===activeId ? {...t, title} : t); localStorage.setItem('threads', JSON.stringify(nt)); return nt })
      }
    }
  }

  const onNewChat = () => {
    const id = Date.now().toString()
    const now = Date.now()
    const newThread: ChatThread = { id, title: 'New Chat', createdAt: now, updatedAt: now, pinned: false }
    const nt = [newThread, ...threads]
    setThreads(nt); localStorage.setItem('threads', JSON.stringify(nt))
    setActiveId(id); localStorage.setItem('active_thread', id)
    const nm = { ...messagesMap, [id]: [] as any }
    setMessagesMap(nm); localStorage.setItem('messages_map', JSON.stringify(nm))
  }

  const onSelectThread = (id: string) => {
    setActiveId(id); localStorage.setItem('active_thread', id)
  }

  const openSettings = () => setSettingsOpen(true)
  const closeSettings = () => setSettingsOpen(false)
  const changeSettings = (s: Settings) => { setSettings(s); localStorage.setItem('settings', JSON.stringify(s)) }
  const clearAll = () => {
    localStorage.removeItem('threads'); localStorage.removeItem('active_thread'); localStorage.removeItem('messages_map'); localStorage.removeItem('settings')
    setThreads([]); setMessagesMap({}); setActiveId(null)
  }

  // Command palette
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toLowerCase().includes('mac')
      if ((isMac && e.metaKey && e.key.toLowerCase()==='k') || (!isMac && e.ctrlKey && e.key.toLowerCase()==='k')) {
        e.preventDefault(); setPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const runRenameCurrent = () => {
    if (!activeId) return
    const current = threads.find(t => t.id===activeId)
    const val = window.prompt('Rename chat', current?.title || 'New Chat')
    if (val!=null) renameThread(activeId, val.trim())
  }
  const runDeleteCurrent = () => { if (activeId) deleteThread(activeId) }
  const runCheckLlm = async () => { try { const s = await apiLlmStatus(); alert(s.ok ? `LLM OK — ${s.provider} (${s.model})` : `LLM Error — ${s.error||'unknown'}`) } catch (e:any) { alert('Status failed: ' + (e?.message||e)) } }
  const runToggleModel = () => {
    const next = settings.llmModel === 'gpt-4o-mini' ? 'gpt-4o' : 'gpt-4o-mini'
    changeSettings({ ...settings, llmModel: next })
  }
  const commands: CommandItem[] = [
    { id: 'new', title: 'New chat', hint: 'N', action: onNewChat },
    { id: 'rename', title: 'Rename current chat', action: runRenameCurrent },
    { id: 'delete', title: 'Delete current chat', action: runDeleteCurrent },
    { id: 'llm', title: 'Check LLM status', action: runCheckLlm },
    { id: 'model', title: `Toggle model (${settings.llmModel})`, action: runToggleModel },
    { id: 'settings', title: 'Open Settings', action: openSettings },
  ]

  const deleteThread = (id: string) => {
    let nextActive: string | null = activeId
    setThreads(ts => {
      const nt = ts.filter(t => t.id !== id)
      // decide next active based on new list
      if (activeId === id) {
        nextActive = nt.length > 0 ? nt[0].id : null
      }
      localStorage.setItem('threads', JSON.stringify(nt))
      return nt
    })
    setMessagesMap(m => {
      const nm = { ...m }
      delete nm[id]
      localStorage.setItem('messages_map', JSON.stringify(nm))
      return nm
    })
    if (activeId === id) {
      setActiveId(nextActive)
      if (nextActive) localStorage.setItem('active_thread', nextActive)
      else localStorage.removeItem('active_thread')
    }
  }

  const renameThread = (id: string, title: string) => {
    setThreads(ts => { const nt = ts.map(t => t.id===id ? { ...t, title: title || 'New Chat' } : t); localStorage.setItem('threads', JSON.stringify(nt)); return nt })
  }

  const togglePinThread = (id: string) => {
    setThreads(ts => { const nt = ts.map(t => t.id===id ? { ...t, pinned: !t.pinned } : t); localStorage.setItem('threads', JSON.stringify(nt)); return nt })
  }

  return (
    <div className={`app-root ${settings.textSize==='sm' ? 'text-size-sm' : settings.textSize==='lg' ? 'text-size-lg' : 'text-size-md'} ${settings.reduceMotion ? 'reduced-motion' : ''} min-h-screen relative text-zinc-100 flex bg-gradient-to-br from-[#0b0318] via-black to-black`}>
      <div className="pointer-events-none absolute inset-0 bg-animated-gradient opacity-40"></div>
      <aside className="w-64 border-r border-zinc-800/60 bg-zinc-900/30 backdrop-blur-md flex flex-col">
        <Sidebar
          threads={threads}
          activeId={activeId}
          onNewChat={onNewChat}
          onSelect={onSelectThread}
          onOpenSettings={openSettings}
          onDelete={deleteThread}
          onRename={renameThread}
          onTogglePin={togglePinThread}
        />
      </aside>
      <main className="flex-1 p-4">
        <div className="mx-auto max-w-5xl h-full">
          <Chat analytics={analytics} onAnalytics={setAnalytics} messages={activeMessages} onMessagesChange={updateMessages} streaming={settings.streamResponses} model={settings.llmModel} threadId={activeId || 'default'} />
        </div>
      </main>
      <SettingsModal open={settingsOpen} settings={settings} onChange={changeSettings} onClose={closeSettings} onClearAll={clearAll} />
      <CommandPalette open={paletteOpen} onClose={()=>setPaletteOpen(false)} commands={commands} />
    </div>
  )
}
