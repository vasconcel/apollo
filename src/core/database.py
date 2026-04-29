# src/core/database.py
import sqlite3
import pandas as pd
import re
import os
import json
from typing import Dict, Any, List, Optional

class DatabaseManager:
    def __init__(self, db_path: str = "data/aims_project.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._initialize_schema()

    def _ensure_db_directory(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _initialize_schema(self):
        """Inicializa o esquema do banco de dados com suporte a múltiplos revisores e auditoria."""
        with sqlite3.connect(self.db_path) as conn:
            # 1. Tabela Principal de Artigos
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT UNIQUE,  -- Ex: WL-001, GL-001
                    title TEXT,
                    original_title TEXT,
                    authors TEXT,
                    year INTEGER,
                    abstract TEXT,
                    doi TEXT,
                    url TEXT,
                    source TEXT,
                    literature_type TEXT CHECK(literature_type IN ('WL', 'GL', 'PENDING')),
                    status TEXT CHECK(status IN (
                        'imported', 'deduplicated', 'excluded', 
                        'pending_consensus', 'included_screening', 
                        'excluded_qc', 'included_final'
                    )) DEFAULT 'imported',
                    exclusion_reason TEXT,
                    quality_score REAL,
                    extraction_data TEXT, -- Armazena JSON com os campos de extração (RQs)
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Tabela de Decisões de Revisores (Blind Review)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screening_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER,
                    reviewer_id TEXT,
                    decision TEXT CHECK(decision IN ('included_screening', 'excluded', 'uncertain')),
                    exclusion_reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (article_id) REFERENCES articles (id),
                    UNIQUE(article_id, reviewer_id)
                )
            """)
            conn.commit()

    def _normalize_title(self, title: str) -> str:
        if not title: return ""
        title_str = str(title).lower().strip()
        title_str = re.sub(r'[^\w\s]', '', title_str)
        title_str = re.sub(r'\s+', ' ', title_str)
        return title_str

    # ==================== GESTÃO DE ARTIGOS ====================

    def upsert_article(self, article_data: Dict[str, Any]) -> int:
        """Insere ou atualiza um artigo, gerando Source ID rastreável."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            doi = str(article_data.get('doi', '')).strip()
            title = article_data.get('title', '')
            norm_title = self._normalize_title(title)
            year = article_data.get('year')

            # Checagem de Duplicata (DOI ou Título+Ano)
            existing = None
            if doi and len(doi) > 3:
                cursor = conn.execute("SELECT id FROM articles WHERE doi = ?", (doi,))
                existing = cursor.fetchone()

            if not existing and norm_title:
                cursor = conn.execute("SELECT id FROM articles WHERE title = ? AND (year = ? OR year IS NULL)", (norm_title, year))
                existing = cursor.fetchone()

            if existing:
                return existing['id']
            else:
                lit_type = article_data.get('literature_type') or 'PENDING'
                
                # Gerar Source ID (Ex: WL-005)
                cursor = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = ?", (lit_type,))
                count = cursor.fetchone()[0] + 1
                source_id = f"{lit_type}-{count:03d}"

                cursor = conn.execute("""
                    INSERT INTO articles (source_id, title, original_title, authors, year, abstract, doi, url, source, literature_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported')
                """, (
                    source_id, norm_title, article_data.get('original_title', title),
                    article_data.get('authors', ''), year, article_data.get('abstract', ''),
                    doi, article_data.get('url', ''), article_data.get('source', ''), lit_type
                ))
                conn.commit()
                return cursor.lastrowid

    # ==================== PROTOCOLO MULTI-REVISOR ====================

    def save_reviewer_decision(self, article_id: int, reviewer_id: str, decision: str, reason: str = ""):
        """Salva a decisão individual de um revisor (Blind Review)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO screening_decisions (article_id, reviewer_id, decision, exclusion_reason)
                VALUES (?, ?, ?, ?)
            """, (article_id, reviewer_id, decision, reason))
            conn.commit()

    def get_pending_for_reviewer(self, reviewer_id: str):
        """Retorna artigos que o revisor atual ainda não avaliou."""
        query = """
            SELECT * FROM articles 
            WHERE id NOT IN (
                SELECT article_id FROM screening_decisions WHERE reviewer_id = ?
            ) AND status = 'imported'
        """
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(query, conn, params=(reviewer_id,))

    def get_conflicts(self) -> pd.DataFrame:
        """Identifica divergências entre revisores para resolução de conflitos."""
        query = """
            SELECT a.id, a.source_id, a.title, 
                   GROUP_CONCAT(d.reviewer_id || ': ' || d.decision, ' | ') as all_decisions
            FROM screening_decisions d
            JOIN articles a ON d.article_id = a.id
            GROUP BY a.id
            HAVING COUNT(DISTINCT d.decision) > 1
        """
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(query, conn)

    def resolve_consensus(self, article_id: int, final_status: str, reason: str = ""):
        """Aplica a decisão final após arbitragem ou consenso."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE articles 
                SET status = ?, exclusion_reason = ? 
                WHERE id = ?
            """, (final_status, reason, article_id))
            conn.commit()

    # ==================== SÍNTESE E QUALIDADE ====================

    def update_quality_and_extraction(self, article_id: int, score: float, extraction_dict: Dict, status: str = "included_final"):
        """Salva o score de qualidade e os dados extraídos (RQs)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE articles 
                SET quality_score = ?, extraction_data = ?, status = ? 
                WHERE id = ?
            """, (score, json.dumps(extraction_dict), status, article_id))
            conn.commit()

    # ==================== UTILITÁRIOS E EXPORTAÇÃO ====================

    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            stats['total'] = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            stats['wl_count'] = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'WL'").fetchone()[0]
            stats['gl_count'] = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'GL'").fetchone()[0]
            
            # Breakdown por status final
            cursor = conn.execute("SELECT status, COUNT(*) FROM articles GROUP BY status")
            stats['status_breakdown'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Progresso do Screening (quantos revisores já votaram)
            cursor = conn.execute("SELECT COUNT(DISTINCT article_id) FROM screening_decisions")
            stats['screened_count'] = cursor.fetchone()[0]
            
            return stats

    def get_articles_by_status(self, status: str):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query("SELECT * FROM articles WHERE status = ?", conn, params=(status,))

    def export_backup_csv(self, output_path: str):
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query("SELECT * FROM articles", conn)
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
        except Exception as e:
            print(f"Falha ao exportar backup: {e}")

    def upsert_mesh(self, articles_list: list):
        """Versão simplificada para inserção em lote (ex: snowballing)."""
        for article in articles_list:
            self.upsert_article(article)