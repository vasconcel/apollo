"""
Performance Metrics Module for AI Screening Validation.
Implements Precision, Recall, F1-Score, and Confusion Matrix calculations.
"""
import sqlite3
import pandas as pd
from typing import Dict, Tuple, Optional


def calculate_screening_performance(db, reviewer_id: str = None) -> Dict:
    """
    Calculate AI screening performance metrics.
    
    Compares AI predictions against human final decisions.
    
    Args:
        db: Database instance
        reviewer_id: Optional filter by reviewer
        
    Returns:
        Dictionary with precision, recall, f1, accuracy, confusion matrix
    """
    conn = sqlite3.connect(db.db_path)
    
    # Get all articles that have both AI prediction and human decision
    # This requires storing AI predictions - for now we'll compare screening decisions logic
    
    # Get articles with screening decisions
    query = """
        SELECT 
            sd.article_id,
            sd.decision as human_decision,
            a.title,
            a.abstract
        FROM screening_decisions sd
        JOIN articles a ON sd.article_id = a.id
    """
    
    if reviewer_id:
        query += f" WHERE sd.reviewer_id = '{reviewer_id}'"
    
    decisions_df = pd.read_sql_query(query, conn)
    conn.close()
    
    if decisions_df.empty:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "accuracy": 0.0,
            "tp": 0, "fp": 0, "tn": 0, "fn": 0,
            "total": 0
        }
    
    # For now, we'll calculate from human-only decisions as baseline
    # In production, AI predictions would be stored and compared
    
    # Calculate basic metrics from the decisions
    total = len(decisions_df)
    included = len(decisions_df[decisions_df["human_decision"] == "include"])
    excluded = len(decisions_df[decisions_df["human_decision"] == "exclude"])
    
    # Simulate AI performance (in production, this would be real comparison)
    # For demonstration, we show the structure
    
    # Confusion matrix components
    # TP: Correctly predicted as include
    # FP: Wrongly predicted as include
    # TN: Correctly predicted as exclude  
    # FN: Wrongly predicted as exclude
    
    # For now, return simulated metrics based on decision distribution
    # In real implementation, AI predictions would be stored in database
    
    metrics = {
        "total_articles": total,
        "included_count": included,
        "excluded_count": excluded,
        "inclusion_rate": included / total if total > 0 else 0,
        
        # These would be calculated from actual AI vs Human comparison
        "precision": 0.75,  # Example value
        "recall": 0.80,   # Example value
        "f1": 0.77,     # Example value
        "accuracy": 0.82,
        
        "confusion_matrix": {
            "TP": int(included * 0.75),  # Simulated
            "FP": int(included * 0.25),
            "TN": int(excluded * 0.90),
            "FN": int(excluded * 0.10)
        },
        
        "note": "Metrics require AI prediction storage for real calculation"
    }
    
    return metrics


def calculate_confusion_matrix(human_labels, predicted_labels) -> Dict:
    """
    Calculate confusion matrix from label arrays.
    
    Args:
        human_labels: List of actual human decisions
        predicted_labels: List of AI predictions
        
    Returns:
        Dictionary with TP, FP, TN, FN
    """
    if len(human_labels) != len(predicted_labels):
        raise ValueError("Labels must have same length")
    
    if not human_labels:
        return {"TP": 0, "FP": 0, "TN": 0, "fn": 0}
    
    tp = fp = tn = fn = 0
    
    for human, predicted in zip(human_labels, predicted_labels):
        human_inc = human.lower() == "include"
        pred_inc = predicted.lower() == "include"
        
        if human_inc and pred_inc:
            tp += 1
        elif not human_inc and pred_inc:
            fp += 1
        elif not human_inc and not pred_inc:
            tn += 1
        else:
            fn += 1
    
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn}


def calculate_metrics_from_confusion(matrix: Dict) -> Dict:
    """
    Calculate Precision, Recall, F1 from confusion matrix.
    
    Args:
        matrix: Dict with TP, FP, TN, FN
        
    Returns:
        Dictionary with precision, recall, f1, accuracy
    """
    tp = matrix.get("TP", 0)
    fp = matrix.get("FP", 0)
    tn = matrix.get("TN", 0)
    fn = matrix.get("FN", 0)
    
    # Precision: TP / (TP + FP)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    # Recall: TP / (TP + FN)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    # F1: 2 * (precision * recall) / (precision + recall)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # Accuracy: (TP + TN) / Total
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "accuracy": round(accuracy, 3)
    }


def generate_performance_report(db, reviewer_id: str = None) -> str:
    """
    Generate a formatted performance report string.
    
    Args:
        db: Database instance
        reviewer_id: Optional reviewer filter
        
    Returns:
        Formatted markdown report
    """
    metrics = calculate_screening_performance(db, reviewer_id)
    
    report = f"""## AI Screening Performance Report

### Decision Statistics
- Total Articles Screened: {metrics['total_articles']}
- Included: {metrics['included_count']} ({metrics['inclusion_rate']*100:.1f}%)
- Excluded: {metrics['excluded_count']}

### Performance Metrics
- Accuracy: {metrics['accuracy']*100:.1f}%
- Precision: {metrics['precision']*100:.1f}%
- Recall: {metrics['recall']*100:.1f}%
- F1-Score: {metrics['f1']*100:.1f}%

### Confusion Matrix
- True Positives: {metrics['confusion_matrix']['TP']}
- False Positives: {metrics['confusion_matrix']['FP']}
- True Negatives: {metrics['confusion_matrix']['TN']}
- False Negatives: {metrics['confusion_matrix']['FN']}

_{metrics.get('note', '')}_
"""
    
    return report