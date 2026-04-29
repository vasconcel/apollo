"""
AIMS Data Converter.
Converts various file formats (BibTeX, RIS, Excel, WoS TSV) to standardized CSV.
"""
import os
import pandas as pd
import bibtexparser
from pathlib import Path

try:
    from rispy import loads as rispy_loads
    RISPY_AVAILABLE = True
except ImportError:
    RISPY_AVAILABLE = False


def convert_excel_to_csv(filepath: str) -> pd.DataFrame:
    """Read Excel file and return DataFrame."""
    try:
        df = pd.read_excel(filepath)
        return df
    except Exception as e:
        print(f"Error reading Excel {filepath}: {e}")
        return pd.DataFrame()


def convert_bibtex_to_csv(filepath: str) -> pd.DataFrame:
    """Read BibTeX file and return DataFrame."""
    try:
        with open(filepath, 'r', encoding='utf-8') as bibfile:
            bib_database = bibtexparser.load(bibfile)

        entries = []
        for entry in bib_database.entries:
            normalized_entry = {
                'title': entry.get('title', ''),
                'year': entry.get('year', ''),
                'abstract': entry.get('abstract', ''),
                'doi': entry.get('doi', ''),
                'authors': entry.get('author', ''),
                'journal': entry.get('journal', entry.get('booktitle', '')),
                'keywords': entry.get('keywords', ''),
                'volume': entry.get('volume', ''),
                'issue': entry.get('number', ''),
                'pages': entry.get('pages', ''),
                'url': entry.get('url', ''),
                'ENTRYTYPE': entry.get('ENTRYTYPE', '')
            }
            entries.append(normalized_entry)

        return pd.DataFrame(entries)
    except Exception as e:
        print(f"Error reading BibTeX {filepath}: {e}")
        return pd.DataFrame()


def convert_ris_to_csv(filepath: str) -> pd.DataFrame:
    """Read RIS file and return DataFrame."""
    try:
        if RISPY_AVAILABLE:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            tags = rispy_loads(content)
            return pd.DataFrame(tags)
        else:
            df = pd.read_csv(filepath, sep='\t')
            return df
    except Exception as e:
        print(f"Error reading RIS {filepath}: {e}")
        return pd.DataFrame()


def convert_wos_txt_to_csv(filepath: str) -> pd.DataFrame:
    """Read Web of Science (.txt TSV) and return DataFrame."""
    try:
        df = pd.read_csv(filepath, sep='\t', quoting=3, on_bad_lines='skip', encoding='utf-8-sig')
        return df
    except Exception as e:
        print(f"Error reading WoS {filepath}: {e}")
        return pd.DataFrame()


def convert_file(filepath: str, output_dir: str = "data/processed/wl") -> bool:
    """Convert a single file to CSV."""
    ext = Path(filepath).suffix.lower()
    filename = Path(filepath).stem

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.csv")

    if ext == '.xlsx':
        df = convert_excel_to_csv(filepath)
        if not df.empty:
            df.to_csv(output_path, index=False)
            print(f"Converted: {filepath} -> {output_path}")
            return True
    elif ext == '.bib':
        df = convert_bibtex_to_csv(filepath)
        if not df.empty:
            df.to_csv(output_path, index=False)
            print(f"Converted: {filepath} -> {output_path}")
            return True
    elif ext == '.ris':
        df = convert_ris_to_csv(filepath)
        if not df.empty:
            df.to_csv(output_path, index=False)
            print(f"Converted: {filepath} -> {output_path}")
            return True
    elif ext == '.txt':
        df = convert_wos_txt_to_csv(filepath)
        if not df.empty:
            df.to_csv(output_path, index=False)
            print(f"Converted: {filepath} -> {output_path}")
            return True
    else:
        print(f"Unsupported format: {ext}")

    return False


def run_conversion(input_dir: str = "data/raw/wl", output_dir: str = "data/processed/wl"):
    """Scan input directory and convert all supported files."""
    if not os.path.exists(input_dir):
        print(f"Input directory {input_dir} does not exist. Creating...")
        os.makedirs(input_dir, exist_ok=True)
        return

    files_to_convert = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(('.xlsx', '.bib', '.ris', '.txt')):
                filepath = os.path.join(root, file)
                files_to_convert.append(filepath)

    if not files_to_convert:
        print(f"No convertible files (.xlsx, .bib, .ris, .txt) found in {input_dir}")
        return

    print(f"Found {len(files_to_convert)} files to convert")

    for filepath in files_to_convert:
        convert_file(filepath, output_dir)


if __name__ == "__main__":
    run_conversion()