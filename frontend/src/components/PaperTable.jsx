import { useState } from 'react'
import { ChevronDown, ChevronUp, Loader2, AlertCircle, FileText, FileSearch, ThumbsUp, ThumbsDown, ShieldCheck, Pencil, Filter, X } from 'lucide-react'

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
  onFiltersChange,
}) {
  const [expanded, setExpanded] = useState(null)
  const [auditingId, setAuditingId] = useState(null)

  // Advanced filters state
  const [showFilters, setShowFilters] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [titleText, setTitleText] = useState('')
  const [abstractText, setAbstractText] = useState('')
  const [yearFrom, setYearFrom] = useState('')
  const [yearTo, setYearTo] = useState('')

  // Bulk selection state
  const [selectedPaperIds, setSelectedPaperIds] = useState(new Set())

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

  // ── Filter handlers ──────────────────────────────────────────────────────

  const applyFilters = () => {
    onPageChange(1)
    if (onFiltersChange) {
      onFiltersChange({
        search: searchText || null,
        title_contains: titleText || null,
        abstract_contains: abstractText || null,
        year_from: yearFrom ? parseInt(yearFrom, 10) : null,
        year_to: yearTo ? parseInt(yearTo, 10) : null,
      })
    }
  }

  const clearFilters = () => {
    setSearchText('')
    setTitleText('')
    setAbstractText('')
    setYearFrom('')
    setYearTo('')
    onPageChange(1)
    if (onFiltersChange) onFiltersChange({})
  }

  const handleFilterKeyDown = (e) => {
    if (e.key === 'Enter') applyFilters()
  }

  const handlePageChange = (newPage) => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    onPageChange(newPage)
  }

  // ── Bulk selection handlers ─────────────────────────────────────────────

  const allIdsOnPage = papers.map((p) => p.id)
  const allSelected = allIdsOnPage.length > 0 && allIdsOnPage.every((id) => selectedPaperIds.has(id))

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedPaperIds((prev) => {
        const next = new Set(prev)
        allIdsOnPage.forEach((id) => next.delete(id))
        return next
      })
    } else {
      setSelectedPaperIds((prev) => {
        const next = new Set(prev)
        allIdsOnPage.forEach((id) => next.add(id))
        return next
      })
    }
  }

  const toggleSelect = (id) => {
    setSelectedPaperIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleBulkAudit = async (verdict) => {
    const ids = Array.from(selectedPaperIds)
    if (ids.length === 0) return
    try {
      const res = await fetch('/api/papers/bulk-audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paper_ids: ids, verdict }),
      })
      if (!res.ok) return
      setSelectedPaperIds(new Set())
      if (onRefresh) onRefresh()
    } catch { /* ignore */ }
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
        <button
          onClick={() => setShowFilters((v) => !v)}
          className={`ml-2 inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold tracking-widest uppercase transition-all duration-150 ${
            showFilters
              ? 'text-cyan-400 border-b-2 border-cyan-500'
              : 'text-zinc-600 hover:text-zinc-400'
          }`}
        >
          <Filter className="w-3 h-3" />
          Filters
        </button>
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

      {/* ── Advanced Filters Panel ── */}
      {showFilters && (
        <div className="border-b border-zinc-800 px-4 py-3 bg-zinc-950/40 animate-glide-in">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <div>
              <label className="block text-[9px] text-zinc-600 uppercase tracking-widest mb-1">General Search</label>
              <input
                type="text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onKeyDown={handleFilterKeyDown}
                placeholder="Title or abstract..."
                className="w-full bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-[12px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-700 transition-colors"
              />
            </div>
            <div>
              <label className="block text-[9px] text-zinc-600 uppercase tracking-widest mb-1">Title Contains</label>
              <input
                type="text"
                value={titleText}
                onChange={(e) => setTitleText(e.target.value)}
                onKeyDown={handleFilterKeyDown}
                placeholder="Title keyword..."
                className="w-full bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-[12px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-700 transition-colors"
              />
            </div>
            <div>
              <label className="block text-[9px] text-zinc-600 uppercase tracking-widest mb-1">Abstract Contains</label>
              <input
                type="text"
                value={abstractText}
                onChange={(e) => setAbstractText(e.target.value)}
                onKeyDown={handleFilterKeyDown}
                placeholder="Abstract keyword..."
                className="w-full bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-[12px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-700 transition-colors"
              />
            </div>
            <div>
              <label className="block text-[9px] text-zinc-600 uppercase tracking-widest mb-1">Year From</label>
              <input
                type="number"
                value={yearFrom}
                onChange={(e) => setYearFrom(e.target.value)}
                onKeyDown={handleFilterKeyDown}
                placeholder="e.g. 2015"
                min="1900"
                max="2100"
                className="w-full bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-[12px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-700 transition-colors"
              />
            </div>
            <div>
              <label className="block text-[9px] text-zinc-600 uppercase tracking-widest mb-1">Year To</label>
              <input
                type="number"
                value={yearTo}
                onChange={(e) => setYearTo(e.target.value)}
                onKeyDown={handleFilterKeyDown}
                placeholder="e.g. 2024"
                min="1900"
                max="2100"
                className="w-full bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-[12px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-700 transition-colors"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={applyFilters}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-cyan-400 border border-cyan-800/60 hover:bg-cyan-950/30 transition-colors"
            >
              <Filter className="w-3 h-3" />
              Filter
            </button>
            <button
              onClick={clearFilters}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-zinc-500 border border-zinc-700 hover:text-zinc-300 hover:border-zinc-500 transition-colors"
            >
              <X className="w-3 h-3" />
              Clear
            </button>
          </div>
        </div>
      )}

      {/* ── Table ── */}
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="scanline-head border-b border-zinc-800">
              <th className="w-6 px-1 py-2 text-left">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  className="accent-cyan-500 cursor-pointer"
                />
              </th>
              <th className="w-6 px-1 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest" />
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest w-10">#</th>
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest">Library</th>
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest">Title</th>
              <th className="px-2 py-2 text-left font-medium text-[10px] text-zinc-600 uppercase tracking-widest w-28">Decision</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-2 py-10 text-center">
                  <Loader2 className="w-4 h-4 animate-spin text-zinc-600 mx-auto" />
                </td>
              </tr>
            ) : papers.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-2 py-10 text-center text-zinc-600 text-xs">
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
                    isSelected={selectedPaperIds.has(p.id)}
                    onToggle={() => toggleRow(p.id)}
                    onAudit={(verdict) => handleAudit(p.id, verdict)}
                    onToggleSelect={() => toggleSelect(p.id)}
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
            onClick={() => handlePageChange(page - 1)}
            className="px-3 py-1 text-[11px] font-bold tracking-wider text-zinc-500 hover:text-zinc-300 border border-zinc-700 hover:border-zinc-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            &lt; PREV
          </button>
          <span className="text-[11px] text-zinc-500 tabular-nums tracking-wider">
            PAGE {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => handlePageChange(page + 1)}
            className="px-3 py-1 text-[11px] font-bold tracking-wider text-zinc-500 hover:text-zinc-300 border border-zinc-700 hover:border-zinc-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            NEXT &gt;
          </button>
        </div>
      )}

      {/* ── Floating Bulk Action Bar ── */}
      {selectedPaperIds.size > 0 && (
        <div className="fixed bottom-8 left-1/2 z-50 -translate-x-1/2 animate-slide-up">
          <div className="flex items-center gap-4 bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl px-5 py-3">
            <span className="text-[12px] text-zinc-300 tabular-nums tracking-wider whitespace-nowrap">
              {selectedPaperIds.size} paper{selectedPaperIds.size > 1 ? 's' : ''} selected
            </span>
            <div className="w-px h-5 bg-zinc-700" />
            <button
              onClick={() => handleBulkAudit('YES')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-emerald-400 border border-emerald-800/60 hover:bg-emerald-950/30 transition-colors"
            >
              <ThumbsUp className="w-3 h-3" />
              Bulk Approve (Include)
            </button>
            <button
              onClick={() => handleBulkAudit('NO')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-rose-400 border border-rose-800/60 hover:bg-rose-950/30 transition-colors"
            >
              <ThumbsDown className="w-3 h-3" />
              Bulk Reject (Exclude)
            </button>
            <button
              onClick={() => handleBulkAudit('RESET')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-zinc-400 border border-zinc-700 hover:text-zinc-200 hover:border-zinc-500 transition-colors"
            >
              <X className="w-3 h-3" />
              Bulk Reset (Clear)
            </button>
            <div className="w-px h-5 bg-zinc-700" />
            <button
              onClick={() => setSelectedPaperIds(new Set())}
              className="inline-flex items-center gap-1.5 px-2 py-1.5 text-[11px] font-bold tracking-wider text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function PaperRow({ paper, rowNum, open, auditing, isSelected, onToggle, onAudit, onToggleSelect }) {
  const [editing, setEditing] = useState(false)
  const criteria = paper.applied_criteria_codes || []
  const exclusionCriteria = criteria.filter((c) => c.startsWith('EC'))
  const inclusionCriteria = criteria.filter((c) => c.startsWith('IC'))

  const typeColor = paper.source_type === 'WL' ? 'border-l-cyan-500' : paper.source_type === 'GL' ? 'border-l-fuchsia-500' : 'border-l-zinc-600'

  const aiDecision = paper.status === 'INCLUDED' ? 'YES' : paper.status === 'EXCLUDED' ? 'NO' : paper.status || null

  const handleAuditClick = (verdict) => {
    setEditing(false)
    onAudit(verdict)
  }

  return (
    <>
      <tr
        onClick={onToggle}
        className={`border-b border-zinc-800/60 cursor-pointer transition-all duration-150 hover:bg-zinc-800/80 ${
          open ? 'bg-zinc-800/60 border-l-2 ' + typeColor : ''
        }`}
      >
        <td className="px-1 py-2" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            className="accent-cyan-500 cursor-pointer"
          />
        </td>
        <td className="px-1 py-2 text-zinc-600">
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
        <td className="px-2 py-2">
          {paper.human_decision ? (
            paper.human_decision === 'YES' ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold bg-emerald-600 text-white">
                &#10003; Included
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold bg-rose-600 text-white">
                &#10007; Excluded
              </span>
            )
          ) : paper.status === 'INCLUDED' ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold border border-emerald-500/30 text-emerald-400 bg-emerald-950/10">
              AI: Include (Pending)
            </span>
          ) : paper.status === 'EXCLUDED' ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold border border-rose-500/30 text-rose-400 bg-rose-950/10">
              AI: Exclude (Pending)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold border border-amber-500/30 text-amber-400 bg-amber-950/10">
              AI: Needs Review (Pending)
            </span>
          )}
        </td>
      </tr>
      {open && (
        <tr key={`${paper.id}-detail`}>
          <td colSpan={6} className="px-0 py-0 border-b border-zinc-800">
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

              {/* Scraped Web Content — GL Papers */}
              {paper.source_type === 'GL' && (
                <div>
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                    &gt; SCRAPED WEB CONTENT
                  </span>
                  {paper.crawled_abstract ? (
                    <div
                      className="text-[11px] text-zinc-400 bg-zinc-950/40 border border-zinc-800 rounded-sm p-3 max-h-36 overflow-y-auto leading-relaxed whitespace-pre-wrap"
                      style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}
                    >
                      {paper.crawled_abstract}
                    </div>
                  ) : (
                    <p className="text-[11px] text-zinc-600 italic">
                      No web text scraped yet. Ensure the Ollama screening engine runs on this paper.
                    </p>
                  )}
                </div>
              )}

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

              {/* Full-Text PDF link */}
              {paper.pdf_url && (
                <div>
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest block mb-1">
                    &gt; FULL-TEXT PDF
                  </span>
                  <a
                    href={paper.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-bold tracking-wider text-cyan-400 border border-cyan-800/60 hover:bg-cyan-950/30 transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <FileText className="w-3 h-3" />
                    View Full-Text PDF
                  </a>
                </div>
              )}

              {/* Human Review Decision (Ground Truth) — State Lock & Edit */}
              <div>
                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-1.5 mb-2">
                  <ShieldCheck className="w-3 h-3 text-amber-400" />
                  Human Review Decision (Ground Truth):
                </span>
                {paper.human_decision && !editing ? (
                  <div className="flex items-center gap-3">
                    {paper.human_decision === 'YES' ? (
                      <div className="inline-flex items-center gap-2 border border-emerald-700/60 bg-emerald-950/20 px-3 py-1.5 text-[12px] font-bold text-emerald-400 tracking-wider">
                        <span className="text-emerald-400 text-sm">&#10003;</span>
                        You decided to INCLUDE this paper
                      </div>
                    ) : (
                      <div className="inline-flex items-center gap-2 border border-rose-700/60 bg-rose-950/20 px-3 py-1.5 text-[12px] font-bold text-rose-400 tracking-wider">
                        <span className="text-rose-400 text-sm">&#10007;</span>
                        You decided to EXCLUDE this paper
                      </div>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); setEditing(true) }}
                      className="inline-flex items-center gap-1.5 border border-zinc-700 bg-zinc-800/50 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 px-2.5 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-150"
                    >
                      <Pencil className="w-3 h-3" />
                      Edit Decision
                    </button>
                  </div>
                ) : aiDecision === 'NO' ? (
                  <div>
                    <p className="text-[11px] text-zinc-400 mb-2 leading-relaxed">
                      AI recommends EXCLUDING this paper. Do you agree with this decision?
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAuditClick('NO') }}
                        disabled={auditing}
                        className="inline-flex items-center gap-1.5 border-2 border-emerald-700/50 bg-emerald-950/10 backdrop-blur text-emerald-400 hover:bg-emerald-950/40 hover:shadow-[0_0_12px_rgba(16,185,129,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                      >
                        {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsUp className="w-3 h-3" />}
                        Yes, Accept &amp; Exclude
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAuditClick('YES') }}
                        disabled={auditing}
                        className="inline-flex items-center gap-1.5 border-2 border-rose-700/50 bg-rose-950/10 backdrop-blur text-rose-400 hover:bg-rose-950/40 hover:shadow-[0_0_12px_rgba(244,63,94,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                      >
                        {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsDown className="w-3 h-3" />}
                        No, Reject &amp; Include
                      </button>
                    </div>
                  </div>
                ) : aiDecision === 'YES' ? (
                  <div>
                    <p className="text-[11px] text-zinc-400 mb-2 leading-relaxed">
                      AI recommends INCLUDING this paper. Do you agree with this decision?
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAuditClick('YES') }}
                        disabled={auditing}
                        className="inline-flex items-center gap-1.5 border-2 border-emerald-700/50 bg-emerald-950/10 backdrop-blur text-emerald-400 hover:bg-emerald-950/40 hover:shadow-[0_0_12px_rgba(16,185,129,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                      >
                        {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsUp className="w-3 h-3" />}
                        Yes, Accept &amp; Include
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAuditClick('NO') }}
                        disabled={auditing}
                        className="inline-flex items-center gap-1.5 border-2 border-rose-700/50 bg-rose-950/10 backdrop-blur text-rose-400 hover:bg-rose-950/40 hover:shadow-[0_0_12px_rgba(244,63,94,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                      >
                        {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsDown className="w-3 h-3" />}
                        No, Reject &amp; Exclude
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <p className="text-[11px] text-zinc-400 mb-2 leading-relaxed">
                      AI was unable to decide. Please select the manual human decision (Ground Truth):
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAuditClick('YES') }}
                        disabled={auditing}
                        className="inline-flex items-center gap-1.5 border-2 border-emerald-700/50 bg-emerald-950/10 backdrop-blur text-emerald-400 hover:bg-emerald-950/40 hover:shadow-[0_0_12px_rgba(16,185,129,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                      >
                        {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsUp className="w-3 h-3" />}
                        Include Paper (YES)
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAuditClick('NO') }}
                        disabled={auditing}
                        className="inline-flex items-center gap-1.5 border-2 border-rose-700/50 bg-rose-950/10 backdrop-blur text-rose-400 hover:bg-rose-950/40 hover:shadow-[0_0_12px_rgba(244,63,94,0.2)] disabled:border-zinc-700 disabled:text-zinc-600 disabled:bg-transparent disabled:cursor-not-allowed px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all duration-200"
                      >
                        {auditing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ThumbsDown className="w-3 h-3" />}
                        Exclude Paper (NO)
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
