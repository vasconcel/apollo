import pandas as pd
from sklearn.metrics import cohen_kappa_score
import sqlite3
import numpy as np

def load_decisions_dataframe(db_path):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("""
        SELECT article_id, reviewer_id, decision
        FROM screening_decisions
    """, conn)
    conn.close()
    return df


def prepare_kappa(df):
    """
    Calculates Cohen's Kappa with robust edge case handling.
    Returns (kappa, pivot) or (None, None) if calculation not possible.
    """
    pivot = df.pivot_table(
        index="article_id",
        columns="reviewer_id",
        values="decision",
        aggfunc="first"
    )

    mapping = {"include": 1, "exclude": 0}
    pivot = pivot.replace(mapping)

    pivot = pivot.dropna()

    # Need at least 2 reviewers with overlapping articles
    if pivot.shape[1] < 2:
        return None, None
    
    # Need sufficient overlapping articles for meaningful kappa
    if pivot.shape[0] < 2:
        return None, None

    reviewers = pivot.columns.tolist()
    
    try:
        # Calculate observed agreement to detect perfect agreement case
        agreement = (pivot[reviewers[0]] == pivot[reviewers[1]]).mean()
        
        # Handle edge case: 100% agreement (perfect concordance)
        # Cohen's Kappa is undefined when there's no variation in predictions
        if agreement == 1.0:
            # Return 1.0 (perfect agreement) with flag for UI to display appropriately
            return 1.0, pivot
        elif agreement == 0.0:
            # Return 0.0 Kappa for complete disagreement
            return 0.0, pivot
        else:
            kappa = cohen_kappa_score(pivot[reviewers[0]], pivot[reviewers[1]])
            return kappa, pivot
            
    except Exception as e:
        print(f"Kappa calculation error: {e}")
        return None, None


def find_conflicts(db_path):
    conn = sqlite3.connect(db_path)

    query = """
    SELECT a.id as article_id, a.title,
           GROUP_CONCAT(d.reviewer_id || ':' || d.decision) as decisions
    FROM screening_decisions d
    JOIN articles a ON d.article_id = a.id
    GROUP BY a.id
    HAVING COUNT(DISTINCT d.decision) > 1
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df