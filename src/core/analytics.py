import pandas as pd
from sklearn.metrics import cohen_kappa_score
import sqlite3

def load_decisions_dataframe(db_path):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("""
        SELECT article_id, reviewer_id, decision
        FROM screening_decisions
    """, conn)
    conn.close()
    return df


def prepare_kappa(df):
    pivot = df.pivot_table(
        index="article_id",
        columns="reviewer_id",
        values="decision",
        aggfunc="first"
    )

    mapping = {"include": 1, "exclude": 0}
    pivot = pivot.replace(mapping)

    pivot = pivot.dropna()

    if pivot.shape[1] < 2:
        return None, None

    reviewers = pivot.columns.tolist()
    kappa = cohen_kappa_score(pivot[reviewers[0]], pivot[reviewers[1]])

    return kappa, pivot


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