# src/core/database.py
import sqlite3
import pandas as pd
import re
import os
import json
from typing import Dict, Any

class DatabaseManager:
    def __init__(self, db_path: str = "data/aims_project.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._initialize_schema()

    def _ensure_db_directory(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _initialize_schema(self):
        """
        Creates table and handles seamless schema migration.
        Updated for publication-ready MLR: Source IDs, Extraction Data JSON, and QC Status.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'")
            row = cursor.fetchone()
            
            # Novo Schema Alinhado ao Protocolo LaTeX
            create_sql = """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT UNIQUE,  -- Rastreabilidade (ex: WL-0001, GL-0042)
                    title TEXT,
                    original_title TEXT,
                    authors TEXT,
                    year INTEGER,
                    abstract TEXT,
                    doi TEXT,
                    url TEXT,
                    source TEXT,
                    literature_type TEXT CHECK(literature_type IN ('WL', 'GL', 'PENDING')),
                    status TEXT CHECK(status IN ('imported', 'deduplicated', 'excluded', 'included_screening', 'excluded_qc', 'included_final')) DEFAULT 'imported',
                    exclusion_reason TEXT,
                    ic_results TEXT,
                    quality_score REAL,
                    extraction_data TEXT,   -- Armazena o JSON do Evidence Synthesis
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            needs_migration = False
            if row:
                current_sql = row[0].upper()
                # Checa se precisamos migrar devido à ausência das novas colunas de protocolo
                if "SOURCE_ID" not in current_sql or "EXTRACTION_DATA" not in current_sql or "EXCLUDED_QC" not in current_sql:
                    needs_migration = True
                    
            if needs_migration:
                conn.execute("PRAGMA foreign_keys=off")
                try:
                    conn.execute("BEGIN TRANSACTION")
                    conn.execute("ALTER TABLE articles RENAME TO articles_old")
                    conn.execute(create_sql)
                    
                    # Mapeia colunas de forma segura para versões antigas do DB
                    old_cols = [c[1] for c in conn.execute("PRAGMA table_info(articles_old)").fetchall()]
                    new_cols = [c[1] for c in conn.execute("PRAGMA table_info(articles)").fetchall()]
                    common_cols = ", ".join([c for c in old_cols if c in new_cols])
                    
                    if common_cols:
                        conn.execute(f"INSERT INTO articles ({common_cols}) SELECT {common_cols} FROM articles_old")
                        
                    conn.execute("DROP TABLE articles_old")
                    
                    # Backfill de Source IDs para dados legados caso existam
                    cursor = conn.execute("SELECT id, literature_type FROM articles WHERE source_id IS NULL")
                    legacy_rows = cursor.fetchall()
                    
                    type_counters = {'WL': 0, 'GL': 0, 'PENDING': 0}
                    for row in legacy_rows:
                        l_type = row[1] if row[1] in type_counters else 'PENDING'
                        prefix = l_type if l_type in ['WL', 'GL'] else 'PD'
                        type_counters[l_type] += 1
                        s_id = f"{prefix}-LEGACY-{type_counters[l_type]:04d}"
                        conn.execute("UPDATE articles SET source_id = ? WHERE id = ?", (s_id, row[0]))

                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"Migration failed: {e}")
                finally:
                    conn.execute("PRAGMA foreign_keys=on")
            else:
                conn.execute(create_sql)
                conn.commit()

    def _normalize_title(self, title: str) -> str:
        if not title: return ""
        title_str = str(title).lower().strip()
        title_str = re.sub(r'[^\w\s]', '', title_str)
        title_str = re.sub(r'\s+', ' ', title_str)
        return title_str

    def _generate_source_id(self, conn, literature_type: str) -> str:
        """Gera IDs incrementais canônicos (Ex: WL-0142) baseados no protocolo."""
        prefix = literature_type if literature_type in ['WL', 'GL'] else 'PD'
        # Conta quantos estudos desse prefixo já existem
        cursor = conn.execute("SELECT COUNT(*) FROM articles WHERE source_id LIKE ?", (f"{prefix}-%",))
        count = cursor.fetchone()[0]
        return f"{prefix}-{count + 1:04d}"

    def upsert_article(self, article_data: Dict[str, Any]) -> int:
        """Upsert Genérico: Insere ou atualiza registros com precisão."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            doi = str(article_data.get('doi', '')).strip()
            
            title = article_data.get('title', '')
            norm_title = self._normalize_title(title)
            year = article_data.get('year')

            existing = None
            if doi and len(doi) > 3:
                cursor = conn.execute("SELECT id FROM articles WHERE doi = ?", (doi,))
                existing = cursor.fetchone()

            if not existing and norm_title:
                if year:
                    cursor = conn.execute("SELECT id FROM articles WHERE title = ? AND year = ?", (norm_title, year))
                else:
                    cursor = conn.execute("SELECT id FROM articles WHERE title = ? AND year IS NULL", (norm_title,))
                existing = cursor.fetchone()

            if existing:
                article_id = existing['id']
                updates = []
                params = []
                # Atualiza campos mas NUNCA sobrescreve o source_id ou status
                for key in ['title', 'authors', 'year', 'abstract', 'doi', 'url', 'source', 'literature_type']:
                    if key in article_data and article_data[key] is not None:
                        updates.append(f"{key} = ?")
                        params.append(article_data[key])
                if updates:
                    params.append(article_id)
                    conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params)
                return article_id
            else:
                lit_type = article_data.get('literature_type') or 'PENDING'
                source_id = self._generate_source_id(conn, lit_type)

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

    def upsert_mesh(self, articles_list: list):
        for article in articles_list:
            self.upsert_article(article)

    def upsert_mesh_batch(self, articles_list: list):
        """Versão otimizada que insere todos os artigos em uma única transação."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN TRANSACTION") 
            try:
                for article_data in articles_list:
                    doi = str(article_data.get('doi', '')).strip()
                    title = article_data.get('title', '')
                    norm_title = self._normalize_title(title)
                    year = article_data.get('year')
                    lit_type = article_data.get('literature_type') or 'PENDING'
                    
                    cursor = conn.execute("SELECT id FROM articles WHERE doi = ? AND doi != ''", (doi,))
                    existing = cursor.fetchone()
                    
                    if not existing:
                        cursor = conn.execute("SELECT id FROM articles WHERE title = ? AND year = ?", (norm_title, year))
                        existing = cursor.fetchone()

                    if not existing:
                        source_id = self._generate_source_id(conn, lit_type)
                        
                        conn.execute("""
                            INSERT INTO articles (source_id, title, original_title, authors, year, abstract, doi, url, source, literature_type, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported')
                        """, (
                            source_id, norm_title, article_data.get('original_title', title),
                            article_data.get('authors', ''), year, article_data.get('abstract', ''),
                            doi, article_data.get('url', ''), article_data.get('source', ''), lit_type
                        ))
                conn.execute("COMMIT") 
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e

    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            stats['total'] = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            stats['wl_count'] = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'WL'").fetchone()[0]
            stats['gl_count'] = conn.execute("SELECT COUNT(*) FROM articles WHERE literature_type = 'GL'").fetchone()[0]
            cursor = conn.execute("SELECT status, COUNT(*) FROM articles GROUP BY status")
            stats['status_breakdown'] = {row[0]: row[1] for row in cursor.fetchall()}
            return stats

    def get_articles_by_status(self, status: str):
        """Retorna artigos em formato DataFrame filtrados pelo status metodológico."""
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query("SELECT * FROM articles WHERE status = ?", conn, params=(status,))

    def update_article_status(self, article_id: int, new_status: str, exclusion_reason: str = None):
        """Atualiza o status de triagem e, opcionalmente, o motivo de exclusão."""
        with sqlite3.connect(self.db_path) as conn:
            if exclusion_reason:
                conn.execute("UPDATE articles SET status = ?, exclusion_reason = ? WHERE id = ?", (new_status, exclusion_reason, article_id))
            else:
                conn.execute("UPDATE articles SET status = ? WHERE id = ?", (new_status, article_id))
            conn.commit()

    def save_evidence_synthesis(self, article_id: int, quality_score: float, extraction_dict: dict, final_status: str = 'included_final'):
        """Método encapsulado para salvar os resultados do formulário de Evidence Synthesis e QA."""
        with sqlite3.connect(self.db_path) as conn:
            ext_json = json.dumps(extraction_dict, ensure_ascii=False)
            conn.execute("""
                UPDATE articles 
                SET status = ?, quality_score = ?, extraction_data = ? 
                WHERE id = ?
            """, (final_status, quality_score, ext_json, article_id))
            conn.commit()

    def export_backup_csv(self, output_path: str):
        """Exporta todo o conteúdo (incluindo Extrações JSON) para CSV de backup analítico."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query("SELECT * FROM articles ORDER BY source_id", conn)
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                print(f"Backup master table exportado para: {output_path}")
        except Exception as e:
            print(f"Falha ao exportar backup: {e}")