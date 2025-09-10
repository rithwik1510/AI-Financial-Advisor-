import { useState } from 'react'

export interface ChatThread {
  id: string
  title: string
  createdAt: number
  updatedAt?: number
  pinned?: boolean
}

export default function Sidebar({
  threads,
  activeId,
  onNewChat,
  onSelect,
  onOpenSettings,
  onDelete,
  onRename,
  onTogglePin,
}: {
  threads: ChatThread[]
  activeId: string | null
  onNewChat: () => void
  onSelect: (id: string) => void
  onOpenSettings: () => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void
  onTogglePin: (id: string) => void
}) {
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const sorted = [...threads].sort((a, b) => {
    const ap = a.pinned ? 1 : 0
    const bp = b.pinned ? 1 : 0
    if (ap !== bp) return bp - ap // pinned first
    // then by updatedAt desc, fallback createdAt desc
    const au = a.updatedAt || a.createdAt
    const bu = b.updatedAt || b.createdAt
    return bu - au
  })

  return (
    <div className="h-full flex flex-col">
      <div className="p-3 border-b border-zinc-800/60 bg-zinc-900/20 backdrop-blur-sm">
        <button onClick={onNewChat} className="w-full bg-gradient-to-r from-purple-600 to-fuchsia-600 hover:from-purple-500 hover:to-fuchsia-500 text-white py-2 rounded-xl shadow-md shadow-purple-900/30 transition">+ New Chat</button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        <div className="text-xs uppercase text-zinc-400 px-2">Recent</div>
        {sorted.length === 0 && (
          <div className="px-2 py-2 text-zinc-400/80 text-sm">No chats yet</div>
        )}
        {sorted.map(t => (
          <div key={t.id} className={`w-full px-2 py-1 group`}> 
            <div className={`flex items-center gap-2 rounded-xl border ${activeId===t.id ? 'bg-zinc-900/60 border-zinc-700' : 'border-zinc-900/60 hover:bg-zinc-900/40'} transition`}
                 onClick={() => onSelect(t.id)} role="button" tabIndex={0}>
              <div className="flex-1 px-2 py-2">
                {editId === t.id ? (
                  <input autoFocus value={draft} onChange={e=>setDraft(e.target.value)}
                    onClick={e=>e.stopPropagation()}
                    onKeyDown={e=>{ if(e.key==='Enter'){ onRename(t.id, draft.trim() || 'New Chat'); setEditId(null); setDraft('') } if(e.key==='Escape'){ setEditId(null); setDraft('') } }}
                    onBlur={()=>{ onRename(t.id, draft.trim() || 'New Chat'); setEditId(null); setDraft('') }}
                    className="w-full bg-transparent outline-none text-sm text-zinc-100"/>
                ) : (
                  <div className="truncate text-sm text-zinc-100 flex items-center gap-1">
                    {t.pinned && (
                      <span title="Pinned" aria-hidden className="text-fuchsia-300">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                          <path d="M14 2c.6 0 1 .4 1 1v3.3l3 2.7c.3.3.4.8.1 1.2l-2.4 3.2c-.2.3-.2.7 0 1l1.3 1.3c.4.4.1 1.1-.5 1.1H13l-4.6 5.3c-.3.4-1 .1-.9-.4l1.2-4.9H6c-.6 0-.9-.7-.5-1.1l1.3-1.3c.3-.3.3-.7 0-1L4.4 10c-.3-.4-.2-.9.1-1.2L7.5 6.3V3c0-.6.4-1 1-1h5.5Z" />
                        </svg>
                      </span>
                    )}
                    <span>{t.title || 'New Chat'}</span>
                  </div>
                )}
              </div>
              <button title="Thread menu" aria-label="Thread menu" onClick={(e)=>{ e.stopPropagation(); setMenuOpenId(menuOpenId===t.id?null:t.id); setConfirmDeleteId(null) }}
                className="opacity-0 group-hover:opacity-100 transition px-2 py-2 text-zinc-300 hover:text-zinc-100 active:scale-95">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 13.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm7 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm-14 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" fill="currentColor"/></svg>
              </button>
            </div>
            {menuOpenId === t.id && (
              <div className="ml-2 mt-1 bg-zinc-950 border border-zinc-800 rounded-lg shadow-xl w-40 overflow-hidden">
                <button className="w-full text-left px-3 py-2 hover:bg-zinc-900 text-sm" onClick={()=>{ setEditId(t.id); setDraft(t.title); setMenuOpenId(null) }}>Rename</button>
                <button className="w-full text-left px-3 py-2 hover:bg-zinc-900 text-sm" onClick={()=>{ onTogglePin(t.id); setMenuOpenId(null) }}>{t.pinned? 'Unpin':'Pin'}</button>
                <button className="w-full text-left px-3 py-2 hover:bg-zinc-900 text-sm text-red-300" onClick={()=>{ setConfirmDeleteId(t.id); setMenuOpenId(null) }}>Delete</button>
              </div>
            )}
            {confirmDeleteId === t.id && (
              <div className="ml-2 mt-2 p-2 rounded-lg border border-red-800/60 bg-red-950/30 text-red-100 text-sm flex items-center gap-2">
                <span>Delete this chat? This cannot be undone.</span>
                <button className="px-2 py-1 rounded bg-red-700 hover:bg-red-600" onClick={()=>{ onDelete(t.id); setConfirmDeleteId(null) }}>Delete</button>
                <button className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700" onClick={()=>setConfirmDeleteId(null)}>Cancel</button>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-zinc-800/60 bg-zinc-900/20 backdrop-blur-sm flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600 to-fuchsia-600 text-white flex items-center justify-center">U</div>
          <div>
            <div className="font-medium">You</div>
            <div className="text-zinc-400 text-xs">Local</div>
          </div>
        </div>
        <button onClick={onOpenSettings} className="px-3 py-1.5 rounded-xl bg-zinc-900/50 border border-zinc-800/60 hover:bg-zinc-800/50 transition">Settings</button>
      </div>
    </div>
  )
}
