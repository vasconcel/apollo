"""
APOLLO Calibration Engine - Inter-Rater Reliability Exports
Exports calibration-ready data for Cohen's Kappa analysis
"""
import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class CalibrationPair:
    """Pair of decisions for inter-rater reliability."""
    article_id: str
    title: str
    
    reviewer_1_decision: str
    reviewer_1_stage: str
    
    reviewer_2_decision: str
    reviewer_2_stage: str
    
    consensus: str = ""
    disagreed: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CalibrationData:
    """Calibration dataset for Kappa analysis."""
    session_id: str
    protocol_version: str
    created_at: str
    
    stage: str
    
    pairs: List[CalibrationPair] = field(default_factory=list)
    
    reviewer_1_id: str = "reviewer_1"
    reviewer_2_id: str = "reviewer_2"
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to DataFrame for analysis."""
        data = []
        for p in self.pairs:
            data.append({
                "article_id": p.article_id,
                "title": p.title[:60] + "..." if len(p.title) > 60 else p.title,
                "reviewer_1": p.reviewer_1_decision,
                "reviewer_2": p.reviewer_2_decision,
                "consensus": p.consensus,
                "disagreed": p.disagreed
            })
        return pd.DataFrame(data)
    
    def compute_kappa_input(self) -> Tuple[int, int, int, int]:
        """
        Compute 2x2 contingency table for Cohen's Kappa.
        
        Returns: (a, b, c, d)
        - a: Both agree include
        - b: R1 include, R2 exclude
        - c: R1 exclude, R2 include
        - d: Both agree exclude
        """
        a = b = c = d = 0
        
        for p in self.pairs:
            r1 = p.reviewer_1_decision
            r2 = p.reviewer_2_decision
            
            if r1 == "include" and r2 == "include":
                a += 1
            elif r1 == "include" and r2 == "exclude":
                b += 1
            elif r1 == "exclude" and r2 == "include":
                c += 1
            else:  # both exclude
                d += 1
        
        return a, b, c, d
    
    def calculate_cohens_kappa(self) -> float:
        """Calculate Cohen's Kappa."""
        a, b, c, d = self.compute_kappa_input()
        
        n = a + b + c + d
        if n == 0:
            return 0.0
        
        p_o = (a + d) / n
        
        p_e = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
        
        if p_e == 1.0:
            return 1.0
        
        kappa = (p_o - p_e) / (1 - p_e)
        
        return round(kappa, 3)


class CalibrationEngine:
    """
    Calibration engine for inter-rater reliability.
    
    Generates exports ready for Cohen's Kappa analysis.
    Supports both:
    - Single researcher (sequential review for calibration)
    - Two independent researchers
    """
    
    def __init__(self, protocol_version: str = "1.0"):
        self.protocol_version = protocol_version
    
    def create_calibration_pairs(
        self,
        decisions_r1: List[Dict],
        decisions_r2: List[Dict],
        stage: str
    ) -> CalibrationData:
        """Create calibration pairs from two sets of decisions."""
        pairs = []
        
        id_map_r2 = {d["article_id"]: d["decision"] for d in decisions_r2}
        
        for d1 in decisions_r1:
            article_id = d1["article_id"]
            r2_decision = id_map_r2.get(article_id, "")
            
            r1_decision = d1.get("decision", "skip")
            r2_dec = r2_decision
            
            consensus = r1_decision if r1_decision == r2_dec and r1_decision != "" else ""
            disagreed = r1_decision != r2_dec and r1_decision != "" and r2_dec != ""
            
            pairs.append(CalibrationPair(
                article_id=article_id,
                title=d1.get("title", "")[:100],
                reviewer_1_decision=r1_decision,
                reviewer_1_stage=stage,
                reviewer_2_decision=r2_dec,
                reviewer_2_stage=stage,
                consensus=consensus,
                disagreed=disagreed
            ))
        
        return CalibrationData(
            session_id=decisions_r1[0].get("session_id", "unknown") if decisions_r1 else "unknown",
            protocol_version=self.protocol_version,
            created_at=datetime.now().isoformat(),
            stage=stage,
            pairs=pairs
        )
    
    def export_calibration_excel(
        self,
        calibration_data: CalibrationData,
        output_path: str
    ) -> str:
        """Export calibration data to Excel."""
        df = calibration_data.to_dataframe()
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="Calibration", index=False)
            
            kappa = calibration_data.calculate_cohens_kappa()
            a, b, c, d = calibration_data.compute_kappa_input()
            
            summary = pd.DataFrame([{
                "Metric": ["Cohen's Kappa", "Agreement (Po)", "Both Include", "Both Exclude", "Disagreed"],
                "Value": [kappa, (a+d)/(a+b+c+d), a, d, b+c]
            }])
            summary.to_excel(writer, sheet_name="Summary", index=False)
        
        return output_path
    
    def export_kappa_matrix(
        self,
        calibration_data: CalibrationData,
        output_path: str
    ) -> Dict:
        """Export Kappa input matrix as JSON."""
        a, b, c, d = calibration_data.compute_kappa_input()
        
        matrix = {
            "session_id": calibration_data.session_id,
            "stage": calibration_data.stage,
            "protocol_version": calibration_data.protocol_version,
            "created_at": calibration_data.created_at,
            "contingency_2x2": {
                "include_include": a,
                "include_exclude": b,
                "exclude_include": c,
                "exclude_exclude": d
            },
            "cohens_kappa": calibration_data.calculate_cohens_kappa(),
            "agreement_rate": (a + d) / (a + b + c + d) if (a + b + c + d) > 0 else 0
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(matrix, f, indent=2)
        
        return matrix
    
    def create_sequential_pairs(
        self,
        decisions_1: List[Dict],
        decisions_2: List[Dict],
        stage: str
    ) -> CalibrationData:
        """
        Create pairs for sequential (same reviewer) calibration.
        
        For single researcher doing calibration review:
        - First pass: decisions_1
        - Second pass: decisions_2
        """
        return self.create_calibration_pairs(
            decisions_1, decisions_2, stage
        )


def export_for_calibration(
    session_1_path: str,
    session_2_path: str,
    output_path: str,
    stage: str = "ec"
) -> Dict:
    """Export two sessions for calibration analysis."""
    with open(session_1_path, "r", encoding="utf-8") as f:
        data1 = json.load(f)
    
    with open(session_2_path, "r", encoding="utf-8") as f:
        data2 = json.load(f)
    
    decisions_1 = [
        {"article_id": a["article_id"], "decision": a.get(f"{stage}_stage", ""), "title": a["title"]}
        for a in data1.get("articles", [])
    ]
    
    decisions_2 = [
        {"article_id": a["article_id"], "decision": a.get(f"{stage}_stage", ""), "title": a["title"]}
        for a in data2.get("articles", [])
    ]
    
    engine = CalibrationEngine(
        protocol_version=data1.get("protocol_version", "1.0")
    )
    
    calib_data = engine.create_calibration_pairs(
        decisions_1, decisions_2, stage
    )
    
    return {
        "excel_path": engine.export_calibration_excel(calib_data, output_path),
        "kappa": engine.export_kappa_matrix(calib_data, output_path.replace(".xlsx", "_kappa.json"))
    }