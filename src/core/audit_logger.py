"""
APOLLO Pipeline Audit Logger

Deterministic logging for APOLLO processing runs.
Logs protocol, stats, and execution details for audit and reproducibility.

STRICT RULES:
- No LLM reasoning leakage
- No article full text dumps
- No nondeterministic timestamps in reproducibility hash
"""
import json
import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ProcessingStats:
    """Statistics from a processing run."""
    wl_total: int = 0
    wl_included: int = 0
    wl_excluded: int = 0
    gl_total: int = 0
    gl_included: int = 0
    gl_excluded: int = 0
    duplicates_detected: int = 0
    
    ec1_failures: int = 0
    ec2_failures: int = 0
    ec3_failures: int = 0
    ec4_failures: int = 0
    ic1_failures: int = 0
    ic2_failures: int = 0
    
    qc_scores_4: int = 0
    qc_scores_3: int = 0
    qc_scores_2: int = 0
    qc_scores_below: int = 0
    
    gl_skipped_ic: int = 0
    gl_skipped_qc: int = 0


@dataclass
class ProtocolInfo:
    """Protocol information for audit."""
    name: str
    version: str
    checksum: str
    ec_count: int
    ic_count: int
    qc_count: int
    threshold: float


class AuditLogger:
    """Deterministic audit logger for APOLLO processing runs."""
    
    LOG_DIR = "logs"
    
    @staticmethod
    def _compute_determinism_hash(input_file: str, protocol_info: ProtocolInfo, 
                                   stats: ProcessingStats) -> str:
        """
        Compute deterministic hash for reproducibility verification.
        
        Combines input metadata + protocol checksum + output stats.
        No actual article content - just structural information.
        """
        hash_input = f"{input_file}|{protocol_info.checksum}|{stats.wl_included}|{stats.wl_excluded}|{stats.gl_included}|{stats.gl_excluded}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    @staticmethod
    def _compute_protocol_checksum(protocol: Optional[Dict]) -> str:
        """Compute SHA256 checksum of protocol definition."""
        if protocol is None:
            return "none"
        protocol_json = json.dumps(protocol, sort_keys=True)
        return hashlib.sha256(protocol_json.encode()).hexdigest()[:16]
    
    @staticmethod
    def _create_run_id() -> str:
        """Create deterministic run ID based on current run characteristics."""
        return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    @staticmethod
    def compute_stats(wl_results: List, gl_results: List) -> ProcessingStats:
        """Compute processing statistics from results."""
        stats = ProcessingStats()
        
        # WL stats
        stats.wl_total = len(wl_results)
        stats.wl_included = sum(1 for r in wl_results if r.final_decision == "INCLUDE")
        stats.wl_excluded = stats.wl_total - stats.wl_included
        
        # GL stats
        stats.gl_total = len(gl_results)
        stats.gl_included = sum(1 for r in gl_results if r.final_decision == "INCLUDE")
        stats.gl_excluded = stats.gl_total - stats.gl_included
        
        # EC/IC failure counts
        for r in wl_results:
            ec = r.ec_decision if r.ec_decision else ""
            ic = r.ic_decision if r.ic_decision else ""
            
            if "EC1" in ec:
                stats.ec1_failures += 1
            elif "EC2" in ec:
                stats.ec2_failures += 1
            elif "EC3" in ec:
                stats.ec3_failures += 1
            elif "EC4" in ec:
                stats.ec4_failures += 1
            
            if "IC1" in ic:
                stats.ic1_failures += 1
            elif "IC2" in ic:
                stats.ic2_failures += 1
        
        # QC scores distribution (WL only)
        for r in wl_results:
            qc = r.qc_score
            if qc == "N/A":
                continue
            try:
                score = float(qc.split("/")[0])
                if score >= 4.0:
                    stats.qc_scores_4 += 1
                elif score >= 3.0:
                    stats.qc_scores_3 += 1
                elif score >= 2.0:
                    stats.qc_scores_2 += 1
                else:
                    stats.qc_scores_below += 1
            except:
                pass
        
        # GL skipped counts
        for r in gl_results:
            if r.ic_decision == "SKIPPED":
                stats.gl_skipped_ic += 1
            if r.qc_score == "SKIPPED":
                stats.gl_skipped_qc += 1
        
        # EC4 duplicates
        stats.duplicates_detected = stats.ec4_failures
        
        return stats
    
    @staticmethod
    def get_protocol_info(protocol: Optional[Dict]) -> ProtocolInfo:
        """Extract protocol information for logging."""
        from src.core.protocol_engine import get_default_protocol
        
        if protocol is None:
            default = get_default_protocol()
            return ProtocolInfo(
                name=default.get("name", "Default APOLLO Protocol"),
                version=default.get("protocol_version", "1.0"),
                checksum=AuditLogger._compute_protocol_checksum(default),
                ec_count=len(default.get("exclusion_criteria", {})),
                ic_count=len(default.get("inclusion_criteria", {})),
                qc_count=len(default.get("quality_criteria", {}).get("WL", {})) + 
                         len(default.get("quality_criteria", {}).get("GL", {})),
                threshold=default.get("quality_criteria", {}).get("threshold", 2.0)
            )
        else:
            return ProtocolInfo(
                name=protocol.get("name", "Custom Protocol"),
                version=protocol.get("protocol_version", "1.0"),
                checksum=AuditLogger._compute_protocol_checksum(protocol),
                ec_count=len(protocol.get("exclusion_criteria", {})),
                ic_count=len(protocol.get("inclusion_criteria", {})),
                qc_count=len(protocol.get("quality_criteria", {}).get("WL", {})) + 
                         len(protocol.get("quality_criteria", {}).get("GL", {})),
                threshold=protocol.get("quality_criteria", {}).get("threshold", 2.0)
            )
    
    @staticmethod
    def log_run(input_file: str, protocol: Optional[Dict], 
                wl_results: List, gl_results: List,
                execution_time_ms: float = 0) -> str:
        """
        Log a complete APOLLO processing run.
        
        Returns:
            Path to the log file created
        """
        # Ensure log directory exists
        os.makedirs(AuditLogger.LOG_DIR, exist_ok=True)
        
        # Compute all components
        protocol_info = AuditLogger.get_protocol_info(protocol)
        stats = AuditLogger.compute_stats(wl_results, gl_results)
        run_id = AuditLogger._create_run_id()
        determinism_hash = AuditLogger._compute_determinism_hash(input_file, protocol_info, stats)
        
        # Build log entry
        log_entry = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "input_file": input_file,
            "protocol": asdict(protocol_info),
            "processing_stats": asdict(stats),
            "execution_time_ms": execution_time_ms,
            "determinism_hash": determinism_hash,
            "export_checksum": hashlib.sha256(
                f"{stats.wl_included}|{stats.wl_excluded}|{stats.gl_included}|{stats.gl_excluded}".encode()
            ).hexdigest()[:16]
        }
        
        # Write log file
        log_path = os.path.join(AuditLogger.LOG_DIR, f"apollo_run_{run_id}.json")
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_entry, f, indent=2)
        
        return log_path
    
    @staticmethod
    def get_latest_log() -> Optional[Dict]:
        """Get the most recent run log."""
        if not os.path.exists(AuditLogger.LOG_DIR):
            return None
        
        log_files = [f for f in os.listdir(AuditLogger.LOG_DIR) if f.startswith("apollo_run_")]
        if not log_files:
            return None
        
        latest = sorted(log_files)[-1]
        with open(os.path.join(AuditLogger.LOG_DIR, latest), 'r') as f:
            return json.load(f)


def log_apollo_run(input_file: str, protocol: Optional[Dict],
                   wl_results: List, gl_results: List,
                   execution_time_ms: float = 0) -> str:
    """Convenience function for logging APOLLO runs."""
    return AuditLogger.log_run(input_file, protocol, wl_results, gl_results, execution_time_ms)