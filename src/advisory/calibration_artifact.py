"""
Persistent calibration artifact storage for APOLLO.

Crash-safe JSON persistence in:

  data/calibration_reports/
    protocol_<hash>/
      calibration_<timestamp>.json

Artifacts are immutable after save. Loading ignores unknown fields
for backward compatibility.

SAFEGUARDS:
- No full article text, prompts, private notes, or raw LLM responses stored
- Only derived operational/diagnostic metadata
- Crash-safe writes (temp file + fsync + os.replace)
"""
import os
import json
import time
import tempfile
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

from .advisory_models import AdvisoryConfig, AdvisoryDecision

REPORTS_BASE = Path("data/calibration_reports")


def _compute_protocol_hash(protocol_version: str, protocol=None) -> str:
    """Compute stable protocol hash from version and optional protocol object."""
    h = hashlib.sha256()
    h.update(protocol_version.encode())
    if protocol is not None:
        try:
            id_ = getattr(protocol, 'protocol_id', '') or getattr(protocol, 'id', '')
            h.update(str(id_).encode())
        except Exception:
            pass
        try:
            s = str(protocol)
            if len(s) > 0:
                h.update(s.encode())
        except Exception:
            pass
    return h.hexdigest()[:16]


def _make_calibration_id(protocol_hash: str, timestamp: str) -> str:
    return f"cal_{protocol_hash}_{timestamp.replace(':', '-').replace('.', '-')}"


def _protocol_snapshot_hash(protocol) -> str:
    """Compute a deterministic hash of the protocol's criteria."""
    if protocol is None:
        return ""
    h = hashlib.sha256()
    try:
        for key in getattr(protocol, '__dict__', {}):
            h.update(str(key).encode())
        for criteria in getattr(protocol, 'ec_criteria', []) or []:
            h.update(str(criteria).encode())
        for criteria in getattr(protocol, 'ic_criteria', []) or []:
            h.update(str(criteria).encode())
    except Exception:
        pass
    return h.hexdigest()[:16]


def _extract_sampled_article_ids(advisories: List[Dict]) -> List[str]:
    """Extract article identifiers from advisories (no full content)."""
    ids = []
    for adv in advisories:
        ids.append(adv.get("cache_key", adv.get("article_id", "")))
    return ids


def _extract_worker_metrics() -> Dict:
    """Extract operational worker metrics (no advisory content)."""
    try:
        from .advisory_metrics import get_metrics
        m = get_metrics()
        return {
            "total_generated": m.total_generated,
            "total_fallback": m.total_fallback,
            "total_errors": m.total_errors,
            "avg_generation_ms": m.avg_generation_ms,
            "cache_hit_rate": m.cache_hit_rate,
        }
    except Exception:
        return {}


def _extract_queue_metrics() -> Dict:
    """Extract operational queue metrics."""
    try:
        from .advisory_queue import get_queue_stats
        return {
            "ec": get_queue_stats("ec"),
            "ic": get_queue_stats("ic"),
        }
    except Exception:
        return {}


def build_calibration_artifact(
    report: Dict,
    runner,
    config: AdvisoryConfig,
    ec_advisories: List[Dict],
    ic_advisories: List[Dict],
    duration_seconds: float,
    ec_duration: float,
    ic_duration: float,
) -> Dict:
    """Build a calibration artifact dict from a calibration run."""
    protocol_hash = _compute_protocol_hash(
        getattr(runner, 'protocol_version', '1.0'),
        getattr(runner, 'protocol', None),
    )
    created_at = datetime.now(timezone.utc).isoformat()
    calibration_id = _make_calibration_id(protocol_hash, created_at)

    protocol = getattr(runner, 'protocol', None)
    p_hash = _protocol_snapshot_hash(protocol)

    return {
        "calibration_id": calibration_id,
        "protocol_hash": protocol_hash,
        "protocol_version": getattr(runner, 'protocol_version', '1.0'),
        "created_at": created_at,
        "screening_mode": config.screening_mode if hasattr(config, 'screening_mode') else "CALIBRATION",
        "sample_size": report.get("sample_size", 0),

        "dataset_metadata": {
            "total_articles": len(getattr(runner, 'articles', [])),
            "sampled_articles": _extract_sampled_article_ids(ec_advisories),
            "stage": "ec+ic",
        },

        "runtime_metadata": {
            "duration_seconds": round(duration_seconds, 2),
            "ec_duration_seconds": round(ec_duration, 2),
            "ic_duration_seconds": round(ic_duration, 2),
            "worker_metrics": _extract_worker_metrics(),
            "queue_metrics": _extract_queue_metrics(),
        },

        "ec_summary": report.get("ec", {}),
        "ic_summary": report.get("ic", {}),

        "criteria": report.get("criteria", {}),
        "overlap": report.get("overlap", {}),

        "diagnostics": [],

        "recommendation": {
            "status": report.get("recommendation", ""),
            "label": report.get("recommendation_label", ""),
            "reasons": [],
        },

        "determinism_metadata": {
            "replay_safe": True,
            "protocol_snapshot_hash": p_hash,
            "advisory_contract_version": "1.0.0",
        },
    }


def save_calibration_artifact(
    artifact: Dict,
    base_path: Optional[Path] = None,
) -> str:
    """Write a calibration artifact crash-safely to disk.

    Returns the absolute path to the saved file.

    Crash-safe write strategy:
    1. Write to temp file in same directory
    2. fsync the temp file
    3. os.replace (atomic on POSIX; near-atomic on Windows)
    4. On failure, clean up temp file
    """
    base = base_path or REPORTS_BASE
    protocol_hash = artifact.get("protocol_hash", "unknown")
    created_at = artifact.get("created_at", "unknown")
    safe_ts = created_at.replace(":", "-").replace(".", "-")
    cal_id = artifact.get("calibration_id", f"cal_{safe_ts}")

    dir_path = base / f"protocol_{protocol_hash}"
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / f"calibration_{safe_ts}.json"

    tmp = tempfile.NamedTemporaryFile(
        dir=str(dir_path),
        suffix='.tmp',
        delete=False,
        mode='w',
        encoding='utf-8',
    )
    try:
        json.dump(artifact, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(file_path))
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise

    return str(file_path)


def load_calibration_artifact(path: str) -> Dict:
    """Load a calibration artifact from disk.

    Unknown fields are preserved for backward compatibility.
    Missing optional fields get safe defaults.
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    validated = {
        "calibration_id": data.get("calibration_id", ""),
        "protocol_hash": data.get("protocol_hash", ""),
        "protocol_version": data.get("protocol_version", "1.0"),
        "created_at": data.get("created_at", ""),
        "screening_mode": data.get("screening_mode", "CALIBRATION"),
        "sample_size": data.get("sample_size", 0),
        "dataset_metadata": data.get("dataset_metadata", {}),
        "runtime_metadata": data.get("runtime_metadata", {}),
        "ec_summary": data.get("ec_summary", {}),
        "ic_summary": data.get("ic_summary", {}),
        "criteria": data.get("criteria", {}),
        "overlap": data.get("overlap", {}),
        "diagnostics": data.get("diagnostics", []),
        "recommendation": data.get("recommendation", {"status": "", "label": "", "reasons": []}),
        "determinism_metadata": data.get("determinism_metadata", {}),
    }

    extra = {k: v for k, v in data.items() if k not in validated}
    validated["_unknown_fields"] = extra

    return validated


def index_calibration_reports(
    base_path: Optional[Path] = None,
) -> List[Dict]:
    """Scan the reports directory and return sorted list of artifact metadata.

    Returns list of dicts with:
      - calibration_id
      - protocol_hash
      - protocol_version
      - created_at
      - sample_size
      - recommendation status
      - file_path

    Sorted newest-first.
    """
    base = base_path or REPORTS_BASE
    results = []

    if not base.exists():
        return results

    for proto_dir in sorted(base.iterdir()):
        if not proto_dir.is_dir():
            continue
        for f in sorted(proto_dir.iterdir()):
            if f.suffix != '.json' or '.tmp' in f.name:
                continue
            try:
                with open(str(f), 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                results.append({
                    "calibration_id": data.get("calibration_id", f.stem),
                    "protocol_hash": data.get("protocol_hash", ""),
                    "protocol_version": data.get("protocol_version", ""),
                    "created_at": data.get("created_at", ""),
                    "sample_size": data.get("sample_size", 0),
                    "recommendation": data.get("recommendation", {}).get("status", ""),
                    "file_path": str(f.resolve()),
                })
            except (json.JSONDecodeError, OSError):
                continue

    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results
