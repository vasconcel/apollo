"""
APOLLO Export Engine - Auditable Decision Exports
Handles all export formats with full audit trail
"""
import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import hashlib


@dataclass
class AuditEntry:
    """Single audit entry."""
    timestamp: str
    action: str
    session_id: str
    article_id: str
    stage: str
    decision: str
    researcher_id: str
    notes: str
    decision_hash: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ExportManifest:
    """Export metadata for reproducibility."""
    export_id: str
    export_type: str
    created_at: str
    protocol_version: str
    
    input_file: str
    input_checksum: str
    
    total_articles: int
    decisions_included: int
    decisions_excluded: int
    
    researcher_id: str
    session_id: str
    
    audit_entries: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ExportEngine:
    """
    Export engine with full audit trail.
    
    Key principles:
    - Every decision is logged with hash
    - Protocol version is preserved
    - Input file checksum recorded
    - Deterministic exports
    """
    
    def __init__(self, protocol_version: str = "1.0"):
        self.protocol_version = protocol_version
    
    def compute_file_checksum(self, file_path: str) -> str:
        """Compute SHA256 checksum of input file."""
        sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()[:16]
    
    def export_decisions_excel(
        self,
        session,
        output_path: str
    ) -> str:
        """Export decisions to Excel (legacy format compatible)."""
        wl_data = []
        gl_data = []
        
        for article in session.articles:
            meta = article.metadata
            
            if meta.get("literature_type") == "GL":
                gl_data.append({
                    "Posicao": meta.get("posicao", ""),
                    "Title": article.title,
                    "URL": meta.get("url", ""),
                    "Source_File": meta.get("source_file", ""),
                    "Revisor 1 EC": article.ec_stage,
                    "Revisor 1 IC": article.ic_stage,
                    "Decision": article.final_decision or self._compute_decision(article)
                })
            else:
                wl_data.append({
                    "Library": meta.get("library", ""),
                    "Global_ID": meta.get("global_id", ""),
                    "Local_ID": meta.get("local_id", ""),
                    "Title": article.title,
                    "Abstract": article.abstract,
                    "Keywords": meta.get("keywords", ""),
                    "CIs1": article.ic_stage,
                    "CEs1": article.ec_stage,
                    "Revisor 1": session.researcher_id,
                    "CIs2": "",
                    "CEs2": "",
                    "Revisor 2": "",
                    "Decision": article.final_decision or self._compute_decision(article)
                })
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            if wl_data:
                pd.DataFrame(wl_data).to_excel(writer, sheet_name="WL", index=False)
            else:
                pd.DataFrame(columns=["Library", "Global_ID", "Local_ID", "Title", "Abstract", 
                                   "Keywords", "CIs1", "CEs1", "Revisor 1", "CIs2", "CEs2", "Revisor 2", "Decision"])\
                    .to_excel(writer, sheet_name="WL", index=False)
            
            if gl_data:
                pd.DataFrame(gl_data).to_excel(writer, sheet_name="GL", index=False)
            else:
                pd.DataFrame(columns=["Posicao", "Title", "URL", "Source_File", 
                                   "Revisor 1 EC", "Revisor 1 IC", "Decision"])\
                    .to_excel(writer, sheet_name="GL", index=False)
            
            pd.DataFrame(columns=[]).to_excel(writer, sheet_name="WL Seeds for HERMES", index=False)
        
        return output_path
    
    def _compute_decision(self, article) -> str:
        """Compute final decision from stage decisions."""
        if article.ec_stage in ["", "exclude"]:
            return "EXCLUDE"
        if article.ic_stage in ["", "exclude"]:
            return "EXCLUDE"
        if article.qc_stage in ["", "exclude"]:
            return "EXCLUDE"
        
        if article.ec_stage == "needs_discussion" or article.ic_stage == "needs_discussion":
            return "NEEDS_DISCUSSION"
        
        return "INCLUDE"
    
    def export_session_json(
        self,
        session,
        output_path: str
    ) -> str:
        """Export full session JSON (includes LLM suggestions)."""
        session_dict = session._to_dict()
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(session_dict, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def export_audit_log(
        self,
        reviewer_state,
        output_path: str
    ) -> str:
        """Export audit log with all decisions."""
        audit_entries = []
        
        for decision in reviewer_state.decisions:
            entry = AuditEntry(
                timestamp=decision.timestamp,
                action="decision_made",
                session_id=decision.session_id,
                article_id=decision.article_id,
                stage=decision.stage,
                decision=decision.decision,
                researcher_id=decision.researcher_id,
                notes=decision.notes,
                decision_hash=decision.decision_hash
            )
            audit_entries.append(entry.to_dict())
        
        audit_data = {
            "exported_at": datetime.now().isoformat(),
            "protocol_version": self.protocol_version,
            "reviewer_id": reviewer_state.researcher_id,
            "session_id": reviewer_state.session_id,
            "total_decisions": len(audit_entries),
            "decisions": audit_entries
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def export_manifest(
        self,
        session,
        input_path: str,
        output_path: str
    ) -> str:
        """Export manifest with full metadata."""
        manifest = ExportManifest(
            export_id=hashlib.sha256(
                f"{session.session_id}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:8],
            export_type="session_review",
            created_at=datetime.now().isoformat(),
            protocol_version=session.protocol_version,
            input_file=input_path,
            input_checksum=self.compute_file_checksum(input_path),
            total_articles=session.total_count,
            decisions_included=session.included_count,
            decisions_excluded=session.excluded_count,
            researcher_id=session.researcher_id,
            session_id=session.session_id
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)
        
        return output_path
    
    def export_all(
        self,
        session,
        reviewer_state,
        input_path: str,
        output_dir: str = "exports"
    ) -> Dict[str, str]:
        """Export all formats."""
        os.makedirs(output_dir, exist_ok=True)
        
        session_id = session.session_id
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        exports = {}
        
        excel_path = os.path.join(output_dir, f"decisions_{timestamp}.xlsx")
        exports["decisions_excel"] = self.export_decisions_excel(session, excel_path)
        
        json_path = os.path.join(output_dir, f"session_{timestamp}.json")
        exports["session_json"] = self.export_session_json(session, json_path)
        
        audit_path = os.path.join(output_dir, f"audit_{timestamp}.json")
        exports["audit_log"] = self.export_audit_log(reviewer_state, audit_path)
        
        manifest_path = os.path.join(output_dir, f"manifest_{timestamp}.json")
        exports["manifest"] = self.export_manifest(session, input_path, manifest_path)
        
        return exports


def create_export(
    session,
    reviewer_state,
    input_path: str,
    output_dir: str = "exports"
) -> Dict[str, str]:
    """Convenience function for full export."""
    engine = ExportEngine(protocol_version=session.protocol_version)
    return engine.export_all(session, reviewer_state, input_path, output_dir)