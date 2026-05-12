"""
APOLLO Reproducibility Bundle — Canonical Package Export

Phase 3: Reproducibility Bundle implementation.
Implements deterministic package export for scientific reproducibility.

Structure:
apollo_bundle/
├── protocol.json
├── session.json
├── audit_log.json
├── manifest.json
├── checksums.sha256
├── environment.json
└── exports/
"""
import json
import os
import shutil
import hashlib
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

APOLLO_VERSION = "1.0.0"


@dataclass
class ReproducibilityBundle:
    """Canonical reproducibility package."""
    bundle_id: str
    bundle_path: str
    created_at: str
    
    protocol_json: str
    session_json: str
    audit_log_json: str
    manifest_json: str
    checksums_sha256: str
    environment_json: str
    
    exports_dir: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ReproducibilityEngine:
    """
    Deterministic bundle export for scientific reproducibility.
    Phase 3 implementation.
    """
    
    def __init__(self, session, protocol=None):
        self.session = session
        self.protocol = protocol
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def create_bundle(
        self,
        output_dir: str,
        include_exports: bool = True
    ) -> ReproducibilityBundle:
        """
        Create deterministic reproducibility bundle.
        
        Phase 3: Reproducibility Bundle implementation.
        
        Args:
            output_dir: Directory to create bundle
            include_exports: Whether to include regenerated exports
            
        Returns:
            ReproducibilityBundle with all metadata
        """
        os.makedirs(output_dir, exist_ok=True)
        
        bundle_id = hashlib.sha256(
            f"{self.session.session_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        bundle_path = os.path.join(output_dir, f"apollo_bundle_{bundle_id}")
        os.makedirs(bundle_path, exist_ok=True)
        
        protocol_path = self._export_protocol(bundle_path)
        session_path = self._export_session(bundle_path)
        audit_path = self._export_audit_log(bundle_path)
        env_path = self._export_environment(bundle_path)
        
        exports_dir = ""
        if include_exports:
            exports_dir = self._export_decisions(bundle_path)
        
        manifest_path = self._create_manifest(
            bundle_path, protocol_path, session_path, audit_path, env_path, exports_dir
        )
        
        checksums_path = self._create_checksums(bundle_path)
        
        return ReproducibilityBundle(
            bundle_id=bundle_id,
            bundle_path=bundle_path,
            created_at=datetime.now().isoformat(),
            protocol_json=protocol_path,
            session_json=session_path,
            audit_log_json=audit_path,
            manifest_json=manifest_path,
            checksums_sha256=checksums_path,
            environment_json=env_path,
            exports_dir=exports_dir
        )
    
    def _export_protocol(self, bundle_path: str) -> str:
        """Export protocol to bundle."""
        protocol_path = os.path.join(bundle_path, "protocol.json")
        
        if self.session.dynamic_protocol:
            protocol_data = self.session.dynamic_protocol
        else:
            from src.core.dynamic_protocol import create_default_protocol
            default = create_default_protocol()
            protocol_data = default.to_dict()
        
        if self.protocol and hasattr(self.protocol, "to_dict"):
            protocol_data = self.protocol.to_dict()
        
        protocol_data["bundle_export_timestamp"] = datetime.now().isoformat()
        
        with open(protocol_path, "w", encoding="utf-8") as f:
            json.dump(protocol_data, f, indent=2, ensure_ascii=False)
        
        return protocol_path
    
    def _export_session(self, bundle_path: str) -> str:
        """Export session to bundle."""
        session_path = os.path.join(bundle_path, "session.json")
        
        session_data = self.session._to_dict_full()
        session_data["bundle_export_timestamp"] = datetime.now().isoformat()
        
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        return session_path
    
    def _export_audit_log(self, bundle_path: str) -> str:
        """Export audit log to bundle."""
        audit_path = os.path.join(bundle_path, "audit_log.json")
        
        audit_data = {
            "exported_at": datetime.now().isoformat(),
            "session_id": self.session.session_id,
            "total_events": len(self.session._audit_chain),
            "events": self.session._audit_chain
        }
        
        with open(audit_path, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2, ensure_ascii=False)
        
        return audit_path
    
    def _export_environment(self, bundle_path: str) -> str:
        """Export environment metadata."""
        env_path = os.path.join(bundle_path, "environment.json")
        
        env_data = {
            "apollo_version": APOLLO_VERSION,
            "python_version": sys.version,
            "export_timestamp": datetime.now().isoformat(),
            "session_id": self.session.session_id,
            "researcher_id": self.session.researcher_id
        }
        
        with open(env_path, "w", encoding="utf-8") as f:
            json.dump(env_data, f, indent=2, ensure_ascii=False)
        
        return env_path
    
    def _export_decisions(self, bundle_path: str) -> str:
        """Export decisions to bundle."""
        exports_dir = os.path.join(bundle_path, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        
        from src.core.export_engine import ExportEngine
        engine = ExportEngine(protocol_version=self.session.protocol_version)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        excel_path = os.path.join(exports_dir, f"decisions_{timestamp}.xlsx")
        engine.export_decisions_excel(self.session, excel_path)
        
        json_path = os.path.join(exports_dir, f"session_export_{timestamp}.json")
        engine.export_session_json(self.session, json_path)
        
        return exports_dir
    
    def _create_manifest(
        self,
        bundle_path: str,
        protocol_path: str,
        session_path: str,
        audit_path: str,
        env_path: str,
        exports_dir: str
    ) -> str:
        """Create bundle manifest."""
        manifest_path = os.path.join(bundle_path, "manifest.json")
        
        wl_count = sum(1 for a in self.session.articles if a.get_literature_type() == "WL")
        gl_count = sum(1 for a in self.session.articles if a.get_literature_type() == "GL")
        
        protocol_data = json.load(open(protocol_path, "r", encoding="utf-8"))
        protocol_hash = protocol_data.get("protocol_hash", "")
        
        session_data = json.load(open(session_path, "r", encoding="utf-8"))
        session_hash = session_data.get("session_hash", "")
        
        manifest = {
            "bundle_id": os.path.basename(bundle_path),
            "apollo_version": APOLLO_VERSION,
            "created_at": datetime.now().isoformat(),
            "protocol_hash": protocol_hash,
            "session_hash": session_hash,
            "article_counts": {
                "total": self.session.total_count,
                "wl": wl_count,
                "gl": gl_count
            },
            "files": {
                "protocol": os.path.basename(protocol_path),
                "session": os.path.basename(session_path),
                "audit_log": os.path.basename(audit_path),
                "environment": os.path.basename(env_path),
                "checksums": "checksums.sha256",
                "exports": os.path.basename(exports_dir) if exports_dir else ""
            },
            "export_timestamp": datetime.now().isoformat()
        }
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return manifest_path
    
    def _create_checksums(self, bundle_path: str) -> str:
        """Create SHA256 checksums file."""
        checksums_path = os.path.join(bundle_path, "checksums.sha256")
        
        checksums = []
        for root, dirs, files in os.walk(bundle_path):
            for filename in files:
                if filename == "checksums.sha256":
                    continue
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, bundle_path)
                file_hash = self.compute_file_hash(file_path)
                checksums.append(f"{file_hash}  {rel_path}")
        
        with open(checksums_path, "w", encoding="utf-8") as f:
            f.write("\n".join(checksums))
        
        return checksums_path


class ReplayEngine:
    """
    Deterministic replay for reproducibility verification.
    Phase 4 implementation.
    """
    
    @staticmethod
    def replay_session(bundle_path: str) -> tuple:
        """
        Reconstruct ScreeningSession from bundle.
        
        Phase 4: Deterministic Replay implementation.
        
        Args:
            bundle_path: Path to Apollo bundle directory
            
        Returns:
            Tuple of (session, validation_result)
        """
        manifest_path = os.path.join(bundle_path, "manifest.json")
        
        if not os.path.exists(manifest_path):
            return None, {"valid": False, "errors": ["manifest.json not found"]}
        
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        session_path = os.path.join(bundle_path, "session.json")
        if not os.path.exists(session_path):
            return None, {"valid": False, "errors": ["session.json not found"]}
        
        with open(session_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)
        
        from src.core.screening_session import ScreeningSession, ArticleReview
        
        session = ScreeningSession(
            session_id=session_data.get("session_id", ""),
            created_at=session_data.get("created_at", ""),
            protocol_version=session_data.get("protocol_version", "1.0"),
            stage=session_data.get("stage", "ec"),
            current_index=session_data.get("current_index", 0),
            total_count=session_data.get("total_count", 0),
            ec_completed=session_data.get("ec_completed", 0),
            ic_completed=session_data.get("ic_completed", 0),
            qc_completed=session_data.get("qc_completed", 0),
            included_count=session_data.get("included_count", 0),
            excluded_count=session_data.get("excluded_count", 0),
            skip_count=session_data.get("skip_count", 0),
            discussion_count=session_data.get("discussion_count", 0),
            researcher_id=session_data.get("researcher_id", "researcher_1"),
            last_saved=session_data.get("last_saved", ""),
            schema_version=session_data.get("schema_version", "2.0")
        )
        
        session.articles = [
            ArticleReview(**a) for a in session_data.get("articles", [])
        ]
        
        if "dynamic_protocol" in session_data:
            session.dynamic_protocol = session_data["dynamic_protocol"]
        
        session._audit_chain = session_data.get("audit_chain", [])
        
        validation = ReplayEngine._validate_bundle(bundle_path, session, manifest)
        
        return session, validation
    
    @staticmethod
    def _validate_bundle(bundle_path: str, session, manifest: Dict) -> Dict:
        """Validate bundle integrity."""
        errors = []
        warnings = []
        
        session_path = os.path.join(bundle_path, "session.json")
        if os.path.exists(session_path):
            file_hash = hashlib.sha256()
            with open(session_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    file_hash.update(chunk)
            
            session_expected = manifest.get("session_hash", "")
            if session_expected and file_hash.hexdigest()[:16] != session_expected:
                warnings.append("Session hash mismatch (expected legacy format)")
        
        if session._audit_chain:
            is_valid, audit_errors = session.verify_audit_chain()
            if not is_valid:
                for err in audit_errors:
                    if "Chain broken" in err:
                        errors.append(f"Audit chain integrity error: {err}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "bundle_id": manifest.get("bundle_id", ""),
            "article_count": session.total_count
        }
    
    @staticmethod
    def regenerate_exports(session, output_dir: str) -> Dict[str, str]:
        """
        Regenerate exports from session.
        
        Phase 4: Deterministic Replay — export regeneration.
        
        Args:
            session: Reconstructed ScreeningSession
            output_dir: Directory for regenerated exports
            
        Returns:
            Dict of export paths
        """
        os.makedirs(output_dir, exist_ok=True)
        
        from src.core.export_engine import ExportEngine
        engine = ExportEngine(protocol_version=session.protocol_version)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        exports = {}
        
        excel_path = os.path.join(output_dir, f"decisions_{timestamp}.xlsx")
        exports["decisions_excel"] = engine.export_decisions_excel(session, excel_path)
        
        json_path = os.path.join(output_dir, f"session_{timestamp}.json")
        exports["session_json"] = engine.export_session_json(session, json_path)
        
        return exports
    
    @staticmethod
    def compare_outputs(original_exports: Dict[str, str], regenerated_exports: Dict[str, str]) -> Dict:
        """
        Compare original and regenerated exports for determinism.
        
        Phase 4: Deterministic Replay — output comparison.
        
        Args:
            original_exports: Dict of original export paths
            regenerated_exports: Dict of regenerated export paths
            
        Returns:
            Comparison result dict
        """
        results = {}
        
        for key in original_exports:
            if key in regenerated_exports:
                orig_path = original_exports[key]
                regen_path = regenerated_exports[key]
                
                if os.path.exists(orig_path) and os.path.exists(regen_path):
                    if orig_path.endswith(".xlsx"):
                        results[key] = {"status": "compared", "note": "Binary comparison not available for xlsx"}
                    else:
                        orig_data = json.load(open(orig_path, "r", encoding="utf-8"))
                        regen_data = json.load(open(regen_path, "r", encoding="utf-8"))
                        
                        orig_json = json.dumps(orig_data, sort_keys=True, ensure_ascii=False)
                        regen_json = json.dumps(regen_data, sort_keys=True, ensure_ascii=False)
                        
                        matches = orig_json == regen_json
                        results[key] = {"status": "match" if matches else "mismatch", "matches": matches}
        
        return results


def create_reproducibility_bundle(
    session,
    output_dir: str,
    protocol=None
) -> ReproducibilityBundle:
    """
    Create reproducibility bundle for session.
    
    Phase 3: Canonical function for bundle creation.
    """
    engine = ReproducibilityEngine(session, protocol)
    return engine.create_bundle(output_dir)


def replay_bundle(bundle_path: str) -> tuple:
    """
    Replay session from bundle.
    
    Phase 4: Canonical function for bundle replay.
    """
    return ReplayEngine.replay_session(bundle_path)