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

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False


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
        output_path: str,
        ec_criteria_descriptions: Optional[Dict[str, str]] = None,
        ic_criteria_descriptions: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Export decisions to Excel with STRICT WL/GL separation.
        Uses xlsxwriter for styling and cell comments.
        
        WL Sheet: 13-column schema (Researcher 1 Package)
        GL Sheet: 7-column schema (Researcher 1 Package)
        
        SPRINT 7.17 Updates:
        - Full criteria descriptions in header comments
        - Sheet tab coloring (WL=Cyan, GL=Orange)
        - GL IC stage: "PENDING" for GL passing EC (no abstracts)
        - NaN values in Abstract replaced with empty string
        """
        if not XLSXWRITER_AVAILABLE:
            raise ImportError(
                "xlsxwriter library not available. Install with: pip install xlsxwriter"
            )
        
        wl_articles = session.get_wl_articles()
        gl_articles = session.get_gl_articles()
        
        wl_columns = ["Library", "Global_ID", "Local_ID", "Title", "Abstract", "Keywords",
                      "CIs1", "CEs1", "Revisor 1", "CIs2", "CEs2", "Revisor 2", "Decision"]
        gl_columns = ["Posicao", "Title", "URL", "Source_File", "Revisor 1 EC", "Revisor 1 IC", "Decision"]
        
        workbook = xlsxwriter.Workbook(output_path)
        
        wl_format_header = workbook.add_format({
            'bold': True, 'bg_color': '#1E3A5F', 'font_color': 'white',
            'border': 1, 'font_size': 10
        })
        wl_format_data = workbook.add_format({'border': 1, 'font_size': 9})
        wl_format_cis1_green = workbook.add_format({
            'border': 1, 'font_size': 9, 'bg_color': '#C6EFCE', 'font_color': '#006100'
        })
        wl_format_ces1_red = workbook.add_format({
            'border': 1, 'font_size': 9, 'bg_color': '#FFC7CE', 'font_color': '#9C0006'
        })
        
        gl_format_header = workbook.add_format({
            'bold': True, 'bg_color': '#1E3A5F', 'font_color': 'white',
            'border': 1, 'font_size': 10
        })
        gl_format_data = workbook.add_format({'border': 1, 'font_size': 9})
        gl_format_ec_green = workbook.add_format({
            'border': 1, 'font_size': 9, 'bg_color': '#C6EFCE', 'font_color': '#006100'
        })
        gl_format_ic_green = workbook.add_format({
            'border': 1, 'font_size': 9, 'bg_color': '#C6EFCE', 'font_color': '#006100'
        })
        gl_format_pending = workbook.add_format({
            'border': 1, 'font_size': 9, 'bg_color': '#FFEB9C', 'font_color': '#9C5700'
        })
        
        ws_wl = workbook.add_worksheet("WL")
        ws_wl.set_column('A:M', 18)
        ws_wl.set_tab_color('#00C8D7')
        
        for col_idx, col_name in enumerate(wl_columns):
            ws_wl.write(0, col_idx, col_name, wl_format_header)
        
        ic_comment_text = "INCLUSION CRITERIA CODES:\n" + "\n".join(
            [f"{k}: {v}" for k, v in (ic_criteria_descriptions or {"IC1": "Addresses R&S practices", "IC2": "Reports empirical findings", "IC3": "Focuses on software industry"}).items()]
        )
        ec_comment_text = "EXCLUSION CRITERIA CODES:\n" + "\n".join(
            [f"{k}: {v}" for k, v in (ec_criteria_descriptions or {"EC1": "Not empirical SE research", "EC2": "Published before 2015", "EC3": "Not peer-reviewed"}).items()]
        )
        ws_wl.write_comment(6, 0, ic_comment_text)
        ws_wl.write_comment(7, 0, ec_comment_text)
        
        row_idx = 1
        for article in wl_articles:
            meta = article.metadata if article.metadata else {}
            final_dec = article.final_decision if article.final_decision else self._compute_decision(article)
            
            cis1_value = article.cis1 if article.cis1 else (article.ic_stage if article.ic_stage else "PENDING")
            ces1_value = article.ces1 if article.ces1 else (article.ec_stage if article.ec_stage else "PENDING")
            
            abstract_text = article.abstract if article.abstract else ""
            if isinstance(abstract_text, float) or (isinstance(abstract_text, str) and abstract_text.lower() in ['nan', 'none', 'n/a']):
                abstract_text = ""
            
            def safe_str(val, default=""):
                if val is None:
                    return default
                if isinstance(val, float):
                    if str(val).lower() in ['nan', 'none', 'inf']:
                        return default
                    return str(int(val)) if val == int(val) else str(val)
                if isinstance(val, str):
                    return val if val.lower() not in ['nan', 'none', 'n/a', ''] else default
                return str(val)
            
            ws_wl.write(row_idx, 0, safe_str(meta.get("library", "")), wl_format_data)
            ws_wl.write(row_idx, 1, safe_str(meta.get("global_id", "")), wl_format_data)
            ws_wl.write(row_idx, 2, safe_str(meta.get("local_id", "")), wl_format_data)
            ws_wl.write(row_idx, 3, safe_str(article.title, "Untitled"), wl_format_data)
            ws_wl.write(row_idx, 4, safe_str(abstract_text), wl_format_data)
            ws_wl.write(row_idx, 5, safe_str(meta.get("keywords", "")), wl_format_data)
            
            cis1_format = wl_format_cis1_green if cis1_value not in ["", "PENDING", "NO"] else wl_format_data
            ws_wl.write(row_idx, 6, cis1_value, cis1_format)
            
            ces1_format = wl_format_ces1_red if ces1_value not in ["", "PENDING", "NO"] else wl_format_data
            ws_wl.write(row_idx, 7, ces1_value if ces1_value else "", ces1_format)
            
            ws_wl.write(row_idx, 8, article.revisor1 if article.revisor1 else session.researcher_id, wl_format_data)
            ws_wl.write(row_idx, 9, "", wl_format_data)
            ws_wl.write(row_idx, 10, "", wl_format_data)
            ws_wl.write(row_idx, 11, "", wl_format_data)
            ws_wl.write(row_idx, 12, final_dec, wl_format_data)
            
            row_idx += 1
        
        ws_gl = workbook.add_worksheet("GL")
        ws_gl.set_column('A:G', 20)
        ws_gl.set_tab_color('#FFB020')
        
        for col_idx, col_name in enumerate(gl_columns):
            ws_gl.write(0, col_idx, col_name, gl_format_header)
        
        row_idx = 1
        for article in gl_articles:
            meta = article.metadata if article.metadata else {}
            final_dec = article.final_decision if article.final_decision else self._compute_decision(article)
            
            ces1_value = article.ces1 if article.ces1 else (article.ec_stage if article.ec_stage else "PENDING")
            
            ec_passed = article.ec_stage == "include" or ces1_value not in ["", "PENDING", "NO", "exclude"]
            if ec_passed and not article.cis1 and article.ic_stage != "exclude":
                cis1_value = "PENDING"
            else:
                cis1_value = article.cis1 if article.cis1 else (article.ic_stage if article.ic_stage else "PENDING")
            
            def safe_str(val, default=""):
                if val is None:
                    return default
                if isinstance(val, float):
                    if str(val).lower() in ['nan', 'none', 'inf']:
                        return default
                    return str(int(val)) if val == int(val) else str(val)
                if isinstance(val, str):
                    return val if val.lower() not in ['nan', 'none', 'n/a', ''] else default
                return str(val)
            
            ws_gl.write(row_idx, 0, safe_str(meta.get("posicao", meta.get("#", ""))), gl_format_data)
            ws_gl.write(row_idx, 1, safe_str(article.title, "Untitled"), gl_format_data)
            ws_gl.write(row_idx, 2, safe_str(meta.get("url", "")), gl_format_data)
            ws_gl.write(row_idx, 3, safe_str(meta.get("source_file", "")), gl_format_data)
            
            ec_format = gl_format_ec_green if ces1_value not in ["", "PENDING", "NO"] else gl_format_data
            ws_gl.write(row_idx, 4, ces1_value, ec_format)
            
            if cis1_value == "PENDING":
                ic_format = gl_format_pending
            elif cis1_value not in ["", "PENDING", "NO"]:
                ic_format = gl_format_ic_green
            else:
                ic_format = gl_format_data
            ws_gl.write(row_idx, 5, cis1_value, ic_format)
            
            ws_gl.write(row_idx, 6, final_dec, gl_format_data)
            
            row_idx += 1
        
        workbook.close()
        
        return output_path
    
    def _compute_decision(self, article) -> str:
        """Compute final decision from stage decisions (Reviewer 1 only - no QC)."""
        if article.ec_stage in ["", "exclude"]:
            return "EXCLUDE"
        if article.ic_stage in ["", "exclude"]:
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