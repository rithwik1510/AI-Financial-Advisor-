import { useRef, useState } from 'react'
import { apiParse, Transaction } from '../api'

export default function FileUpload({ onParsed }: { onParsed: (tx: Transaction[]) => void }) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setBusy(true); setErr(null)
    try {
      const arr = Array.from(files)
      const res = await apiParse(arr)
      onParsed(res.transactions)
    } catch (e: any) {
      setErr(e?.message || 'Failed to parse files')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="border rounded p-4 bg-white shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold">Upload Statements</h3>
          <p className="text-sm text-gray-600">PDF/CSV/XLSX are supported.</p>
        </div>
        <label className="cursor-pointer inline-flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700">
          <input ref={inputRef} type="file" multiple className="hidden" accept=".pdf,.csv,.xlsx,.xls" onChange={(e) => handleFiles(e.target.files)} />
          {busy ? 'Processing...' : 'Choose Files'}
        </label>
      </div>
      <div className="mt-3 text-xs text-gray-600">
        <p><strong>Tip:</strong> For best accuracy, upload CSV/XLSX exports from your bank. PDF parsing is experimental and may miss rows on complex layouts or scanned PDFs.</p>
      </div>
      {err && <p className="text-red-600 text-sm mt-2">{err}</p>}
    </div>
  )
}
