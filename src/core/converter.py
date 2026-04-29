"""
AIMS Data Converter - Professional Multi-format Support.
Handles: BibTeX (.bib), RIS (.ris), Excel (.xlsx), and WoS Tab-delimited (.txt).
"""
import os
import pandas as pd
import bibtexparser
import rispy
from pathlib import Path
import logging

# Configuração de logging para auditoria de conversão
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def convert_excel_to_df(filepath: str) -> pd.DataFrame:
    """Lê Excel e retorna DataFrame."""
    try:
        return pd.read_excel(filepath)
    except Exception as e:
        logger.error(f"Failed to read Excel {filepath}: {e}")
        return pd.DataFrame()

def convert_bibtex_to_df(filepath: str) -> pd.DataFrame:
    """Converte BibTeX para DataFrame padronizado."""
    try:
        with open(filepath, 'r', encoding='utf-8') as bibfile:
            parser = bibtexparser.bparser.BibTexParser(common_strings=True)
            bib_database = bibtexparser.load(bibfile, parser=parser)
        
        df = pd.DataFrame(bib_database.entries)
        # Mapeamento comum de BibTeX para o padrão AIMS
        mapping = {
            'author': 'authors',
            'journal': 'source_title',
            'booktitle': 'source_title',
        }
        return df.rename(columns=mapping)
    except Exception as e:
        logger.error(f"Failed to read BibTeX {filepath}: {e}")
        return pd.DataFrame()

def convert_ris_to_df(filepath: str) -> pd.DataFrame:
    """Converte RIS (Reference Manager) para DataFrame."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            entries = rispy.load(f)
        
        df = pd.DataFrame(entries)
        # Mapeamento comum de tags RIS (T1/TI = Title, AB = Abstract, etc)
        mapping = {
            'primary_title': 'title',
            'authors': 'authors',
            'publication_year': 'year',
            'abstract': 'abstract',
            'doi': 'doi',
            'url': 'url'
        }
        return df.rename(columns=mapping)
    except Exception as e:
        logger.error(f"Failed to read RIS {filepath}: {e}")
        return pd.DataFrame()

def convert_wos_txt_to_df(filepath: str) -> pd.DataFrame:
    """Converte exportação do Web of Science (Tab-delimited) para DataFrame."""
    try:
        # WoS usa tabulação e encoding específico às vezes
        df = pd.read_csv(filepath, sep='\t', quoting=3, on_bad_lines='skip')
        # WoS usa siglas (TI=Title, AB=Abstract, PY=Year, AU=Authors, DI=DOI)
        mapping = {
            'TI': 'title',
            'AB': 'abstract',
            'PY': 'year',
            'AU': 'authors',
            'DI': 'doi'
        }
        return df.rename(columns=mapping)
    except Exception as e:
        logger.error(f"Failed to read WoS TXT {filepath}: {e}")
        return pd.DataFrame()

def run_conversion(input_dir: str, output_dir: str):
    """
    Orquestrador de conversão. 
    Lê qualquer arquivo suportado em input_dir e salva o CSV em output_dir.
    """
    if not os.path.exists(input_dir):
        logger.warning(f"Input directory {input_dir} not found.")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
    
    for filename in files:
        filepath = os.path.join(input_dir, filename)
        ext = Path(filename).suffix.lower()
        df = pd.DataFrame()

        if ext == '.xlsx':
            df = convert_excel_to_df(filepath)
        elif ext == '.bib':
            df = convert_bibtex_to_df(filepath)
        elif ext == '.ris':
            df = convert_ris_to_df(filepath)
        elif ext == '.txt':
            # Checa se é WoS ou apenas um CSV disfarçado
            df = convert_wos_txt_to_df(filepath)
        elif ext == '.csv':
            # Se já for CSV, apenas lê para validar
            try:
                df = pd.read_csv(filepath, on_bad_lines='skip')
            except:
                continue
        
        if not df.empty:
            # Salva o arquivo convertido com o mesmo nome, mas extensão .csv
            output_filename = f"{Path(filename).stem}.csv"
            output_path = os.path.join(output_dir, output_filename)
            
            # Usamos utf-8-sig para garantir que o Excel abra corretamente os acentos
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logger.info(f"Successfully converted: {filename} -> {output_filename}")
        else:
            logger.warning(f"Skipped or failed to convert: {filename}")

if __name__ == "__main__":
    # Teste manual
    run_conversion("data/raw/wl", "data/processed/wl")