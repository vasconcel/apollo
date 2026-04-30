import sqlite3
import pandas as pd

class ConsensusEngine:
    def __init__(self, db_path):
        self.db_path = db_path

    def load_decisions(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT article_id, reviewer_id, decision
            FROM screening_decisions
        """, conn)
        conn.close()
        return df

    def detect_conflicts(self):
        df = self.load_decisions()

        pivot = df.pivot_table(
            index="article_id",
            columns="reviewer_id",
            values="decision",
            aggfunc="first"
        )

        conflicts = pivot[
            pivot.nunique(axis=1) > 1
        ]

        return conflicts.reset_index()

    def detect_consensus(self):
        df = self.load_decisions()

        pivot = df.pivot_table(
            index="article_id",
            columns="reviewer_id",
            values="decision",
            aggfunc="first"
        )

        consensus = pivot[
            pivot.nunique(axis=1) == 1
        ]

        return consensus.reset_index()

    def auto_resolve_consensus(self, db):
        consensus_df = self.detect_consensus()

        for _, row in consensus_df.iterrows():
            article_id = row["article_id"]

            decisions = row.drop("article_id").dropna().values
            final_decision = decisions[0]

            db.save_final_decision(
                article_id,
                final_decision,
                "system_auto",
                "Auto-resolved consensus"
            )

        return len(consensus_df)