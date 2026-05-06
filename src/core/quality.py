"""
APOLLO Quality Scoring Engine
Deterministic QC evaluation based on WL-Q1→Q4 / GL-Q1→Q4 criteria
"""


class QualityEngine:
    """Rule-based quality scoring for QC decisions."""
    
    def __init__(self, threshold=2.0):
        self.threshold = threshold
    
    def evaluate(self, scores_dict: dict) -> dict:
        """
        Evaluate article quality based on criteria scores.
        
        Args:
            scores_dict: Dictionary of criterion -> score (0, 0.5, or 1.0)
        
        Returns:
            dict with total_score and decision (include/exclude)
        """
        total = sum(scores_dict.values())
        decision = "include" if total >= self.threshold else "exclude"
        
        return {
            "total_score": total,
            "decision": decision,
            "threshold": self.threshold,
            "passing": total >= self.threshold
        }
    
    def evaluate_with_confidence(self, scores_dict: dict) -> dict:
        """
        Evaluate with confidence score based on score margin.
        """
        result = self.evaluate(scores_dict)
        max_score = len(scores_dict) * 1.0
        margin = result["total_score"] - self.threshold
        
        if margin >= 1.0:
            confidence = 1.0
        elif margin >= 0.5:
            confidence = 0.8
        elif margin >= 0:
            confidence = 0.6
        else:
            confidence = 0.4
        
        result["confidence"] = confidence
        return result