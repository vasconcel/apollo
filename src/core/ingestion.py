"""
AIMS Data Ingestion Pipeline.
Loads processed CSV files, standardizes columns, deduplicates, and stores in SQLite database.
"""
import os
import glob
import re
import pandas as pd

from .config_manager import load_config
from .database import DatabaseManager


def normalize_columns(df: pd.DataFrame, column_aliases: dict) -> pd.DataFrame:
    """Normalize column names using aliases."""
    df_normalized = df.copy()
    df_normalized.columns = [column_aliases.get(col.strip(), col.strip()) for col in df_normalized.columns]
    return df_normalized


def normalize_year(value):
    """Normalize year to integer."""
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        try:
            return int(str(value)[:4])
        except (ValueError, TypeError):
            return None


# Insert inside `src/core/ingestion.py`
def standardize_dataframe(df: pd.DataFrame, source: str, column_aliases: dict, source_columns: list) -> pd.DataFrame:
    """Standardize DataFrame to required schema."""
    df = normalize_columns(df, column_aliases)

    if 'year' in df.columns:
        df['year'] = df['year'].apply(normalize_year)

    for col in source_columns:
        if col not in df.columns:
            df[col] = ''

    df['source'] = source
    
    if 'literature_type' not in df.columns:
        if 'wl' in source.lower():
            df['literature_type'] = 'WL'
        elif 'gl' in source.lower():
            df['literature_type'] = 'GL'
        else:
            df['literature_type'] = 'PENDING'

    return df


def load_csv_files(directory: str, column_aliases: dict, source_columns: list) -> pd.DataFrame:
    """Load all CSV files from a directory."""
    all_dfs = []

    pattern = os.path.join(directory, '**', '*.csv')
    csv_files = glob.glob(pattern, recursive=True)

    for csv_file in csv_files:
        if csv_file.endswith('_converted.csv'):
            continue

        try:
            source_name = os.path.basename(os.path.dirname(csv_file))
            df = pd.read_csv(csv_file, encoding='utf-8')
            if not df.empty:
                df = standardize_dataframe(df, source_name, column_aliases, source_columns)
                all_dfs.append(df)
                print(f"Loaded: {csv_file} ({len(df)} records)")
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")

    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def clean_title(title):
    """Clean title for comparison: lowercase, remove punctuation."""
    if pd.isna(title):
        return ''
    title_str = str(title).lower().strip()
    title_str = re.sub(r'[^\w\s]', '', title_str)
    title_str = re.sub(r'\s+', ' ', title_str)
    return title_str


def deduplicate_articles(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates based on DOI and cleaned title."""
    initial_count = len(df)
    print(f"Initial count: {initial_count} records")

    df = df.copy()
    df['title_clean'] = df['title'].apply(clean_title)

    if 'doi' in df.columns:
        doi_dupes = df[df['doi'].notna() & (df['doi'].astype(str).str.strip() != '')]
        if not doi_dupes.empty:
            doi_count_before = len(doi_dupes)
            df = df.drop_duplicates(subset=['doi'], keep='first')
            doi_removed = doi_count_before - len(df[df['doi'].notna() & (df['doi'].astype(str).str.strip() != '')])
            print(f"Removed {doi_removed} duplicates by DOI")
    else:
        print("DOI column not found for deduplication")

    df = df.drop_duplicates(subset=['title_clean', 'year'], keep='first')
    df = df.drop(columns=['title_clean'])

    final_count = len(df)
    removed = initial_count - final_count
    print(f"Removed {removed} duplicates. Final count: {final_count} records")

    return df


def run_ingestion(config_path: str = "project_config.json", db_path: str = "data/aims_project.db"):
    """Main ingestion pipeline."""
    print("Starting data ingestion...")

    config = load_config(config_path)
    column_aliases = config.column_aliases
    source_columns = config.source_columns

    db = DatabaseManager(db_path)

    wl_dir = "data/processed/wl"
    gl_dir = "data/processed/gl"

    wl_dfs = load_csv_files(wl_dir, column_aliases, source_columns) if os.path.exists(wl_dir) else pd.DataFrame()
    gl_dfs = load_csv_files(gl_dir, column_aliases, source_columns) if os.path.exists(gl_dir) else pd.DataFrame()

    if wl_dfs.empty and gl_dfs.empty:
        print("No data found.")
        return

    all_dfs = pd.concat([wl_dfs, gl_dfs], ignore_index=True)
    all_dfs = deduplicate_articles(all_dfs)

    print(f"Processing {len(all_dfs)} articles for database insertion...")

    for _, row in all_dfs.iterrows():
        article_data = {
            'title': row.get('title', ''),
            'original_title': row.get('title', ''),
            'authors': row.get('authors', ''),
            'year': row.get('year'),
            'abstract': row.get('abstract', ''),
            'doi': row.get('doi', ''),
            'url': row.get('url', ''),
            'source': row.get('source', ''),
            'literature_type': row.get('literature_type', '')
        }
        db.upsert_article(article_data)

    print(f"Inserted/updated {len(all_dfs)} articles in database")

    db.export_backup_csv("data/master_table.csv")

    stats = db.get_stats()
    print("\n=== Database Statistics ===")
    print(f"Total articles: {stats['total']}")
    print(f"WL articles: {stats['wl_count']}")
    print(f"GL articles: {stats['gl_count']}")
    print("Status breakdown:")
    for status, count in stats['status_breakdown'].items():
        print(f"  {status}: {count}")


if __name__ == "__main__":
    run_ingestion()
