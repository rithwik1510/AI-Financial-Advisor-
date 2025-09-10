export interface Settings {
  streamResponses: boolean
  saveHistory: boolean
  reduceMotion: boolean
  textSize: 'sm' | 'md' | 'lg'
  llmModel?: string // e.g., 'gemini-1.5-pro' | 'gemini-1.5-flash'
}

import { useState } from 'react'
import { apiLlmStatus } from '../api'

export default function SettingsModal({
  open,
  settings,
  onChange,
  onClose,
  onClearAll,
}: {
  open: boolean
  settings: Settings
  onChange: (s: Settings) => void
  onClose: () => void
  onClearAll: () => void
}) {
  const [llmStatus, setLlmStatus] = useState<string>('')
  const [checking, setChecking] = useState(false)

  if (!open) return null

  const checkLlm = async () => {
    setChecking(true)
    try {
      const s = await apiLlmStatus()
      if (s.ok) setLlmStatus(`OK • ${s.provider} (${s.model})`)
      else setLlmStatus(`Error • ${s.provider} (${s.model})${s.error ? `: ${s.error}` : ''}`)
    } catch (e: any) {
      setLlmStatus(`Error: ${e?.message || e}`)
    } finally {
      setChecking(false)
    }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-zinc-950 border border-zinc-800 rounded-xl p-4 shadow-xl">
        <div className="flex items-center justify-between mb-3 settings-modal-close-fix">
          <h3 className="text-lg font-semibold">Settings</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200">✕</button>
        </div>
        <div className="space-y-4 text-sm">
          <div>
            <div className="mb-1">LLM Model</div>
            <select
              className="w-full bg-zinc-950 border border-zinc-800 rounded p-2"
              value={settings.llmModel || 'gemini-1.5-pro'}
              onChange={e => onChange({ ...settings, llmModel: e.target.value })}
            >
              <option value="gemini-1.5-pro">gemini-1.5-pro (quality)</option>
              <option value="gemini-1.5-flash">gemini-1.5-flash (fast)</option>
            </select>
            <div className="mt-2 flex items-center gap-2">
              <button onClick={checkLlm} disabled={checking} className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700">{checking ? 'Checking…' : 'Check LLM'}</button>
              <span className="text-xs text-zinc-400">{llmStatus}</span>
            </div>
          </div>
          <label className="flex items-center justify-between">
            <span>Stream responses</span>
            <input type="checkbox" checked={settings.streamResponses} onChange={e => onChange({ ...settings, streamResponses: e.target.checked })} />
          </label>
          <label className="flex items-center justify-between">
            <span>Save chat history on this device</span>
            <input type="checkbox" checked={settings.saveHistory} onChange={e => onChange({ ...settings, saveHistory: e.target.checked })} />
          </label>
          <label className="flex items-center justify-between">
            <span>Reduce motion</span>
            <input type="checkbox" checked={settings.reduceMotion} onChange={e => onChange({ ...settings, reduceMotion: e.target.checked })} />
          </label>
          <div>
            <div className="mb-1">Text size</div>
            <div className="flex gap-2">
              {(['sm','md','lg'] as const).map(sz => (
                <button key={sz} onClick={() => onChange({ ...settings, textSize: sz })} className={`px-3 py-1 rounded border ${settings.textSize===sz ? 'border-purple-500 text-purple-300' : 'border-zinc-700 hover:border-zinc-600'}`}>{sz.toUpperCase()}</button>
              ))}
            </div>
          </div>
          <div className="pt-2 border-t border-zinc-800 text-xs text-zinc-400">
            <p>Privacy: Data stays local. Chats and files never leave your device.</p>
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <button onClick={onClearAll} className="text-red-400 hover:text-red-300 text-sm">Clear all local data</button>
          <button onClick={onClose} className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded">Close</button>
        </div>
      </div>
    </div>
  )
}
