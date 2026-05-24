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
        relative cursor-pointer rounded-xl border-2 border-dashed p-6
        flex flex-col items-center justify-center gap-3 text-center transition-all duration-200
        ${dragging ? 'border-emerald-400 bg-emerald-50' : 'border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50'}
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
          <FileSpreadsheet className="w-10 h-10 text-emerald-500 animate-pulse" />
          <p className="text-sm font-medium text-gray-600">Importing…</p>
        </>
      ) : dragging ? (
        <>
          <Upload className="w-10 h-10 text-emerald-500" />
          <p className="text-sm font-medium text-emerald-600">Drop your file here</p>
        </>
      ) : (
        <>
          <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
            <FileX className="w-6 h-6 text-gray-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700">
              <span className="text-emerald-600 underline underline-offset-2">Click to upload</span> or drag and drop
            </p>
            <p className="text-xs text-gray-400 mt-1">CSV, XLS or XLSX up to 50MB</p>
          </div>
        </>
      )}
    </div>
  )
}
