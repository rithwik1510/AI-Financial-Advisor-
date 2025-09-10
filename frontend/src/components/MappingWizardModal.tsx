import { useState } from 'react'
import { apiSaveTemplate } from '../api'

export default function MappingWizardModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState('My Bank Template')
  const [anchors, setAnchors] = useState('Account Summary, Transaction Details')
  const [dateRange, setDateRange] = useState<[number, number]>([40, 120] as any)
  const [descRange, setDescRange] = useState<[number, number]>([125, 380] as any)
  const [amtRange, setAmtRange] = useState<[number, number]>([400, 9999] as any)
  const [fmt, setFmt] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  if (!open) return null

  const save = async () => {
    setSaving(true); setStatus(null)
    try {
      const payload = {
        name,
        anchors: anchors.split(',').map(s => s.trim()).filter(Boolean),
        columns: { date: dateRange, description: descRange, amount: amtRange },
        date_format: fmt || undefined,
      }
      const res = await apiSaveTemplate(payload as any)
      setStatus(`Saved: ${res.path}`)
    } catch (e: any) {
      setStatus(`Failed to save template: ${e?.message || e}`)
    } finally {
      setSaving(false)
    }
  }

  const parseTuple = (s: string, def: [number, number]) => {
    const m = s.split(',').map(x => parseFloat(x.trim())).filter(x => !isNaN(x))
    return (m.length === 2 ? ([m[0], m[1]] as [number, number]) : def)
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-2xl p-5">
        <h3 className="text-lg font-semibold">Map Columns (PDF Template)</h3>
        <p className="text-sm text-zinc-400 mt-1">Estimate X-position ranges (in points) for each column. You can inspect PDF layouts using viewers that show coordinates, or start with guesses and iterate.</p>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <label className="text-sm">Template Name
            <input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-2" value={name} onChange={e=>setName(e.target.value)} />
          </label>
          <label className="text-sm">Date Format (optional)
            <input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-2" value={fmt} onChange={e=>setFmt(e.target.value)} placeholder="%m/%d/%Y" />
          </label>
          <label className="col-span-2 text-sm">Anchors (comma separated)
            <input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-2" value={anchors} onChange={e=>setAnchors(e.target.value)} />
          </label>
          <label className="text-sm">Date X-Range (e.g., 40,120)
            <input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-2" defaultValue={dateRange.join(',')} onBlur={e=>setDateRange(parseTuple(e.target.value, dateRange))} />
          </label>
          <label className="text-sm">Description X-Range (e.g., 125,380)
            <input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-2" defaultValue={descRange.join(',')} onBlur={e=>setDescRange(parseTuple(e.target.value, descRange))} />
          </label>
          <label className="text-sm">Amount X-Range (e.g., 400,9999)
            <input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-2" defaultValue={amtRange.join(',')} onBlur={e=>setAmtRange(parseTuple(e.target.value, amtRange))} />
          </label>
        </div>
        {status && <div className="mt-3 text-sm text-zinc-300">{status}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button disabled={saving} onClick={onClose} className="px-3 py-2 rounded bg-zinc-800 hover:bg-zinc-700">Close</button>
          <button disabled={saving} onClick={save} className="px-3 py-2 rounded bg-purple-600 hover:bg-purple-700">Save Template</button>
        </div>
      </div>
    </div>
  )
}

