import { useState } from 'react'
import { ChevronDown, ChevronUp, Loader2, AlertCircle, FileText, FileSearch, ThumbsUp, ThumbsDown, ShieldCheck } from 'lucide-react'

const TABS = ['All', 'Included', 'Excluded', 'Needs Review']

const SOURCE_TYPES = [
  { key: 'ALL', label: 'ALL' },
  { key: 'WL', label: '[ WL ]' },
  { key: 'GL', label: '[ GL ]' },
]

const SOURCE_BADGE = {
  WL: { label: '[ WL ]', classes: 'text-cyan-400 border-cyan-700 drop-shadow-[0_0_4px_rgba(34,211,238,0.3)]' },
  GL: { label: '[ GL ]', classes: 'text-fuchsia-400 border-fuchsia-700 drop-shadow-[0_0_4px_rgba(217,70,239,0.3)]' },
}

function statusLabel(status) {
  if (!status) {
    return <span className="text-[12px] text-zinc-600 font-mono tracking-wider">&gt; PENDING</span>
  }
  if (status === 'INCLUDED') {
    return <span className="text-[12px] text-emerald-400 font-mono tracking-wider">&gt; INCLUDED</span>
  }
  if (status === 'EXCLUDED') {
    return <span className="text-[12px] text-rose-400 font-mono tracking-wider">! EXCLUDED</span>
  }
  return <span className="text-[12px] text-amber-400 font-mono tracking-wider">? {status}</span>
}

export default function PaperTable({
  papers,
  total,
  page,
  totalPages,
  loading,
  statusFilter,
  literatureType,
  onTabChange,
  onPageChange,
  onLiteratureTypeChange,
  onRefresh,
}) {
  const [expanded, setExpanded] = useState(null)
  const [auditingId, setAuditingId] = useState(null)

  const activeTab = !statusFilter ? 'All' : statusFilter === 'INCLUDED' ? 'Included' : statusFilter === 'EXCLUDED' ? 'Excluded' : 'Needs Review'

  const toggleRow = (id) => {
    setExpanded((prev) => (prev === id ? null : id))
  }

  const handleAudit = async (paperId, verdict) => {
    setAuditingId(paperId)
    try {
      const res = await fetch(`/api/papers/${paperId}/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verdict }),
      })
      if (!res.ok) return
      if (onRefresh) onRefresh()
    } catch { /* ignore */ } finally {
      setAuditingId(null)
    }
  }

  return (
    <div className="border border-zinc-800 bg-zinc-900/50 rounded-sm overflow-hidden animate-glide-in">
      {/* ── Status Filters ── */}
      <div className="flex items-center gap-1 px-3 pt-3 pb-1.5 border-b border-zinc-800">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            className={`px-2.5 py-1 text-[11px] font-bold tracking-widest uppercase transition-all duration-150 ${
              activeTab === tab
                ? 'text-cyan-400 border-b-2 border-cyan-500'
                : 'text-zinc-600 hover:text-zinc-400'
            }`}
          >
            {tab}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-zinc-600 tabular-nums tracking-wider">{total} RESULT{total !== 1 ? 'S' : ''}</span>
      </div>

      {/* ── Literature Type Toggle ── */}
      <div className="flex items-center gap-1 px-3 pb-3 border-b border-zinc-800">
        {SOURCE_TYPES.map((st) => (
          <button
            key={st.key}
            onClick={() => onLiteratureTypeChange(st.key)}
            className={`inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold tracking-wider transition-all duration-150 ${
              literatureType === st.key
                ? st.key === 'WL' ? 'text-cyan-400 bg-cyan-950/30' : st.key === 'GL' ? 'text-fuchsia-400 bg-fuchsia-950/30' : 'text-zinc-200 bg-zinc-800'
                : 'text-zinc-600 hover:text-zinc-400'
            }`}
          >
            {st.key === 'WL' && <FileText className="w-3 h-3" />}
            {st.key === 'GL' && <FileSearch className="w-3 h-3" />}
            {st.label}
          </button>
        ))}
      </div>

      {/* ── Table ── */}
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="scanline-head border-b border-zinc-800">
              <th className="w-8 px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest" />
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest w-10">#</th>
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest">Library</th>
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest">Title</th>
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest w-28">Decision</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-2 py-10 text-center">
                  <Loader2 className="w-4 h-4 animate-spin text-zinc-600 mx-auto" />
                </td>
              </tr>
            ) : papers.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-2 py-10 text-center text-zinc-600 text-xs">
                  <AlertCircle className="w-4 h-4 mx-auto mb-1" />
                  No records match filter.
                </td>
              </tr>
            ) : (
              papers.map((p, idx) => {
                const open = expanded === p.id
                const rowNum = (page - 1) * 20 + idx + 1
                return (
                  <PaperRow
                    key={p.id}
                    paper={p}
                    rowNum={rowNum}
                    open={open}
                    auditing={auditingId === p.id}
                    onToggle={() => toggleRow(p.id)}
                    onAudit={(verdict) => handleAudit(p.id, verdict)}
                  />
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2.5 border-t border-zinc-800">
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="px-3 py-1 text-[11px] font-bold tracking-wider text-zinc-500 hover:text-zinc-300 border border-zinc-700 hover:border-zinc-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            &lt; PREV
          </button>
          <span className="text-[11px] text-zinc-500 tabular-nums tracking-wider">
            PAGE {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1 text-[11px] font-bold tracking-wider text-zinc-500 hover:text-zinc-300 border border-zinc-700 hover:border-zinc-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            NEXT &gt;
          </button>
        </div>
      )}
    </div>
  )
}

function PaperRow({ paper, rowNum, open, auditing, onToggle, onAudit }) {
  const criteria = paper.applied_criteria_codes || []
  const exclusionCriteria = criteria.filter((c) => c.startsWith('EC'))
  const inclusionCriteria = criteria.filter((c) => c.startsWith('IC'))

  const typeColor = paper.source_type === 'WL' ? 'border-l-cyan-500' : paper.source_type === 'GL' ? 'border-l-fuchsia-500' : 'border-l-zinc-600'

  return (
    <>
      <tr
        onClick={onToggle}
        className={`border-b border-zinc-800/60 cursor-pointer transition-all duration-150 hover:bg-zinc-800/80 ${
          open ? 'bg-zinc-800/60 border-l-2 ' + typeColor : ''
        }`}
      >
        <td className="px-2 py-2 text-zinc-600">
          {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </td>
        <td className="px-2 py-2 text-zinc-500 tabular-nums text-[12px]">{rowNum}</td>
        <td className="px-2 py-2 text-zinc-400 max-w-[120px] truncate text-[12px]">{paper.source_library}</td>
        <td className="px-2 py-2 text-zinc-200 font-medium max-w-md">
          <div className="flex items-center gap-2 truncate">
            {paper.source_type && SOURCE_BADGE[paper.source_type] && (
              <span className={`inline-block border px-1 py-0.5 text-[9px] font-bold leading-none shrink-0 ${SOURCE_BADGE[paper.source_type].classes}`}>
                {SOURCE_BADGE[paper.source_type].label}
              </span>
            )}
            <span className="truncate">{paper.title}</span>
          </div>
        </td>
        <td className="px-2 py-2">{statusLabel(paper.status)}</td>
      </tr>
      {open && (
        <tr key={`${paper.id}-detail`}>
          <td colSpan={5} className="px-0 py-0 border-b border-zinc-800">
            <div className="px-8 py-4 space-y-4 bg-zinc-950/60 text-[13px] leading-relaxed animate-glide-in">
              {/* Abstract — Decrypted Report */}
              <div>
                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                  &gt; ABSTRACT
                </span>
                <div className={`border-l-2 ${paper.source_type === 'WL' ? 'border-l-cyan-700' : paper.source_type === 'GL' ? 'border-l-fuchsia-700' : 'border-l-zinc-600'} pl-3`}>
                  <p className="text-zinc-400 max-h-24 overflow-y-auto whitespace-pre-wrap text-[12px] leading-relaxed" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
                    {paper.abstract || '(no abstract)'}
                  </p>
                </div>
              </div>

              {/* Criteria codes */}
              <div className="flex flex-wrap gap-5">
                {inclusionCriteria.length > 0 && (
                  <div>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                      &gt; INCLUSION
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {inclusionCriteria.map((code) => (
                        <span key={code} className="inline-block border border-emerald-800/60 bg-emerald-950/10 px-1.5 py-0.5 text-[10px] font-bold text-emerald-400 tracking-wider">
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {exclusionCriteria.length > 0 && (
                  <div>
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                      &gt; EXCLUSION
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {exclusionCriteria.map((code) => (
                        <span key={code} className="inline-block border border-rose-800/60 bg-rose-950/10 px-1.5 py-0.5 text-[10px] font-bold text-rose-400 tracking-wider">
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {criteria.length === 0 && (
                  <p className="text-[11px] text-zinc-600">No criteria codes recorded.</p>
                )}
              </div>

              {/* AI Rationale — Decrypted Report */}
              {paper.rationale && (
                <div>
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                    &gt; AI RATIONALE
                  </span>
                  <div className={`border-l-2 ${paper.source_type === 'WL' ? 'border-l-cyan-700' : paper.source_type === 'GL' ? 'border-l-fuchsia-700' : 'border-l-zinc-600'} pl-3`}>
                    <div className="bg-zinc-950 border border-zinc-800 p-2.5 text-zinc-400 text-[11px] leading-relaxed max-h-36 overflow-y-auto whitespace-pre-wrap">
                      {paper.rationale}
                    </div>
                  </div>
                </div>
              )}

              {/* Human Audit Override — Neon-wire glassmorphism */}
              <div>
                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-1.5 mb-2">
                  <ShieldCheck className="w-3 h-3 text-amber-400" />
                  HUMAN AUDIT OVERRIDE
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); onAudit('YES') }}
                    disabled={auditing}
                    className="inline-flex items-center gap-1.5 border-2 border-emerald-700/50 bg-emerald-950/10 backdrop-blur text-emerald-400 hover:bg-emerald-950/40 hover:shadow-[0_0_12px_rgba(16,185,129,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                  >
                    {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsUp className="w-3 h-3" />}
                    &gt; APPROVE YES
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onAudit('NO') }}
                    disabled={auditing}
                    className="inline-flex items-center gap-1.5 border-2 border-rose-700/50 bg-rose-950/10 backdrop-blur text-rose-400 hover:bg-rose-950/40 hover:shadow-[0_0_12px_rgba(244,63,94,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                  >
                    {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsDown className="w-3 h-3" />}
                    ! REJECT NO
                  </button>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
