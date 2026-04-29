import pandas as pd
import sqlite3
import json

class ExchangeManager:
    def __init__(self, db_path):
        self.db_path = db_path

    def export_decisions(self, reviewer_id, output_path):
        """Exporta apenas as decisões de um revisor específico para CSV."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM screening_decisions WHERE reviewer_id = ?"
            df = pd.read_sql_query(query, conn, params=(reviewer_id,))
            df.to_csv(output_path, index=False)
            return len(df)

    def import_decisions(self, csv_path):
        """Importa decisões de um arquivo CSV externo para o banco central."""
        df = pd.read_csv(csv_path)
        count = 0
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO screening_decisions 
                        (article_id, reviewer_id, decision, exclusion_reason, criteria_snapshot, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (row['article_id'], row['reviewer_id'], row['decision'], 
                          row['exclusion_reason'], row['criteria_snapshot'], row['timestamp']))
                    count += 1
                except Exception as e:
                    print(f"Error importing row: {e}")
            conn.commit()
        return count