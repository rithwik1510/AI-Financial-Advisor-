import { useEffect, useMemo, useState } from 'react'

export interface CommandItem {
  id: string
  title: string
  hint?: string
  action: () => void
}

export default function CommandPalette({ open, onClose, commands }: { open: boolean; onClose: () => void; commands: CommandItem[] }) {
  const [query, setQuery] = useState('')
  const [idx, setIdx] = useState(0)
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim()
    return commands.filter(c => !q || c.title.toLowerCase().includes(q) || (c.hint || '').toLowerCase().includes(q))
  }, [commands, query])

  useEffect(() => { if (open) { setQuery(''); setIdx(0) } }, [open])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!open) return
      if (e.key === 'Escape') { e.preventDefault(); onClose(); return }
      if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(i => Math.min(i+1, Math.max(0, filtered.length-1))); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setIdx(i => Math.max(i-1, 0)); return }
      if (e.key === 'Enter') { e.preventDefault(); const item = filtered[idx]; if (item) { onClose(); setTimeout(()=>item.action(), 0) } }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, filtered, idx, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative mx-auto mt-24 w-full max-w-xl rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl">
        <div className="p-3 border-b border-zinc-800">
          <input autoFocus value={query} onChange={e=>setQuery(e.target.value)} placeholder="Type a command..."
                 className="w-full bg-zinc-950 text-zinc-100 placeholder:text-zinc-500 outline-none" />
        </div>
        <div className="max-h-72 overflow-auto">
          {filtered.length === 0 ? (
            <div className="px-4 py-6 text-sm text-zinc-400">No matches</div>
          ) : filtered.map((c, i) => (
            <button key={c.id} onClick={()=>{ onClose(); c.action() }}
                    className={`w-full text-left px-4 py-3 text-sm flex items-center justify-between ${i===idx ? 'bg-zinc-900' : 'hover:bg-zinc-900/60'}`}>
              <span className="text-zinc-100">{c.title}</span>
              {c.hint && <span className="text-zinc-500 text-xs">{c.hint}</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

