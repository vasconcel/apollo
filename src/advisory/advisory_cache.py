"""
Centralized advisory cache layer for APOLLO.

This module provides:
- Session cache for current runtime
- Disk cache for persistence across restarts
- Deterministic cache key generation
- Advisory retrieval API (read-only for UI)

STRICT ISOLATION:
- UI modules MUST use get() to retrieve advisories
- UI modules MUST NOT generate, retry, or backoff
- Only worker pipeline may generate advisories
"""

import os
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from .advisory_models import (
    AdvisoryResult,
    AdvisoryConfig,
    AdvisoryDecision,
    AdvisoryStatus
)

_VERBOSE = False  # Set to True for debug, False for production

_mem_snapshot_cache: Dict[str, AdvisoryResult] = {}
_mem_snapshot_hits: int = 0
_mem_snapshot_misses: int = 0


def _get_mem_snapshot(title: str, abstract: str, protocol_version: str, stage: str) -> Optional[AdvisoryResult]:
    """Get advisory from memory snapshot cache (reduces rerender lookups)."""
    global _mem_snapshot_cache, _mem_snapshot_hits, _mem_snapshot_misses

    cache = get_advisory_cache()
    key = cache.compute_cache_key(title, abstract, protocol_version)
    cache_key_full = f"{stage}_{key}"

    if cache_key_full in _mem_snapshot_cache:
        _mem_snapshot_hits += 1
        return _mem_snapshot_cache[cache_key_full]

    _mem_snapshot_misses += 1
    return None


def _set_mem_snapshot(title: str, abstract: str, protocol_version: str, stage: str, advisory: AdvisoryResult) -> None:
    """Set advisory in memory snapshot cache."""
    global _mem_snapshot_cache

    cache = get_advisory_cache()
    key = cache.compute_cache_key(title, abstract, protocol_version)
    cache_key_full = f"{stage}_{key}"

    _mem_snapshot_cache[cache_key_full] = advisory


def clear_mem_snapshot() -> None:
    """Clear memory snapshot cache (call at session start)."""
    global _mem_snapshot_cache, _mem_snapshot_hits, _mem_snapshot_misses
    _mem_snapshot_cache = {}
    _mem_snapshot_hits = 0
    _mem_snapshot_misses = 0


def get_mem_snapshot_stats() -> Dict:
    """Get memory snapshot cache statistics."""
    return {"hits": _mem_snapshot_hits, "misses": _mem_snapshot_misses, "size": len(_mem_snapshot_cache)}


def _log_verbose(msg: str) -> None:
    """Conditional verbose logging - only prints when _VERBOSE is True."""
    if _VERBOSE:
        print(msg)


def validate_advisory_structure(advisory: Any) -> tuple[bool, str, Optional[Dict]]:
    """
    Validate advisory structure and return normalized form.
    
    Returns:
        (is_valid, error_message, normalized_dict)
    """
    if advisory is None:
        return False, "Advisory is None", None
    
    if not isinstance(advisory, AdvisoryResult):
        return False, f"Invalid advisory type: {type(advisory).__name__}", None
    
    try:
        decision_val = advisory.decision.value if hasattr(advisory.decision, 'value') else str(advisory.decision)
        confidence_val = float(advisory.confidence) if advisory.confidence is not None else 0.0
        
        normalized = {
            "stage": getattr(advisory, 'stage', 'unknown'),
            "decision": decision_val,
            "confidence": confidence_val,
            "triggered_criteria": list(advisory.triggered_criteria) if advisory.triggered_criteria else [],
            "non_triggered_criteria": list(getattr(advisory, 'non_triggered_criteria', [])) if hasattr(advisory, 'non_triggered_criteria') else [],
            "criterion_evaluations": {},
            "justification": str(advisory.justification) if advisory.justification else "",
            "is_fallback": bool(advisory.is_fallback),
            "is_placeholder": bool(advisory.is_placeholder),
            "error": str(advisory.error) if advisory.error else None,
            "generated_at": str(advisory.generated_at) if advisory.generated_at else None
        }
        
        if advisory.criterion_evaluations:
            for ce in advisory.criterion_evaluations:
                if hasattr(ce, 'criterion_id'):
                    normalized["criterion_evaluations"][ce.criterion_id] = {
                        "criterion_name": getattr(ce, 'criterion_name', ce.criterion_id),
                        "satisfied": getattr(ce, 'satisfied', False),
                        "triggered": getattr(ce, 'triggered', getattr(ce, 'satisfied', False)),
                        "evidence": getattr(ce, 'evidence', []),
                        "confidence": getattr(ce, 'confidence', 0.0),
                        "justification": getattr(ce, 'justification', "")
                    }
        
        return True, "", normalized
        
    except Exception as e:
        return False, f"Validation error: {str(e)}", None


class AdvisoryCache:
    """
    Centralized advisory cache with multi-layer retrieval.
    
    Layers (in order of priority):
    1. Session cache (memory, fastest)
    2. Disk cache (persistent)
    3. Return unavailable (never generate)
    """
    
    def __init__(self, config: Optional[AdvisoryConfig] = None):
        self.config = config or AdvisoryConfig()
        self._session_cache: Dict[str, AdvisoryResult] = {}
        self.entries: Dict[str, AdvisoryResult] = {}  # Alias for backward compatibility
        
        self._cache_dir = Path(self.config.cache_dir)
        if self.config.enable_disk_cache:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def __len__(self) -> int:
        """Return number of cached advisories in session cache."""
        return len(self._session_cache)
    
    def get(self, cache_key: str, protocol_version: str = "1.0", stage: str = "ic") -> AdvisoryResult:
        """
        Retrieve advisory by cache key.
        
        This is the PRIMARY API for UI modules.
        
        Returns:
            AdvisoryResult - always returns (never generates)
            - If cached: returns cached advisory
            - If not cached: returns UNAVAILABLE placeholder
            
        NEVER generates or retries - strictly read-only.
        """
        if not cache_key:
            _log_verbose(f"[CACHE GET] Stage: {stage} | Key: NONE (empty)")
            return AdvisoryResult.create_unavailable("No cache key provided")

        session_key = self._session_key(cache_key, protocol_version, stage)

        if session_key in self._session_cache:
            cached = self._session_cache[session_key]
            _log_verbose(f"[CACHE GET] Stage: {stage} | Key: {cache_key[:16]}... | Session HIT")
            return cached

        disk_advisory = self._load_from_disk(cache_key, stage)
        if disk_advisory is not None:
            self._session_cache[session_key] = disk_advisory
            _log_verbose(f"[CACHE GET] Stage: {stage} | Key: {cache_key[:16]}... | Disk HIT")
            return disk_advisory

        _log_verbose(f"[CACHE GET] Stage: {stage} | Key: {cache_key[:16]}... | MISS (not generated)")
        return AdvisoryResult.create_unavailable("Advisory not yet generated")
    
    def get_for_article(
            self,
            title: str,
            abstract: str,
            protocol_version: str = "1.0",
            stage: str = "ic"
        ) -> AdvisoryResult:
            """
            Retrieve advisory by article content.
            
            Computes cache key from content, then delegates to get().
            """
            cache_key = self._compute_cache_key(title, abstract, protocol_version)
            print(f"[CACHE GET ARTICLE] Stage: {stage} | Title: {title[:30] if title else 'empty'}... | Key: {cache_key[:16]}...")
            return self.get(cache_key, protocol_version, stage)
    
    def set(self, advisory: AdvisoryResult, stage: str = "ic") -> None:
        """
        Store advisory in cache.
        
        This should ONLY be called by worker pipeline, not UI.
        
        Stores to:
        1. Session cache (memory)
        2. Disk cache (persistent)
        """
        if not advisory.cache_key:
            return
        
        session_key = self._session_key(advisory.cache_key, advisory.protocol_version, stage)
        self._session_cache[session_key] = advisory
        
        if self.config.enable_disk_cache:
            self._save_to_disk(advisory, stage)
    
    def has(self, cache_key: str, protocol_version: str = "1.0", stage: str = "ic") -> bool:
        """Check if advisory exists in any cache layer."""
        session_key = self._session_key(cache_key, protocol_version, stage)
        if session_key in self._session_cache:
            return True
        
        disk_path = self._disk_path(cache_key, stage)
        return disk_path.exists()
    
    def get_status(self, cache_key: str, protocol_version: str = "1.0", stage: str = "ic") -> AdvisoryStatus:
        """Get status of advisory with detection for prefiltered/quarantined/fallback."""
        advisory = self.get(cache_key, protocol_version, stage)

        prefilter_applied = getattr(advisory, 'prefilter_applied', False)
        stage_validation = getattr(advisory, 'stage_validation', "") or ""
        model_used = getattr(advisory, 'model_used', "") or ""

        if getattr(advisory, 'prefilter_applied', False):
            return AdvisoryStatus.PREFILTERED

        if "QUARANTINED" in (getattr(advisory, 'stage_validation', "") or ""):
            return AdvisoryStatus.QUARANTINED

        if model_used == "prefilter" or (getattr(advisory, 'raw_confidence', -1) == 0 and model_used == ""):
            if advisory.is_available():
                return AdvisoryStatus.PREFILTERED

        if advisory.is_placeholder and advisory.error:
            if "not yet generated" in advisory.error.lower():
                return AdvisoryStatus.PENDING
            return AdvisoryStatus.FAILED
        
        if advisory.error:
            return AdvisoryStatus.FAILED
        
        if advisory.is_available():
            return AdvisoryStatus.COMPLETED
        
        return AdvisoryStatus.UNAVAILABLE
    
    def list_cached(self, protocol_version: str = "1.0") -> List[str]:
        """List all cached advisory keys."""
        keys = set()
        
        for session_key in self._session_cache:
            if session_key.endswith(f"_{protocol_version}"):
                key = session_key.rsplit("_", 1)[0]
                keys.add(key)
        
        if self.config.enable_disk_cache and self._cache_dir.exists():
            for f in self._cache_dir.glob("*.json"):
                key = f.stem
                keys.add(key)
        
        return list(keys)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        session_count = len(self._session_cache)
        
        disk_count = 0
        if self.config.enable_disk_cache and self._cache_dir.exists():
            disk_count = len(list(self._cache_dir.glob("*.json")))
        
        return {
            "session_cache_count": session_count,
            "disk_cache_count": disk_count,
            "total_cached": max(session_count, disk_count),
            "cache_dir": str(self._cache_dir)
        }
    
    def clear_session(self) -> None:
        """Clear session cache only (preserves disk cache)."""
        self._session_cache.clear()
    
    def clear_disk(self) -> None:
        """Clear disk cache only."""
        if self._cache_dir.exists():
            for f in self._cache_dir.glob("*.json"):
                f.unlink()
    
    def clear_all(self) -> None:
        """Clear both session and disk caches."""
        self.clear_session()
        self.clear_disk()
    
    @staticmethod
    def compute_cache_key(title: str, abstract: str, protocol_version: str = "1.0") -> str:
        """
        Compute deterministic cache key from article content.
        
        This is PUBLIC API for cache key computation.
        
        Same content + same protocol = same key (deterministic).
        """
        content = f"{protocol_version}:{title.strip().lower()}:{abstract.strip().lower()}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _session_key(self, cache_key: str, protocol_version: str, stage: str = "ic") -> str:
        """Construct session cache key."""
        return f"{stage}_{cache_key}_{protocol_version}"
    
    def _compute_cache_key(self, title: str, abstract: str, protocol_version: str) -> str:
        """Compute cache key (internal helper)."""
        return self.compute_cache_key(title, abstract, protocol_version)
    
    def _disk_path(self, cache_key: str, stage: str = "ic") -> Path:
        """Get disk path for cache key."""
        stage_dir = self._cache_dir / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        return stage_dir / f"{cache_key}.json"
    
    def _load_from_disk(self, cache_key: str, stage: str = "ic") -> Optional[AdvisoryResult]:
        """Load advisory from disk cache with validation."""
        disk_path = self._disk_path(cache_key, stage)

        if not disk_path.exists():
            _log_verbose(f"[CACHE DISK] Stage: {stage} | Key: {cache_key[:16]}... | File not found")
            return None

        try:
            with open(disk_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            advisory = AdvisoryResult.from_dict(data)

            if advisory.error and "NoneType" in advisory.error and "attribute" in advisory.error:
                print(f"[CACHE INVALIDATE] Legacy corrupted entry: {cache_key[:16]}...")
                try:
                    disk_path.unlink()
                    _log_verbose(f"[CACHE INVALIDATE] Removed: {disk_path}")
                except Exception:
                    pass
                return None

            _log_verbose(f"[CACHE DISK] Stage: {stage} | Key: {cache_key[:16]}... | Loaded successfully")
            return advisory
        except json.JSONDecodeError as e:
            print(f"[CACHE DISK ERROR] Stage: {stage} | Key: {cache_key[:16]}... | JSON parse error: {e}")
            return None
        except Exception as e:
            print(f"[CACHE DISK ERROR] Stage: {stage} | Key: {cache_key[:16]}... | Load error: {e}")
            return None
    
    def _save_to_disk(self, advisory: AdvisoryResult, stage: str = "ic") -> None:
        """Save advisory to disk cache."""
        disk_path = self._disk_path(advisory.cache_key, stage)
        
        try:
            with open(disk_path, 'w', encoding='utf-8') as f:
                json.dump(advisory.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save advisory to disk: {e}")


_global_cache: Optional[AdvisoryCache] = None


def get_advisory_cache() -> AdvisoryCache:
    """Get global advisory cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = AdvisoryCache()
    return _global_cache


def set_advisory_cache(cache: AdvisoryCache) -> None:
    """Set global advisory cache instance (for testing)."""
    global _global_cache
    _global_cache = cache


def get_advisory(
    title: str,
    abstract: str,
    protocol_version: str = "1.0",
    stage: str = "ic"
) -> AdvisoryResult:
    """
    Get advisory for article (public API) with memoization.

    This is the STRICTLY READ-ONLY entry point for UI modules.

    Uses memory snapshot cache to avoid repeated lookups during same render cycle.
    """
    cached = _get_mem_snapshot(title, abstract, protocol_version, stage)
    if cached is not None:
        _log_verbose(f"[MEM SNAPSHOT HIT] Stage: {stage}")
        return cached

    cache = get_advisory_cache()
    result = cache.get_for_article(title, abstract, protocol_version, stage)

    _set_mem_snapshot(title, abstract, protocol_version, stage, result)
    return result


def get_advisory_by_key(
    cache_key: str,
    protocol_version: str = "1.0",
    stage: str = "ic"
) -> AdvisoryResult:
    """Get advisory by cache key (public API)."""
    cache = get_advisory_cache()
    return cache.get(cache_key, protocol_version, stage)


def has_advisory(
    title: str,
    abstract: str,
    protocol_version: str = "1.0",
    stage: str = "ic"
) -> bool:
    """Check if advisory exists for article."""
    cache = get_advisory_cache()
    key = cache.compute_cache_key(title, abstract, protocol_version)
    return cache.has(key, protocol_version, stage)


def store_advisory(advisory: AdvisoryResult, stage: str = "ic") -> None:
    """
    Store advisory in cache (public API for worker).
    
    Only worker pipeline should call this.
    """
    cache = get_advisory_cache()
    cache.set(advisory, stage)


def get_advisory_status(
    title: str,
    abstract: str,
    protocol_version: str = "1.0",
    stage: str = "ic"
) -> AdvisoryStatus:
    """Get status of advisory."""
    cache = get_advisory_cache()
    key = cache.compute_cache_key(title, abstract, protocol_version)
    return cache.get_status(key, protocol_version, stage)


def get_cache_stats() -> Dict:
    """Get cache statistics."""
    cache = get_advisory_cache()
    return cache.get_cache_stats()


def list_cached_advisories(protocol_version: str = "1.0") -> List[str]:
    """List all cached advisory keys."""
    cache = get_advisory_cache()
    return cache.list_cached(protocol_version)


def get_ec_advisory(
    title: str,
    abstract: str,
    protocol_version: str = "1.0"
) -> AdvisoryResult:
    """
    Get EC advisory for article (convenience wrapper).
    
    Uses stage="ec" to separate from IC advisories.
    """
    return get_advisory(title, abstract, protocol_version, stage="ec")


def get_ec_advisory_status(
    title: str,
    abstract: str,
    protocol_version: str = "1.0"
) -> AdvisoryStatus:
    """Get status of EC advisory (convenience wrapper)."""
    return get_advisory_status(title, abstract, protocol_version, stage="ec")


def get_qc_advisory(
    title: str,
    abstract: str,
    protocol_version: str = "1.0"
) -> AdvisoryResult:
    """
    Get QC advisory for article (convenience wrapper).

    Uses stage="qc" to separate from EC/IC advisories.
    """
    print(f"[QC ADVISORY API] Title: {title[:30] if title else 'empty'}... | Protocol: {protocol_version}")
    return get_advisory(title, abstract, protocol_version, stage="qc")


def get_qc_advisory_status(
    title: str,
    abstract: str,
    protocol_version: str = "1.0"
) -> AdvisoryStatus:
    """Get status of QC advisory (convenience wrapper)."""
    print(f"[QC ADVISORY STATUS API] Title: {title[:30] if title else 'empty'}... | Protocol: {protocol_version}")
    return get_advisory_status(title, abstract, protocol_version, stage="qc")