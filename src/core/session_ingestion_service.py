"""
APOLLO Session Ingestion Service

Stateless ingestion service for screening sessions.
Parses Excel/CSV uploads and converts records to ArticleReview objects.
Contains no Streamlit, advisory, persistence, navigation, or query logic.
"""

import os
import uuid
from typing import Dict, List, Optional, Any

from src.core.logging_config import get_logger

logger = get_logger("ingestion")
INGESTION_DEBUG = False

LITERATURE_TYPE_MAP = {
    "WL": "WL", "wl": "WL", "Wl": "WL",
    "WHITE LITERATURE": "WL", "White Literature": "WL", "white literature": "WL",
    "GL": "GL", "gl": "GL", "Gl": "GL",
    "GREY LITERATURE": "GL", "Grey Literature": "GL", "grey literature": "GL",
}


class SessionIngestionService:
    """Stateless ingestion service for ScreeningSession.

    All methods are @staticmethod — no instance state, no persistence,
    no navigation, no query logic.
    """

    # ------------------------------------------------------------------
    # Metadata normalization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Defensive metadata normalization."""
        required_fields = {
            "year": "Unknown",
            "year_source": "missing",
            "authors": "",
            "author_normalization_source": "unknown",
            "source": "",
            "source_type": "unknown",
            "literature_type": "WL",
            "metadata_completeness": "unknown"
        }
        normalized = dict(metadata)
        for field_name, default_value in required_fields.items():
            if field_name not in normalized or normalized[field_name] is None or str(normalized.get(field_name, "")).strip() == "":
                normalized[field_name] = default_value
        return normalized

    @staticmethod
    def normalize_literature_type(raw_value: str) -> str:
        """Normalize literature type to canonical WL/GL value."""
        if not raw_value:
            return "WL"
        normalized = raw_value.strip()
        return LITERATURE_TYPE_MAP.get(normalized, LITERATURE_TYPE_MAP.get(normalized.upper(), "WL"))

    @staticmethod
    def compute_csv_metadata_completeness(row: dict) -> str:
        """Compute metadata completeness for CSV rows."""
        has_title = bool(row.get("Title"))
        has_abstract = bool(row.get("Abstract"))
        has_year = bool(row.get("Year"))
        if has_title and has_abstract and has_year:
            return "complete"
        elif has_title:
            return "partial"
        return "minimal"

    # ------------------------------------------------------------------
    # Article conversion
    # ------------------------------------------------------------------

    @staticmethod
    def add_articles(article_records: List) -> List[Any]:
        """Convert article records to ArticleReview objects."""
        from src.core.screening_session import ArticleReview
        return [ArticleReview.from_article_record(r) for r in article_records]

    # ------------------------------------------------------------------
    # Upload ingestion
    # ------------------------------------------------------------------

    @staticmethod
    def ingest_from_bytes(
        file_bytes: bytes,
        filename: str,
        stage: str = "ec",
    ) -> List[Any]:
        """Ingest articles from file bytes (Excel or CSV).

        Args:
            file_bytes: Raw file content.
            filename: Original filename (determines parser: .csv vs .xlsx).
            stage: Current screening stage ("ec" or "ic").

        Returns:
            List of ArticleReview objects with full metadata.
        """
        import tempfile
        import pandas as pd
        from src.core.article_metadata import (
            normalize_wl_metadata, normalize_gl_metadata, article_to_dict,
            LATEX_DECODER_AVAILABLE,
        )
        from src.core.year_extraction import extract_year

        temp_path = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name

        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)

            if filename.endswith(".csv"):
                df = pd.read_csv(temp_path)
                articles = []
                for _, row in df.iterrows():
                    row_dict = row.to_dict()
                    lit_type = SessionIngestionService.normalize_literature_type(
                        str(row_dict.get("Literature_Type", "WL"))
                    )
                    completeness = SessionIngestionService.compute_csv_metadata_completeness(row_dict)

                    title = str(row_dict.get("Title", ""))
                    abstract = str(row_dict.get("Abstract", ""))

                    year_value = row_dict.get("Year")
                    year_source = "csv"
                    if year_value is None or str(year_value).strip() == "":
                        extracted_year, extracted_source = extract_year(title, abstract, None)
                        if extracted_year:
                            year_value = extracted_year
                            year_source = extracted_source

                    metadata = {
                        "year": str(year_value) if year_value else "",
                        "authors": str(row_dict.get("Authors", "")),
                        "literature_type": lit_type,
                        "title": title,
                        "abstract": abstract,
                        "global_id": str(row_dict.get("global_id", str(uuid.uuid4())[:8])),
                        "year_source": year_source,
                        "metadata_completeness": completeness,
                    }
                    from src.core.screening_session import ArticleReview
                    review_article = ArticleReview(
                        article_id=metadata["global_id"],
                        title=metadata["title"],
                        abstract=metadata["abstract"],
                        metadata=metadata,
                    )
                    if stage == "ic":
                        review_article.ec_stage = str(row_dict.get("EC_Decision", "INCLUDE"))
                    articles.append(review_article)
                return articles
            else:
                wl_df = pd.read_excel(temp_path, sheet_name="White Literature")
                gl_df = pd.read_excel(temp_path, sheet_name="Grey Literature")

            articles = []
            if INGESTION_DEBUG:
                logger.debug("WL ingestion start")
            for idx, row in wl_df.iterrows():
                row_dict = row.to_dict()
                article = normalize_wl_metadata(row_dict)
                article_dict = article_to_dict(article)

                year_value = article.year if article.year else None
                year_source = "atlas"

                if INGESTION_DEBUG:
                    logger.debug(f"WL {idx} - Structured year: {repr(year_value)}")

                if year_value is None:
                    extracted_year, extracted_source = extract_year(
                        article.title, article.abstract, None,
                    )
                    if INGESTION_DEBUG:
                        logger.debug(f"WL {idx} - Regex fallback: year={repr(extracted_year)}, source={repr(extracted_source)}")
                    if extracted_year:
                        year_value = extracted_year
                        year_source = extracted_source

                if INGESTION_DEBUG:
                    logger.debug(f"WL {idx} - Final year: {repr(year_value)}, source: {repr(year_source)}")

                metadata = {
                    "year": str(year_value) if year_value else "",
                    "authors": article.authors,
                    "literature_type": article.literature_type,
                    "doi": article.doi,
                    "source": article.source,
                    "keywords": article.keywords,
                    "library": article.library,
                    "global_id": article.global_id,
                    "local_id": article.local_id,
                    "url": article.url,
                    "completeness": article.completeness_score,
                    "year_source": year_source,
                    "metadata_completeness": article.metadata_completeness,
                    "raw_data": article.raw_data,
                    "author_normalization_source": "pylatexenc" if LATEX_DECODER_AVAILABLE else "raw",
                }

                metadata = SessionIngestionService.normalize_metadata(metadata)

                from src.core.screening_session import ArticleReview
                review_article = ArticleReview(
                    article_id=article.global_id or article.local_id or str(uuid.uuid4())[:8],
                    title=article.title,
                    abstract=article.abstract,
                    metadata=metadata,
                )
                articles.append(review_article)

            if INGESTION_DEBUG:
                logger.debug("GL ingestion start")
            for idx, row in gl_df.iterrows():
                row_dict = row.to_dict()
                article = normalize_gl_metadata(row_dict)
                article_dict = article_to_dict(article)

                year_value = article.year if article.year else None
                year_source = "atlas"

                if INGESTION_DEBUG:
                    logger.debug(f"GL {idx} - Structured year: {repr(year_value)}")

                if year_value is None:
                    extracted_year, extracted_source = extract_year(
                        article.title, article.abstract, None,
                    )
                    if INGESTION_DEBUG:
                        logger.debug(f"GL {idx} - Regex fallback: year={repr(extracted_year)}, source={repr(extracted_source)}")
                    if extracted_year:
                        year_value = extracted_year
                        year_source = extracted_source

                if INGESTION_DEBUG:
                    logger.debug(f"GL {idx} - Final year: {repr(year_value)}, source: {repr(year_source)}")

                metadata = {
                    "year": str(year_value) if year_value else "",
                    "authors": article.authors,
                    "literature_type": article.literature_type,
                    "url": article.url,
                    "source": article.source,
                    "keywords": article.keywords,
                    "global_id": article.global_id,
                    "local_id": article.local_id,
                    "completeness": article.completeness_score,
                    "year_source": year_source,
                    "metadata_completeness": article.metadata_completeness,
                    "raw_data": article.raw_data,
                    "author_normalization_source": "pylatexenc" if LATEX_DECODER_AVAILABLE else "raw",
                }

                metadata = SessionIngestionService.normalize_metadata(metadata)

                from src.core.screening_session import ArticleReview
                review_article = ArticleReview(
                    article_id=article.global_id or article.local_id or str(uuid.uuid4())[:8],
                    title=article.title,
                    abstract=article.abstract,
                    metadata=metadata,
                )
                articles.append(review_article)

            return articles

        finally:
            os.unlink(temp_path)
