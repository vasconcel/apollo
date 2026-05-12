"""
APOLLO Decision Engine - ATLAS Orchestrator

Orchestrates WL/GL article processing through EC/IC/QC pipeline.
Delegates loading, evaluation, and export to specialized modules.
Replaces the monolithic atlas_processor.py with decomposed architecture.
"""
import pandas as pd
import os
import time
from typing import Dict, List, Tuple, Optional, Any

from src.core.article_record import ArticleRecord, EligibilityDecision, QualityDecision
from src.core.ingestion_engine import ATLASLoader
from src.core.criteria_evaluator import EligibilityDecision as ED, QualityDecision as QD, ExclusionCriteria, InclusionCriteria, QualityCriteria
from src.core.year_extraction import extract_year, compute_metadata_completeness


class APOLLODecisionEngine:
    """
    Main decision engine that processes ATLAS data through EC/IC/QC pipeline.
    Protocol Support: Configurable via ProtocolEngine.
    """
    
    def __init__(self, enable_llm_reasoning: bool = True, protocol: Dict = None):
        self.enable_llm_reasoning = enable_llm_reasoning
        self.protocol = protocol
        
        self._protocol_engine = None
        if protocol:
            from src.core.protocol_engine import ProtocolEngine
            self._protocol_engine = ProtocolEngine(protocol)
    
    def _precompute_duplicate_global_ids(self, wl_df: pd.DataFrame) -> set:
        global_ids = wl_df['Global_ID'].dropna().astype(str)
        global_ids = global_ids[global_ids != '']
        value_counts = global_ids.value_counts()
        return set(value_counts[value_counts > 1].index)
    
    def process_wl_articles(self, wl_df: pd.DataFrame) -> List[ArticleRecord]:
        """Process White Literature articles."""
        duplicate_global_ids = self._precompute_duplicate_global_ids(wl_df)
        seen_ids_this_run = set()
        results = []
        
        for _, row in wl_df.iterrows():
            year, year_source = extract_year(
                str(row.get("Title", "")),
                str(row.get("Abstract", "")),
                row.get("Year")
            )
            
            row_metadata = row.to_dict()
            row_metadata["year_source"] = year_source
            row_metadata["metadata_completeness"] = compute_metadata_completeness(row_metadata)
            row_metadata["literature_provenance"] = "WL"
            row_metadata["source_sheet"] = "White Literature"
            row_metadata["authors"] = str(row.get("Authors", ""))
            
            record = ArticleRecord(
                literature_type="WL",
                source_sheet="White Literature",
                library=str(row.get("Library", "")),
                global_id=str(row.get("Global_ID", "")),
                local_id=str(row.get("Local_ID", "")),
                title=str(row.get("Title", "")),
                abstract=str(row.get("Abstract", "")),
                keywords=str(row.get("Keywords", "")),
                authors=str(row.get("Authors", "")),
                year=year,
                metadata=row_metadata
            )
            
            is_duplicate = (record.global_id in duplicate_global_ids and 
                           record.global_id in seen_ids_this_run) and ExclusionCriteria.ENABLE_DUPLICATE_CHECK
            duplicate_flag = str(row.get("Duplicate_Flag", row.get("duplicate_flag", "")))
            
            ec_result = self._evaluate_ec(record, year, is_duplicate, duplicate_flag)
            record.ec_decision = ec_result.to_display()
            if record.global_id: seen_ids_this_run.add(record.global_id)
            
            if ec_result.decision == "include":
                ic_result = self._evaluate_ic(record)
                record.ic_decision = ic_result.to_display()
                
                if ic_result.decision == "include":
                    qc_result = self._evaluate_qc(record, "WL")
                    record.qc_score = qc_result.to_display()
                    record.final_decision = "INCLUDE" if qc_result.decision == "include" else "EXCLUDE"
                else:
                    record.qc_score = "N/A"
                    record.final_decision = "EXCLUDE"
            else:
                record.ic_decision = "N/A"
                record.qc_score = "N/A"
                record.final_decision = "EXCLUDE"
            
            results.append(record)
        return results
    
    def process_gl_articles(self, gl_df: pd.DataFrame) -> List[ArticleRecord]:
        """
        Process Grey Literature articles.
        METHODOLOGICAL FIX (v1.0.0): GL articles passing EC are marked as PENDING
        for IC/QC to allow manual review via URL, preserving them in the HITL funnel.
        """
        results = []
        
        for _, row in gl_df.iterrows():
            row_metadata = row.to_dict()
            row_metadata["year_source"] = "missing"
            row_metadata["metadata_completeness"] = compute_metadata_completeness(row_metadata)
            row_metadata["literature_provenance"] = "GL"
            row_metadata["source_sheet"] = "Grey Literature"
            
            record = ArticleRecord(
                literature_type="GL",
                source_sheet="Grey Literature",
                posicao=str(row.get("Posicao", "") or row.get("#", "")),
                title=str(row.get("Title", "")),
                url=str(row.get("URL", "")),
                source_file=str(row.get("Source_File", "")),
                metadata=row_metadata
            )
            
            title = record.title
            abstract = ""
            
            ec_result = self._evaluate_ec(record, None, False, "")
            record.ec_decision = ec_result.to_display()
            
            if ec_result.decision == "include":
                record.ic_decision = "PENDING"
                record.qc_score = "PENDING"
                record.final_decision = "PENDING"
            else:
                record.ic_decision = "N/A"
                record.qc_score = "N/A"
                record.final_decision = "EXCLUDE"
            
            results.append(record)
        
        return results
    
    def _evaluate_ec(self, record: ArticleRecord, year: Optional[int], is_duplicate: bool, duplicate_flag: str) -> EligibilityDecision:
        """Evaluate exclusion criteria using protocol or fallback."""
        if self._protocol_engine:
            data = {
                "title": record.title, "abstract": record.abstract, "year": year,
                "global_id": record.global_id, "text_combined": f"{record.title} {record.abstract}".lower(),
                "duplicate_flag": duplicate_flag
            }
            decision, criterion, reason = self._protocol_engine.evaluate_ec(data, "WL", is_duplicate)
            return EligibilityDecision(decision, criterion, reason)
        else:
            return ExclusionCriteria.evaluate(record.title, record.abstract, year, True, is_duplicate, duplicate_flag)
    
    def _evaluate_ic(self, record: ArticleRecord) -> EligibilityDecision:
        """Evaluate inclusion criteria using protocol or fallback."""
        if self._protocol_engine:
            data = {"title": record.title, "abstract": record.abstract, "text_combined": f"{record.title} {record.abstract}".lower()}
            decision, criterion, reason = self._protocol_engine.evaluate_ic(data, "WL")
            return EligibilityDecision(decision, criterion, reason)
        else:
            return InclusionCriteria.evaluate(record.title, record.abstract)
    
    def _evaluate_qc(self, record: ArticleRecord, literature_type: str) -> QualityDecision:
        """Evaluate quality criteria using protocol or fallback."""
        if self._protocol_engine:
            data = {"title": record.title, "abstract": record.abstract, "text_combined": f"{record.title} {record.abstract}".lower()}
            decision, scores, total = self._protocol_engine.evaluate_qc(data, literature_type)
            return QualityDecision(scores=scores, total_score=total, decision=decision, literature_type=literature_type)
        else:
            return QualityCriteria.evaluate(record.title, record.abstract, literature_type)
    
    def export_to_excel(self, output_path: str, wl_results: List[ArticleRecord],
                        gl_results: List[ArticleRecord], wl_snowball: List[ArticleRecord] = None):
        """Export results to Excel with EXACT column structure expected by PRISMA."""
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            wl_columns = ["Library", "Global_ID", "Local_ID", "Title", "Abstract", "Keywords",
                          "CIs1", "CEs1", "Revisor 1", "CIs2", "CEs2", "Revisor 2", "Decision"]
            wl_data = [{
                "Library": r.library, "Global_ID": r.global_id, "Local_ID": r.local_id,
                "Title": r.title, "Abstract": r.abstract, "Keywords": r.keywords,
                "CIs1": r.ic_decision, "CEs1": r.ec_decision, "Revisor 1": "APOLLO",
                "CIs2": "", "CEs2": "", "Revisor 2": "", "Decision": r.final_decision
            } for r in wl_results]
            pd.DataFrame(wl_data, columns=wl_columns).to_excel(writer, sheet_name="WL", index=False)
            
            gl_columns = ["Posicao", "Title", "URL", "Source_File", "Revisor 1 EC", "Revisor 1 IC", "Decision"]
            gl_data = [{
                "Posicao": r.posicao, "Title": r.title, "URL": r.url, "Source_File": r.source_file,
                "Revisor 1 EC": r.ec_decision, "Revisor 1 IC": r.ic_decision, "Decision": r.final_decision
            } for r in gl_results]
            pd.DataFrame(gl_data, columns=gl_columns).to_excel(writer, sheet_name="GL", index=False)
            
            sb_data = [] if not wl_snowball else [{
                "Library": r.library, "Global_ID": r.global_id, "Local_ID": r.local_id,
                "Title": r.title, "Abstract": r.abstract, "Keywords": r.keywords,
                "CIs1": r.ic_decision, "CEs1": r.ec_decision, "Revisor 1": "APOLLO",
                "CIs2": "", "CEs2": "", "Revisor 2": "", "Decision": r.final_decision
            } for r in wl_snowball]
            pd.DataFrame(sb_data, columns=wl_columns).to_excel(writer, sheet_name="WL Seeds for HERMES", index=False)


def process_atlas_file(input_path: str, output_path: str, enable_llm: bool = True):
    """Main CLI entry point - process ATLAS file deterministically."""
    start_time = time.time()
    
    wl_df, gl_df = ATLASLoader.load_atlas_file(input_path)
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    engine = APOLLODecisionEngine(enable_llm_reasoning=enable_llm)
    wl_results = engine.process_wl_articles(wl_df)
    gl_results = engine.process_gl_articles(gl_df)
    
    engine.export_to_excel(output_path, wl_results, gl_results)
    return wl_results, gl_results


def export_apollo_selection_criteria(input_path: str, output_filename: str = "APOLLO_Selection_Criteria.xlsx", enable_llm: bool = True) -> str:
    """SINGLE CLEAN EXPORT FUNCTION."""
    input_dir = os.path.dirname(input_path) or "."
    output_path = os.path.join(input_dir, output_filename)
    
    process_atlas_file(input_path, output_path, enable_llm)
    return output_path


def create_screening_session(
    input_path: str,
    protocol: Dict = None,
    enable_llm_suggestions: bool = True,
    researcher_id: str = "researcher_1"
) -> Tuple[Any, Any, List[ArticleRecord], List[ArticleRecord]]:
    """
    Create screening session for human-in-the-loop review.
    Initiates a session where articles await explicit human decision.
    """
    from src.core.screening_session import create_session
    from src.core.reviewer_state import ReviewerState
    
    wl_df, gl_df = ATLASLoader.load_atlas_file(input_path)
    wl_df = ATLASLoader.normalize_wl_columns(wl_df)
    gl_df = ATLASLoader.normalize_gl_columns(gl_df)
    
    engine = APOLLODecisionEngine(enable_llm_reasoning=False, protocol=protocol)
    
    wl_results = engine.process_wl_articles(wl_df)
    gl_results = engine.process_gl_articles(gl_df)
    
    all_records = wl_results + gl_results
    
    session = create_session(
        article_records=all_records,
        protocol_version=protocol.get("protocol_version", "1.0") if protocol else "1.0"
    )
    
    reviewer_state = ReviewerState(
        researcher_id=researcher_id,
        session_id=session.session_id,
        stage="ec"
    )
    
    return session, reviewer_state, wl_results, gl_results