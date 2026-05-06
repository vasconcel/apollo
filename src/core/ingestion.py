"""
AIMS Data Ingestion Pipeline.
Loads processed CSV files, standardizes columns, deduplicates with high precision, 
and stores in SQLite database.
"""
import os
import glob
import re
import pandas as pd
from .config_manager import load_config
from .database import Database
from .logger import get_logger, setup_logger

# Setup logger for ingestion module
logger = setup_logger("ingestion", "logs/aims_ingestion.log")


def normalize_columns(df: pd.DataFrame, column_aliases: dict) -> pd.DataFrame:
    """Normalize column names using config aliases."""
    df_normalized = df.copy()
    df_normalized.columns = [col.strip().lower() for col in df_normalized.columns]
    
    alias_map = {k.lower(): v for k, v in column_aliases.items()}
    df_normalized.columns = [alias_map.get(col, col) for col in df_normalized.columns]
    return df_normalized


def normalize_year(value):
    """Ensure year is a valid integer or None."""
    if pd.isna(value):
        return None
    try:
        match = re.search(r'\d{4}', str(value))
        if match:
            return int(match.group())
        return None
    except (ValueError, TypeError):
        return None


def normalize_doi(doi):
    """Normalize DOI by removing protocols and domains."""
    if pd.isna(doi) or str(doi).strip() == '':
        return None
    doi = str(doi).lower().strip()
    doi = doi.replace('https://doi.org/', '')
    doi = doi.replace('http://doi.org/', '')
    doi = doi.replace('doi.org/', '')
    doi = doi.replace('doi:', '')
    return doi


def clean_title(title):
    """Clean title for comparison: lowercase, no punctuation."""
    if pd.isna(title) or str(title).strip() == '':
        return ''
    title_str = str(title).lower().strip()
    title_str = re.sub(r'[^\w\s]', '', title_str)
    title_str = re.sub(r'\s+', ' ', title_str)
    return title_str


def standardize_dataframe(df: pd.DataFrame, source: str, column_aliases: dict, source_columns: list) -> pd.DataFrame:
    """Standardize DataFrame to system schema."""
    df = normalize_columns(df, column_aliases)

    if 'year' in df.columns:
        df['year'] = df['year'].apply(normalize_year)
    
    if 'doi' in df.columns:
        df['doi'] = df['doi'].apply(normalize_doi)

    for col in source_columns:
        if col not in df.columns:
            df[col] = ''

    df['source'] = source
    
    if 'wl' in source.lower() or 'white' in source.lower():
        df['literature_type'] = 'WL'
    elif 'gl' in source.lower() or 'grey' in source.lower():
        df['literature_type'] = 'GL'
    else:
        df['literature_type'] = 'WL'

    return df


def load_csv_files(directory: str, column_aliases: dict, source_columns: list):
    """Load all CSV files from directory recursively."""
    all_dfs = []
    pattern = os.path.join(directory, '**', '*.csv')
    csv_files = glob.glob(pattern, recursive=True)

    for csv_file in csv_files:
        if 'master_table' in csv_file or 'backup' in csv_file:
            continue

        try:
            source_name = os.path.basename(os.path.dirname(csv_file))
            df = pd.read_csv(csv_file, encoding='utf-8', on_bad_lines='skip')
            
            if not df.empty:
                df = standardize_dataframe(df, source_name, column_aliases, source_columns)
                all_dfs.append(df)
                logger.info(f"Loaded: {csv_file} ({len(df)} records)")
        except Exception as e:
            logger.error(f"Error loading {csv_file}: {e}")
            all_dfs.append(pd.DataFrame())

    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def deduplicate_articles(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates using DOI (primary) and Title+Year (secondary)."""
    initial_count = len(df)
    df = df.copy()

    df['title_clean'] = df['title'].apply(clean_title)
    
    has_doi = df[df['doi'].notna() & (df['doi'] != '')].copy()
    no_doi = df[df['doi'].isna() | (df['doi'] == '')].copy()

    has_doi = has_doi.drop_duplicates(subset=['doi'], keep='first')
    
    df = pd.concat([has_doi, no_doi], ignore_index=True)
    doi_removed = initial_count - len(df)
    if doi_removed > 0:
        logger.info(f"Removed {doi_removed} duplicates by DOI normalization.")

    count_before_title = len(df)
    df = df.drop_duplicates(subset=['title_clean', 'year'], keep='first')
    
    title_removed = count_before_title - len(df)
    if title_removed > 0:
        logger.info(f"Removed {title_removed} duplicates by Title + Year.")

    df = df.drop(columns=['title_clean'])
    
    final_count = len(df)
    logger.info(f"Deduplication Summary: {initial_count} -> {final_count} (Total removed: {initial_count - final_count})")
    return df


def run_ingestion(config_path: str = "project_config.json", db_path: str = "data/aims_project.db", review_id: int = 1):
    """Main ingestion pipeline."""
    logger.info("Starting data ingestion...")

    config = load_config(config_path)
    column_aliases = config.column_aliases
    source_columns = config.source_columns

    db = Database(db_path, review_id=review_id)

    base_dir = "data/processed"
    
    if not os.path.exists(base_dir):
        logger.warning(f"Directory {base_dir} not found. Please run converter first.")
        return

    all_data = load_csv_files(base_dir, column_aliases, source_columns)

    if all_data.empty:
        logger.warning("No data found to ingest.")
        return

    all_data = deduplicate_articles(all_data)

    logger.info(f"Processing {len(all_data)} articles for database insertion...")

    failed_records = []
    
    for idx, row in all_data.iterrows():
        try:
            article_data = {
                'title': str(row.get('title', '')),
                'authors': str(row.get('authors', '')),
                'year': row.get('year'),
                'abstract': str(row.get('abstract', '')),
                'doi': str(row.get('doi', '')),
                'url': str(row.get('url', '')),
                'source': str(row.get('source', '')),
                'literature_type': row.get('literature_type', 'WL')
            }
            
            if not article_data['title']:
                failed_records.append({
                    'row': idx,
                    'reason': 'Missing title',
                    'data': str(row.to_dict())[:200]
                })
                continue
                
            db.upsert_article(article_data)
            
        except Exception as e:
            failed_records.append({
                'row': idx,
                'reason': str(e),
                'title': str(row.get('title', ''))[:100]
            })
            logger.warning(f"Failed to insert row {idx}: {e}")

    logger.info(f"Inserted/updated {len(all_data) - len(failed_records)} articles in database")

    # Generate Failed Records Report
    if failed_records:
        logger.warning(f"=== FAILED RECORDS REPORT ({len(failed_records)} records) ===")
        for record in failed_records[:10]:  # Log first 10 failures
            logger.warning(f"Row {record.get('row')}: {record.get('reason')} - Title: {record.get('title', 'N/A')}")
        
        if len(failed_records) > 10:
            logger.warning(f"... and {len(failed_records) - 10} more failures")

    # Export backup
    try:
        db.export_backup_csv("data/master_table.csv")
    except Exception as e:
        logger.error(f"Failed to export backup: {e}")

    stats = db.get_stats(review_id)
    logger.info("=== Database Statistics ===")
    logger.info(f"Total articles: {stats['total']}")
    logger.info(f"WL articles: {stats['wl_count']}")
    logger.info(f"GL articles: {stats['gl_count']}")
    logger.info("Status breakdown:")
    for status, count in stats['status_breakdown'].items():
        logger.info(f"  {status}: {count}")


if __name__ == "__main__":
    run_ingestion()