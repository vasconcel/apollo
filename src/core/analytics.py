import sqlite3
import pandas as pd
import numpy as np
from sklearn.metrics import cohen_kappa_score
import logging

logger = logging.getLogger(__name__)

class MLRAnalytics:
    def __init__(self, db_path: str = "data/aims_project.db"):
        self.db_path = db_path

    def merge_reviewer_decisions(self, external_db_path: str):
        """
        Importa decisões de um banco de dados externo (de outro revisor) 
        para o banco de dados mestre.
        """
        try:
            with sqlite3.connect(self.db_path) as master_conn:
                # Conecta ao banco externo
                master_conn.execute(f"ATTACH DATABASE '{external_db_path}' AS external_db")
                
                # Insere apenas as decisões que ainda não existem no mestre
                # Baseado no par (article_id, reviewer_id)
                query = """
                    INSERT INTO screening_decisions (article_id, reviewer_id, decision, exclusion_reason, timestamp)
                    SELECT article_id, reviewer_id, decision, exclusion_reason, timestamp
                    FROM external_db.screening_decisions
                    WHERE NOT EXISTS (
                        SELECT 1 FROM screening_decisions 
                        WHERE screening_decisions.article_id = external_db.screening_decisions.article_id
                        AND screening_decisions.reviewer_id = external_db.screening_decisions.reviewer_id
                    )
                """
                cursor = master_conn.execute(query)
                master_conn.commit()
                count = cursor.rowcount
                master_conn.execute("DETACH DATABASE external_db")
                return f"Sucesso: {count} decisões importadas."
        except Exception as e:
            logger.error(f"Erro no merge: {e}")
            return f"Erro: {str(e)}"

    def get_agreement_metrics(self):
        """
        Calcula o Cohen's Kappa entre os dois revisores principais.
        Assume que existem pelo menos dois revisores com decisões sobre os mesmos artigos.
        """
        query = """
            SELECT article_id, reviewer_id, decision 
            FROM screening_decisions 
            WHERE decision IN ('included_screening', 'excluded')
        """
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn)

        if df.empty or len(df['reviewer_id'].unique()) < 2:
            return {"kappa": 0.0, "status": "Insufficient data for Kappa", "n_shared": 0}

        # Pivotar para ter revisores como colunas
        # Mapeamos: included_screening -> 1, excluded -> 0
        df['decision_bin'] = df['decision'].map({'included_screening': 1, 'excluded': 0})
        
        pivot_df = df.pivot(index='article_id', columns='reviewer_id', values='decision_bin').dropna()
        
        if pivot_df.empty:
            return {"kappa": 0.0, "status": "No overlapping articles reviewed", "n_shared": 0}

        # Pegamos os dois primeiros revisores para o cálculo
        reviewers = pivot_df.columns[:2]
        kappa = cohen_kappa_score(pivot_df[reviewers[0]], pivot_df[reviewers[1]])
        
        # Interpretação Landis & Koch
        interpretation = "Poor"
        if kappa > 0.8: interpretation = "Almost Perfect"
        elif kappa > 0.6: interpretation = "Substantial"
        elif kappa > 0.4: interpretation = "Moderate"
        
        return {
            "kappa": round(kappa, 3),
            "interpretation": interpretation,
            "n_shared": len(pivot_df),
            "reviewers": list(reviewers)
        }

    def get_conflicts(self):
        """
        Identifica artigos onde os revisores divergiram.
        """
        query = """
            SELECT 
                a.id as article_id, 
                a.title, 
                GROUP_CONCAT(d.reviewer_id || ': ' || d.decision, ' | ') as details
            FROM screening_decisions d
            JOIN articles a ON d.article_id = a.id
            GROUP BY a.id
            HAVING COUNT(DISTINCT d.decision) > 1
        """
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(query, conn)

    def get_prisma_data(self):
        """
        Gera os números reais para o diagrama PRISMA do protocolo.
        """
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            # 1. Identification
            stats['total_imported'] = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            # 2. Screening
            stats['excluded_screening'] = conn.execute("SELECT COUNT(*) FROM articles WHERE status = 'excluded'").fetchone()[0]
            # 3. Quality (Eligibility)
            stats['excluded_qc'] = conn.execute("SELECT COUNT(*) FROM articles WHERE status = 'excluded_qc'").fetchone()[0]
            # 4. Included
            stats['final_included'] = conn.execute("SELECT COUNT(*) FROM articles WHERE status = 'included_final'").fetchone()[0]
            
            return stats

    def resolve_conflict(self, article_id: int, final_decision: str, rationale: str):
        """
        Aplica a decisão final (arbitragem) após discussão de conflito.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Atualiza o status do artigo na tabela principal
            conn.execute(
                "UPDATE articles SET status = ?, exclusion_reason = ? WHERE id = ?",
                (final_decision, rationale, article_id)
            )
            # Opcional: Logar quem resolveu o conflito na tabela de decisões
            conn.execute(
                "INSERT OR REPLACE INTO screening_decisions (article_id, reviewer_id, decision, exclusion_reason) VALUES (?, ?, ?, ?)",
                (article_id, "CONSENSUS_ADMIN", final_decision, rationale)
            )
            conn.commit()