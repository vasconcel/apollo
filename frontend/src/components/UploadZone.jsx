import { useState, useRef, useCallback } from 'react'
import { Upload, FileSpreadsheet, FileX } from 'lucide-react'

export default function UploadZone({ onSuccess, onError }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef(null)

  const upload = useCallback(
    async (file) => {
      setUploading(true)
      try {
        const fd = new FormData()
        fd.append('file', file)
        const res = await fetch('/api/import', { method: 'POST', body: fd })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || `Upload failed (${res.status})`)
        }
        onSuccess(await res.json())
      } catch (err) {
        onError(err.message)
      } finally {
        setUploading(false)
      }
    },
    [onSuccess, onError],
  )

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files?.[0]
      if (file) upload(file)
    },
    [upload],
  )

  const handleChange = useCallback(
    (e) => {
      const file = e.target.files?.[0]
      if (file) upload(file)
      e.target.value = ''
    },
    [upload],
  )

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragging(true)
  }
  const handleDragLeave = (e) => {
    e.preventDefault()
    setDragging(false)
  }

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={() => inputRef.current?.click()}
      className={`
        relative cursor-pointer border-2 border-dashed rounded-sm p-5
        flex flex-col items-center justify-center gap-3 text-center transition-all duration-200
        ${dragging
          ? 'border-cyan-400 bg-cyan-950/30 shadow-neon-cyan'
          : 'border-zinc-700 bg-zinc-900/50 hover:border-cyan-700 hover:bg-zinc-900/80'
        }
        ${uploading ? 'pointer-events-none opacity-60' : ''}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xls,.xlsx"
        className="hidden"
        onChange={handleChange}
      />

      {uploading ? (
        <>
          <FileSpreadsheet className="w-8 h-8 text-cyan-400 animate-neon-pulse" />
          <p className="text-xs font-medium text-zinc-400 uppercase tracking-wider">&gt; Ingesting&hellip;</p>
        </>
      ) : dragging ? (
        <>
          <Upload className="w-8 h-8 text-cyan-400" />
          <p className="text-xs font-medium text-cyan-400">&gt; Drop file to ingest</p>
        </>
      ) : (
        <>
          <div className="w-10 h-10 border border-zinc-700 rounded-sm flex items-center justify-center bg-zinc-900">
            <FileX className="w-5 h-5 text-zinc-500" />
          </div>
          <div>
            <p className="text-xs text-zinc-400">
              <span className="text-cyan-400 underline underline-offset-4 decoration-cyan-800 decoration-dotted">
                SELECT FILE
              </span>{' '}
              or drop here
            </p>
            <p className="text-[10px] text-zinc-600 mt-1 tracking-widest uppercase">Data Ingestion Port</p>
          </div>
        </>
      )}
    </div>
  )
}
