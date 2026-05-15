"""
Debug script to trace year pipeline at runtime.
Run this to see actual year values at each stage.
"""
import pandas as pd
import tempfile
import os
from src.core.article_metadata import normalize_wl_metadata, _get_year

# Find a test ATLAS file
def find_atlas_file():
    """Find ATLAS Excel file."""
    search_dirs = [
        "D:/Projetos/apollo/data",
        "D:/Projetos/apollo/uploads", 
        "D:/Projetos/apollo/test_data",
        ".",
    ]
    for d in search_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith('.xlsx') and 'atlas' in f.lower():
                    return os.path.join(d, f)
    return None

def debug_year_extraction():
    """Debug year extraction from real ATLAS file."""
    atlas_file = find_atlas_file()
    
    if not atlas_file:
        print("No ATLAS file found. Please provide a test file.")
        return
    
    print(f"=== USING FILE: {atlas_file} ===\n")
    
    # Load Excel
    wl_df = pd.read_excel(atlas_file, sheet_name="White Literature")
    print(f"Loaded {len(wl_df)} WL rows")
    print(f"Columns: {list(wl_df.columns)}\n")
    
    # Check Year column
    if 'Year' in wl_df.columns:
        print("=== YEAR COLUMN ANALYSIS ===")
        for idx, row in wl_df.head(5).iterrows():
            raw_year = row.get('Year')
            print(f"\n--- Row {idx} ---")
            print(f"  Raw value: {repr(raw_year)}")
            print(f"  Type: {type(raw_year)}")
            print(f"  Is NaN: {pd.isna(raw_year)}")
            
            # Test _get_year function
            row_dict = row.to_dict()
            extracted_year = _get_year(row_dict)
            print(f"  _get_year() returned: {repr(extracted_year)}")
            
            # Test full normalization
            article = normalize_wl_metadata(row_dict)
            print(f"  normalize_wl_metadata().year: {repr(article.year)}")
    else:
        print("ERROR: No 'Year' column found!")
        print(f"Available columns: {wl_df.columns.tolist()}")

if __name__ == "__main__":
    debug_year_extraction()