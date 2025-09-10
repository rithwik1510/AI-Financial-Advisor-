import { useEffect, useRef, useState } from 'react'
import { AnalyzeResult, apiAsk, apiAnalyze, apiParse, Transaction, ParseResponse } from '../api'
import ToolResultsCardAdv from './ToolResultsCardAdv'

export interface Message { role: 'user' | 'assistant'; content: string; toolResults?: any; toolMissing?: string[]; ts?: number }

export default function Chat({
  analytics,
  onAnalytics,
  messages,
  onMessagesChange,
  streaming = true,
  model,
  threadId,
}: {
  analytics: AnalyzeResult | null
  onAnalytics: (a: AnalyzeResult) => void
  messages?: Message[]
  onMessagesChange?: (m: Message[]) => void
  streaming?: boolean
  model?: string
  threadId?: string
}) {
  const TypingDots = () => (
    <span className="typing-dots" aria-label="Assistant is typing">
      <span className="typing-dot"></span>
      <span className="typing-dot"></span>
      <span className="typing-dot"></span>
    </span>
  )

  const [internalMsgs, setInternalMsgs] = useState<Message[]>(messages || [])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement | null>(null)
  const [editingIdx, setEditingIdx] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState<string>('')
  const [dqScore, setDqScore] = useState<number | null>(null)
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  // PDF mapping wizard removed with local PDF parser deprecation
  const MAX_PDF_MB = 20
  const MAX_TABLE_MB = 8
  const ACCEPTED_EXTS = ['.pdf', '.csv', '.xlsx', '.xls']
  // UI state for drag and drop and scroll helpers
  const [dragOver, setDragOver] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [showJump, setShowJump] = useState(false)

  const msgs = messages ?? internalMsgs
  const setMessages = (m: Message[] | ((prev: Message[]) => Message[])) => {
    const base = messages ?? internalMsgs
    const next = typeof m === 'function' ? (m as any)(base) : m
    setInternalMsgs(next)
    if (onMessagesChange) onMessagesChange(next)
  }

  // Persist drafts per thread
  const draftKey = (threadId ? `draft_${threadId}` : 'draft_default')
  const loadDraft = () => {
    try {
      const v = localStorage.getItem(draftKey)
      if (v !== null) setInput(v)
    } catch {}
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadDraft, [threadId])
  const saveDraft = (val: string) => { try { localStorage.setItem(draftKey, val) } catch {} }

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    // Auto-scroll to bottom when new messages arrive unless user scrolled up
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200
    if (nearBottom) {
      requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight }))
    }
  }, [msgs.length])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowUp' && (document.activeElement as HTMLElement)?.tagName !== 'TEXTAREA') {
        if (!input && msgs.length > 0) {
          // find last user message
          for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === 'user') { setEditingIdx(i); setEditDraft(msgs[i].content); break }
          }
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [input, msgs])

  const ToolResultsCard = ({ results, missing }: { results: any; missing: string[] }) => {
    const mp = results?.mortgage_payment
    const af = results?.affordability
    const hasAny = !!mp || !!af || (missing && missing.length > 0)
    if (!hasAny) return null
    return (
      <div className="border border-zinc-800/70 rounded-xl bg-zinc-900/40">
        <div className="p-3 border-b border-zinc-800/60 text-zinc-300 text-sm">Tool Results</div>
        <div className="p-3 grid gap-3 md:grid-cols-2">
          {mp && (
            <div className="rounded-lg bg-zinc-900/50 border border-zinc-800/60 p-3">
              <div className="font-medium text-zinc-100">Mortgage Payment</div>
              <div className="mt-1 text-sm text-zinc-300">Rate: {(mp.annual_rate*100).toFixed(2)}% • Term: {mp.term_months} mo</div>
              <div className="mt-2 text-sm text-zinc-200">
                <div>PI: ${mp.monthly_pi.toFixed ? mp.monthly_pi.toFixed(2) : mp.monthly_pi}</div>
                <div>Taxes: ${mp.monthly_taxes.toFixed ? mp.monthly_taxes.toFixed(2) : mp.monthly_taxes}</div>
                <div>Insurance: ${mp.monthly_insurance.toFixed ? mp.monthly_insurance.toFixed(2) : mp.monthly_insurance}</div>
                {mp.monthly_hoa ? <div>HOA: ${mp.monthly_hoa.toFixed ? mp.monthly_hoa.toFixed(2) : mp.monthly_hoa}</div> : null}
                {mp.monthly_pmi ? <div>PMI: ${mp.monthly_pmi.toFixed ? mp.monthly_pmi.toFixed(2) : mp.monthly_pmi}</div> : null}
                <div className="mt-1 font-semibold">PITI: ${mp.monthly_piti.toFixed ? mp.monthly_piti.toFixed(2) : mp.monthly_piti}</div>
              </div>
            </div>
          )}
          {af && (
            <div className="rounded-lg bg-zinc-900/50 border border-zinc-800/60 p-3">
              <div className="font-medium text-zinc-100">Affordability</div>
              <div className="mt-1 text-sm text-zinc-300">Binding: {af.binding_constraint} • PITI at max: ${af.piti_at_max.toFixed ? af.piti_at_max.toFixed(2) : af.piti_at_max}</div>
              <div className="mt-2 text-sm text-zinc-200">
                <div>Max Price: ${af.max_price.toLocaleString?.() || af.max_price}</div>
                {af.breakdown && (
                  <div className="mt-1 text-zinc-300">
                    <div>PI: ${af.breakdown.pi.toFixed ? af.breakdown.pi.toFixed(2) : af.breakdown.pi}</div>
                    <div>Taxes: ${af.breakdown.taxes.toFixed ? af.breakdown.taxes.toFixed(2) : af.breakdown.taxes}</div>
                    <div>Ins: ${af.breakdown.insurance.toFixed ? af.breakdown.insurance.toFixed(2) : af.breakdown.insurance}</div>
                    {af.breakdown.hoa ? <div>HOA: ${af.breakdown.hoa.toFixed ? af.breakdown.hoa.toFixed(2) : af.breakdown.hoa}</div> : null}
                    {af.breakdown.pmi ? <div>PMI: ${af.breakdown.pmi.toFixed ? af.breakdown.pmi.toFixed(2) : af.breakdown.pmi}</div> : null}
                  </div>
                )}
              </div>
            </div>
          )}
          {missing && missing.length > 0 && (
            <div className="rounded-lg bg-amber-950/30 border border-amber-800/60 p-3 text-amber-200">
              <div className="font-medium">Missing Inputs</div>
              <div className="text-sm mt-1">Please provide: {missing.join(', ')}</div>
            </div>
          )}
        </div>
      </div>
    )
  }

  const attach = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const arr = Array.from(files)
    const skipped: string[] = []
    const filtered = arr.filter(f => {
      const lower = f.name.toLowerCase()
      const okType = ACCEPTED_EXTS.some(ext => lower.endsWith(ext))
      if (!okType) { skipped.push(`${f.name}: unsupported type`); return false }
      return true
    })
    const pdfs = filtered.filter(f => (f.type === 'application/pdf') || f.name.toLowerCase().endsWith('.pdf'))
    const tables = filtered.filter(f => !pdfs.includes(f))
    // PDFs: with OpenAI provider, direct doc Q&A upload is not supported here
    if (pdfs.length > 0) {
      const tooBig = pdfs.filter(f => f.size > MAX_PDF_MB * 1024 * 1024)
      const ok = pdfs.filter(f => !tooBig.includes(f))
      if (tooBig.length > 0) skipped.push(...tooBig.map(f => `${f.name}: exceeds ${MAX_PDF_MB}MB limit`))
      if (ok.length > 0) {
        setMessages(m => [...m, { role: 'assistant', content: `PDF Q&A is not available with the current LLM provider. Please attach CSV/XLSX exports for accurate analytics.`, ts: Date.now() }])
      }
    }
    if (tables.length === 0) { if (skipped.length > 0) setMessages(m => [...m, { role: 'assistant', content: `Skipped: ${skipped.join('; ')}`, ts: Date.now() }]); return }
    setBusy(true)
    try {
      const tooBigTables = tables.filter(f => f.size > MAX_TABLE_MB * 1024 * 1024)
      const okTables = tables.filter(f => !tooBigTables.includes(f))
      if (tooBigTables.length > 0) skipped.push(...tooBigTables.map(f => `${f.name}: exceeds ${MAX_TABLE_MB}MB limit`))
      const parsed: ParseResponse = await apiParse(okTables)
      const tx: Transaction[] = parsed.transactions
      if (tx.length > 0) {
        const analyzed = await apiAnalyze(tx)
        onAnalytics(analyzed)
        setDqScore(typeof parsed.dq_score === 'number' ? parsed.dq_score : null)
        const note = parsed && parsed.notes ? `\n\n${parsed.notes}` : ''
        const dqMsg = typeof parsed.dq_score === 'number' ? `\nData Quality: ${parsed.dq_score}/100` : ''
        const warnMsg = parsed.warnings && parsed.warnings.length > 0 ? `\nWarnings: ${parsed.warnings.slice(0,3).join('; ')}` : ''
        const skipMsg = skipped.length > 0 ? `\nSkipped: ${skipped.join('; ')}` : ''
        setMessages(m => [...m, { role: 'assistant', content: `Processed ${tx.length} transactions from ${parsed.files.length} file(s). You can now ask questions.${dqMsg}${warnMsg}${skipMsg}${note}`, ts: Date.now() }])
      } else {
        const skipMsg = skipped.length > 0 ? ` Skipped: ${skipped.join('; ')}` : ''
        setMessages(m => [...m, { role: 'assistant', content: `No transactions were detected from the attached CSV/XLSX files.${skipMsg}`, ts: Date.now() }])
      }
    } catch (err: any) {
      let details = ''
      try {
        if (err?.response) {
          const st = err.response.status
          const data = err.response.data
          const msg = (data && (data.detail || data.message)) || (typeof data === 'string' ? data : '')
          details = ` (status ${st}${msg ? `: ${msg}` : ''})`
        } else if (err?.message) {
          details = ` (${err.message})`
        }
      } catch {}
      setMessages(m => [...m, { role: 'assistant', content: `Failed to process files. Ensure they are valid CSV/XLSX.${details}`, ts: Date.now() }])
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const resendWithText = async (idx: number, q: string) => {
    if (analytics && dqScore !== null && dqScore < 70) {
      setMessages(m => [...m, { role: 'assistant', content: `Your data quality score is ${dqScore}/100. For more reliable analytics, please try CSV/XLSX exports from your bank.`, ts: Date.now() }])
      // wizard removed
    }
    const question = (q || '').trim(); if (!question) return
    setBusy(true)
    try {
      if (streaming) {
        setMessages(m => {
          const base = m.slice(0, idx + 1)
          return [...base, { role: 'assistant', content: '', ts: Date.now() }]
        })
        const resp = await fetch('/api/ask/stream', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ analytics: analytics ?? null, question, model })
        })
        if (!resp.ok || !resp.body) throw new Error('Stream failed')
        const reader = resp.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let ended = false
        while (true) {
          const { value, done } = await reader.read(); if (done) break
          buffer += decoder.decode(value, { stream: true })
          let cut
          while ((cut = buffer.indexOf('\n\n')) !== -1) {
            const raw = buffer.slice(0, cut).trim(); buffer = buffer.slice(cut + 2)
            if (!raw.startsWith('data:')) continue
            const jsonStr = raw.slice(5).trim()
            try {
              const evt = JSON.parse(jsonStr)
              if (evt.type === 'tools') {
                setMessages(m => [...m, { role: 'assistant', content: '', toolResults: evt.results || {}, toolMissing: evt.missing || [], ts: Date.now() }])
              } else if (evt.type === 'token') {
                setMessages(m => {
                  const copy = m.slice(); const last = copy[copy.length - 1]
                  if (last && last.role === 'assistant') last.content += evt.content || ''
                  return copy
                })
              } else if (evt.type === 'message') {
                setMessages(m => [...m, { role: 'assistant', content: evt.content || '', ts: Date.now() }])
              } else if (evt.type === 'done') {
                ended = true
              }
            } catch {}
          }
          if (ended) break
        }
      } else {
        const { answer } = await apiAsk(analytics ?? null, question, model)
        setMessages(m => {
          const base = m.slice(0, idx + 1)
          return [...base, { role: 'assistant', content: answer, ts: Date.now() }]
        })
      }
    } catch {
      setMessages(m => [...m, { role: 'assistant', content: 'Could not reach the LLM provider. Check your API key (e.g., OPENAI_API_KEY) and try again.', ts: Date.now() }])
    } finally {
      setBusy(false)
    }
  }

  const startEdit = (idx: number) => { setEditingIdx(idx); setEditDraft(msgs[idx]?.content || '') }
  const cancelEdit = () => { setEditingIdx(null); setEditDraft('') }
  const saveAndResend = async (idx: number) => {
    const newQ = (editDraft || '').trim(); if (!newQ) return
    setMessages(m => {
      const copy = m.slice(0, idx + 1)
      if (copy[idx]) copy[idx] = { role: 'user', content: newQ, ts: Date.now() }
      return copy
    })
    setEditingIdx(null); setEditDraft('')
    await resendWithText(idx, newQ)
  }
  const quickResend = async (idx: number) => {
    const q = msgs[idx]?.content || ''
    await resendWithText(idx, q)
  }

  const send = async () => {
    if (!input.trim()) return
    const q = input.trim()
    setMessages(m => [...m, { role: 'user', content: q, ts: Date.now() }])
    setInput(''); saveDraft('')
    setBusy(true)
    try {
      if (attachedFiles.length > 0) {
        setAttachedFiles([])
        setMessages(m => [...m, { role: 'assistant', content: `PDF Q&A is not available with the current LLM provider. Please attach CSV/XLSX exports for accurate analytics.`, ts: Date.now() }])
      } else if (streaming) {
        setMessages(m => [...m, { role: 'assistant', content: '', ts: Date.now() }])
        const resp = await fetch('/api/ask/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ analytics: analytics ?? null, question: q, model })
        })
        if (!resp.ok || !resp.body) throw new Error('Stream failed')
        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let ended = false
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          let idx
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const raw = buffer.slice(0, idx).trim()
            buffer = buffer.slice(idx + 2)
            if (!raw.startsWith('data:')) continue
            const jsonStr = raw.slice(5).trim()
            try {
              const evt = JSON.parse(jsonStr)
              if (evt.type === 'tools') {
                setMessages(m => [...m, { role: 'assistant', content: '', toolResults: evt.results || {}, toolMissing: evt.missing || [], ts: Date.now() }])
              } else if (evt.type === 'token') {
                setMessages(m => {
                  const copy = m.slice()
                  const last = copy[copy.length - 1]
                  if (last && last.role === 'assistant') last.content += evt.content || ''
                  return copy
                })
              } else if (evt.type === 'message') {
                setMessages(m => [...m, { role: 'assistant', content: evt.content || '', ts: Date.now() }])
              } else if (evt.type === 'error') {
                setMessages(m => [...m, { role: 'assistant', content: evt.message || 'Error during streaming', ts: Date.now() }])
              } else if (evt.type === 'done') {
                ended = true
              }
            } catch {}
          }
          if (ended) break
        }
      } else {
        const { answer } = await apiAsk(analytics ?? null, q, model)
        setMessages(m => [...m, { role: 'assistant', content: answer, ts: Date.now() }])
      }
    } catch {
      try {
        if (attachedFiles.length > 0) {
          setAttachedFiles([])
          setMessages(m => [...m, { role: 'assistant', content: `PDF Q&A is not available with the current LLM provider. Please attach CSV/XLSX exports for accurate analytics.`, ts: Date.now() }])
        } else {
          const { answer } = await apiAsk(analytics ?? null, q, model)
        setMessages(m => {
          const copy = m.slice()
          const last = copy[copy.length - 1]
          if (last && last.role === 'assistant' && last.content === '') last.content = answer
          else copy.push({ role: 'assistant', content: answer, ts: Date.now() })
          return copy
        })
        }
      } catch {
        setMessages(m => [...m, { role: 'assistant', content: 'Could not reach the LLM provider. Check your API key (e.g., OPENAI_API_KEY) and try again.', ts: Date.now() }])
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* MappingWizardModal removed */}
      {analytics && dqScore !== null && (
        <div className={`mx-auto w-full max-w-3xl mt-3 px-3`}>
          <div className={`rounded-xl border px-4 py-2 text-sm ${dqScore < 70 ? 'border-red-800/60 bg-red-950/30 text-red-200' : dqScore < 90 ? 'border-amber-800/60 bg-amber-950/30 text-amber-200' : 'border-emerald-800/60 bg-emerald-950/30 text-emerald-200'}`}>
            Data Quality: {dqScore}/100. {dqScore < 70 ? 'Consider using CSV/XLSX exports for more reliable analytics.' : 'Looks good.'}
          </div>
        </div>
      )}
      {msgs.length > 0 ? (
        <div className="flex-1 overflow-y-auto py-6" ref={el=>{scrollRef.current=el}} onScroll={(e)=>{
          const el = e.currentTarget
          const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
          setShowJump(!nearBottom)
        }}>
          <div className="space-y-6">
            {msgs.map((m, idx) => (
              <div key={idx} className="px-2 animate-fade-in">
                {m.role === 'user' ? (
                  <div className="mx-auto max-w-3xl text-right">
                    {editingIdx === idx ? (
                      <div className="inline-block bg-gradient-to-br from-purple-600 to-fuchsia-600 text-white px-4 py-3 rounded-2xl shadow-md shadow-purple-900/30 w-full max-w-2xl text-left">
                        <textarea className="w-full bg-transparent outline-none resize-vertical" rows={3} value={editDraft} onChange={e => setEditDraft(e.target.value)} />
                        <div className="mt-2 flex gap-2 justify-end text-xs">
                          <button onClick={() => saveAndResend(idx)} className="px-3 py-1 rounded bg-white/20 hover:bg-white/30">Save & Resend</button>
                          <button onClick={cancelEdit} className="px-3 py-1 rounded bg-white/10 hover:bg-white/20">Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div className="inline-block bg-gradient-to-br from-purple-600 to-fuchsia-600 text-white px-4 py-2 rounded-2xl shadow-md shadow-purple-900/30 transition-transform">
                        {m.content}
                        <div className="mt-1 text-[11px] opacity-80 select-none text-right">
                          <button onClick={() => startEdit(idx)} className="underline decoration-white/30 hover:decoration-white mr-3">Edit</button>
                          <button onClick={() => quickResend(idx)} className="underline decoration-white/30 hover:decoration-white">Resend</button>
                        </div>
                        <div className="mt-1 text-[11px] opacity-80 select-none text-right">{m.ts ? new Date(m.ts).toLocaleTimeString() : ''}</div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="mx-auto max-w-3xl">
                    {m.toolResults && (
                      <div className="px-2 py-2">
                        <ToolResultsCardAdv
                          index={idx}
                          results={m.toolResults}
                          missing={m.toolMissing || []}
                          analytics={analytics}
                          onUpdate={(i, newRes) => setMessages(prev => { const copy = prev.slice(); const msg = copy[i]; if (msg) msg.toolResults = { ...msg.toolResults, ...newRes }; return copy })}
                        />
                      </div>
                    )}
                    <div className="group/message relative">
                      <div className="whitespace-pre-wrap leading-relaxed text-zinc-100 px-2 py-2">
                        {m.content && m.content.length > 0 ? m.content : (busy && m.role==='assistant' && idx === msgs.length - 1 ? <TypingDots /> : null)}
                      </div>
                      <div className="px-2 pb-2 text-xs text-zinc-500">{m.ts ? new Date(m.ts).toLocaleTimeString() : ''}</div>
                      <div className="absolute right-2 top-1 opacity-0 group-hover/message:opacity-100 transition text-xs flex gap-2">
                        <button className="px-2 py-1 rounded bg-zinc-900/70 border border-zinc-800 hover:bg-zinc-800 text-zinc-200" onClick={() => { try { navigator.clipboard.writeText(m.content || '') } catch {} }}>Copy</button>
                        <button className="px-2 py-1 rounded bg-zinc-900/70 border border-zinc-800 hover:bg-zinc-800 text-zinc-200" onClick={() => setInput(prev => (prev ? prev + "\n> " + (m.content||'') : "> " + (m.content||'')))}>Quote</button>
                        {(() => {
                          // regenerate using the previous user message
                          let prevUserIdx = -1
                          for (let j = idx - 1; j >= 0; j--) { if (msgs[j]?.role === 'user') { prevUserIdx = j; break } }
                          return prevUserIdx >= 0 ? (
                            <button className="px-2 py-1 rounded bg-gradient-to-br from-purple-700 to-fuchsia-700 hover:from-purple-600 hover:to-fuchsia-600 text-white"
                              onClick={() => resendWithText(prevUserIdx, msgs[prevUserIdx].content)}>
                              Regenerate
                            </button>
                          ) : null
                        })()}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {busy && (msgs.length === 0 || msgs[msgs.length-1]?.role === 'user') && (
              <div className="px-2 animate-fade-in">
                <div className="mx-auto max-w-3xl">
                  <div className="whitespace-pre-wrap leading-relaxed text-zinc-100 px-2 py-2">
                    <TypingDots />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 pt-16">
          <div className="text-center px-4">
            <h2 className="text-2xl font-semibold text-zinc-200">What can I help you with today?</h2>
            <p className="mt-3 text-sm text-zinc-400">Attach statements below. For charts and monthly breakdowns, CSV/XLSX exports give the most accurate results. PDF Q&A is not available in this build.</p>
            <div className="mt-4 flex flex-wrap gap-2 justify-center text-sm">
              {[
                'Can I afford a $400k home at 6.5% with $20k down?',
                'Help me cut $200/month from discretionary spend.',
                'What are my top 5 recurring expenses?',
                'How is my savings rate trending over the last 6 months?'
              ].map((s, i) => (
                <button key={i} onClick={() => setInput(s)} className="px-3 py-1.5 rounded-full border border-zinc-800/60 hover:border-zinc-700 bg-zinc-900/30 text-zinc-200">{s}</button>
              ))}
            </div>
          </div>
          <div className="mt-8 px-4">
            <div className="max-w-3xl mx-auto relative group">
              <input
                className="w-full rounded-full bg-zinc-950/70 backdrop-blur border border-zinc-800 px-5 pr-28 py-4 text-zinc-100 placeholder:text-zinc-500 shadow-inner focus:outline-none focus:ring-2 focus:ring-purple-600 transition-all hover:shadow-[0_0_30px_-12px_rgba(168,85,247,0.45)]"
                placeholder="Ask a question about your finances..."
                value={input}
                onChange={e => { setInput(e.target.value); saveDraft(e.target.value) }}
                onKeyDown={e => e.key==='Enter' && send()}
                disabled={busy}
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button
                  onClick={() => fileRef.current?.click()}
                  disabled={busy}
                  className="p-2 rounded-full text-zinc-300 hover:text-fuchsia-400 transition transform hover:scale-110 hover:shadow-[0_0_20px_rgba(216,180,254,0.35)]"
                  aria-label="Attach files"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 12.5L12.5 21C10 23.5 6 23.5 3.5 21C1 18.5 1 14.5 3.5 12L12 3.5C13.5 2 16 2 17.5 3.5C19 5 19 7.5 17.5 9L9 17.5C8 18.5 6.5 18.5 5.5 17.5C4.5 16.5 4.5 15 5.5 14L13 6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
                <button
                  onClick={send}
                  disabled={busy}
                  className="p-2 rounded-full text-white bg-gradient-to-br from-purple-600 to-fuchsia-600 hover:from-purple-500 hover:to-fuchsia-500 transition transform hover:scale-110 shadow-lg shadow-purple-900/30"
                  aria-label="Send"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 12L20 4L12 20L11 13L4 12Z" fill="currentColor"/>
                  </svg>
                </button>
              </div>
              <input ref={fileRef} type="file" multiple className="hidden" accept=".pdf,.csv,.xlsx,.xls" onChange={(e) => attach(e.target.files)} />
            </div>
          </div>
        </div>
      )}

      {showJump && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2">
          <button onClick={()=>{ const el = scrollRef.current; if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }) }}
                  className="px-3 py-1.5 rounded-full bg-gradient-to-br from-purple-700 to-fuchsia-700 text-white shadow-lg shadow-purple-900/30">
            Jump to latest
          </button>
        </div>
      )}

      {msgs.length > 0 && (
        <div className={`mt-2 flex gap-2 items-center max-w-3xl mx-auto w-full sticky bottom-4 px-2 composer ${dragOver ? 'ring-2 ring-fuchsia-600/50 rounded-2xl' : ''}`}
             onDragOver={(e)=>{e.preventDefault(); setDragOver(true)}} onDragEnter={(e)=>{e.preventDefault(); setDragOver(true)}} onDragLeave={()=>setDragOver(false)} onDrop={(e)=>{e.preventDefault(); setDragOver(false); attach(e.dataTransfer.files)}}>
          <input ref={fileRef} type="file" multiple className="hidden" accept=".pdf,.csv,.xlsx,.xls" onChange={(e) => attach(e.target.files)} />
          <button className="px-3 py-2 rounded-2xl bg-gradient-to-br from-purple-700 to-fuchsia-700 hover:from-purple-600 hover:to-fuchsia-600 text-white shadow-lg shadow-purple-900/30 disabled:opacity-50 transition-all" onClick={() => fileRef.current?.click()} disabled={busy}>Attach</button>
          {attachedFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 max-w-[55%]">
              {attachedFiles.map((f, i) => (
                <div key={i} className="flex items-center gap-2 px-2 py-1 rounded-xl border border-zinc-800 bg-zinc-900 text-xs text-zinc-200">
                  <span className="text-fuchsia-300">PDF</span>
                  <span className="truncate max-w-[160px]" title={f.name}>{f.name}</span>
                  <span className="text-zinc-500">{Math.round(f.size/1024/1024)}MB</span>
                  <button className="text-zinc-400 hover:text-zinc-200" onClick={()=> setAttachedFiles(prev => prev.filter((_, idx)=>idx!==i))}>×</button>
                </div>
              ))}
            </div>
          )}
          <input className="flex-1 border border-zinc-800 bg-zinc-950/80 backdrop-blur text-zinc-100 rounded-2xl px-4 py-3 disabled:bg-zinc-800 placeholder:text-zinc-500 shadow-inner focus:outline-none focus:ring-2 focus:ring-purple-600 transition-all" placeholder="Message your coach..." value={input} onChange={e => { setInput(e.target.value); saveDraft(e.target.value) }} onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send() } }} disabled={busy} />
          <button className="bg-gradient-to-br from-purple-600 to-fuchsia-600 hover:from-purple-500 hover:to-fuchsia-500 text-white px-5 py-3 rounded-2xl disabled:opacity-50 shadow-lg shadow-purple-900/30 transition-all" onClick={send} disabled={busy}>{busy ? 'Sending...' : 'Send'}</button>
        </div>
      )}
    </div>
  )
}
