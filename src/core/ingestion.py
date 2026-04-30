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

def normalize_columns(df: pd.DataFrame, column_aliases: dict) -> pd.DataFrame:
    """Normaliza nomes de colunas usando os aliases do config."""
    df_normalized = df.copy()
    # Converte colunas para lowercase antes do mapeamento para evitar Case Sensitivity
    df_normalized.columns = [col.strip().lower() for col in df_normalized.columns]
    
    # Prepara o mapa de aliases em lowercase
    alias_map = {k.lower(): v for k, v in column_aliases.items()}
    
    df_normalized.columns = [alias_map.get(col, col) for col in df_normalized.columns]
    return df_normalized

def normalize_year(value):
    """Garante que o ano seja um inteiro válido ou None."""
    if pd.isna(value):
        return None
    try:
        # Tenta extrair os primeiros 4 dígitos (ex: "2023-10-01" -> 2023)
        match = re.search(r'\d{4}', str(value))
        if match:
            return int(match.group())
        return None
    except (ValueError, TypeError):
        return None

def normalize_doi(doi):
    """Normaliza o DOI removendo protocolos e domínios."""
    if pd.isna(doi) or str(doi).strip() == '':
        return None
    doi = str(doi).lower().strip()
    # Remove prefixos comuns
    doi = doi.replace('https://doi.org/', '')
    doi = doi.replace('http://doi.org/', '')
    doi = doi.replace('doi.org/', '')
    doi = doi.replace('doi:', '')
    return doi

def clean_title(title):
    """Limpa o título para comparação: minúsculo, sem pontuação, sem espaços extras."""
    if pd.isna(title) or str(title).strip() == '':
        return ''
    title_str = str(title).lower().strip()
    # Remove caracteres especiais e pontuação
    title_str = re.sub(r'[^\w\s]', '', title_str)
    # Remove espaços múltiplos
    title_str = re.sub(r'\s+', ' ', title_str)
    return title_str

def standardize_dataframe(df: pd.DataFrame, source: str, column_aliases: dict, source_columns: list) -> pd.DataFrame:
    """Padroniza o DataFrame para o schema do sistema."""
    df = normalize_columns(df, column_aliases)

    if 'year' in df.columns:
        df['year'] = df['year'].apply(normalize_year)
    
    if 'doi' in df.columns:
        df['doi'] = df['doi'].apply(normalize_doi)

    # Garante que todas as colunas esperadas existam
    for col in source_columns:
        if col not in df.columns:
            df[col] = ''

    df['source'] = source
    
    # Determina o tipo de literatura baseado no caminho do arquivo ou nome da fonte
    if 'wl' in source.lower() or 'white' in source.lower():
        df['literature_type'] = 'WL'
    elif 'gl' in source.lower() or 'grey' in source.lower():
        df['literature_type'] = 'GL'
    else:
        df['literature_type'] = 'WL' # Default para WL se não identificado

    return df

def load_csv_files(directory: str, column_aliases: dict, source_columns: list) -> pd.DataFrame:
    """Carrega todos os arquivos CSV de um diretório recursivamente."""
    all_dfs = []
    pattern = os.path.join(directory, '**', '*.csv')
    csv_files = glob.glob(pattern, recursive=True)

    for csv_file in csv_files:
        # Ignora arquivos de backup ou o master_table
        if 'master_table' in csv_file or 'backup' in csv_file:
            continue

        try:
            # Pega o nome da pasta pai como nome da fonte (ex: 'wl' ou 'scopus')
            source_name = os.path.basename(os.path.dirname(csv_file))
            df = pd.read_csv(csv_file, encoding='utf-8', on_bad_lines='skip')
            
            if not df.empty:
                df = standardize_dataframe(df, source_name, column_aliases, source_columns)
                all_dfs.append(df)
                print(f"Loaded: {csv_file} ({len(df)} records)")
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")

    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

def deduplicate_articles(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas usando DOI (primário) e Título+Ano (secundário)."""
    initial_count = len(df)
    df = df.copy()

    # 1. Normalização para deduplicação
    df['title_clean'] = df['title'].apply(clean_title)
    # DOI já foi normalizado no standardize_dataframe

    # 2. Deduplicação por DOI (Apenas se o DOI não for nulo)
    # Criamos máscaras para separar o que tem DOI e o que não tem
    has_doi = df[df['doi'].notna() & (df['doi'] != '')].copy()
    no_doi = df[df['doi'].isna() | (df['doi'] == '')].copy()

    # Remove duplicatas no grupo que tem DOI
    has_doi = has_doi.drop_duplicates(subset=['doi'], keep='first')
    
    # Recombina para o próximo passo
    df = pd.concat([has_doi, no_doi], ignore_index=True)
    doi_removed = initial_count - len(df)
    if doi_removed > 0:
        print(f"Removed {doi_removed} duplicates by DOI normalization.")

    # 3. Deduplicação por Título + Ano
    # Útil para capturar papers sem DOI ou onde o DOI veio errado de uma base
    count_before_title = len(df)
    df = df.drop_duplicates(subset=['title_clean', 'year'], keep='first')
    
    title_removed = count_before_title - len(df)
    if title_removed > 0:
        print(f"Removed {title_removed} duplicates by Title + Year.")

    # Limpeza final
    df = df.drop(columns=['title_clean'])
    
    final_count = len(df)
    print(f"Deduplication Summary: {initial_count} -> {final_count} (Total removed: {initial_count - final_count})")
    return df

def run_ingestion(config_path: str = "project_config.json", db_path: str = "data/aims_project.db"):
    """Pipeline principal de ingestão."""
    print("Starting data ingestion...")

    config = load_config(config_path)
    column_aliases = config.column_aliases
    source_columns = config.source_columns

    db = Database(db_path)

    # Busca em processed (onde o converter.py salvou os arquivos limpos)
    base_dir = "data/processed"
    
    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} not found. Please run converter first.")
        return

    all_data = load_csv_files(base_dir, column_aliases, source_columns)

    if all_data.empty:
        print("No data found to ingest.")
        return

    # Executa deduplicação em memória antes de ir para o banco
    all_data = deduplicate_articles(all_data)

    print(f"Processing {len(all_data)} articles for database insertion...")

    # Upsert no banco de dados (trata colisões se rodar a ingestão múltiplas vezes)
    for _, row in all_data.iterrows():
        article_data = {
            'title': row.get('title', ''),
            'authors': row.get('authors', ''),
            'year': row.get('year'),
            'abstract': row.get('abstract', ''),
            'doi': row.get('doi', ''),
            'url': row.get('url', ''),
            'source': row.get('source', ''),
            'literature_type': row.get('literature_type', 'WL')
        }
        db.upsert_article(article_data)

    print(f"Inserted/updated {len(all_data)} articles in database")

    # Exporta a tabela mestre para CSV (Backup/Auditoria)
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