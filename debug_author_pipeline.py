"""
Debug script to trace author string at every stage.
"""
import pandas as pd
from src.core.article_metadata import decode_author_string, normalize_wl_metadata

def debug_author_pipeline():
    """Debug author string processing."""
    atlas_file = "ATLAS_Master_Initial_Search.xlsx"
    
    wl_df = pd.read_excel(atlas_file, sheet_name="White Literature")
    
    print("=== AUTHOR DECODING FORENSICS ===\n")
    
    # Check if Authors column exists
    if 'Authors' not in wl_df.columns:
        print("ERROR: No 'Authors' column!")
        print(f"Available: {wl_df.columns.tolist()}")
        return
    
    print("Sample author values (first 5):")
    for idx, row in wl_df.head(5).iterrows():
        raw_authors = row.get('Authors', '')
        print(f"\n--- Row {idx} ---")
        print(f"  Raw: {repr(raw_authors)}")
        print(f"  Type: {type(raw_authors)}")
        
        # Test decode_author_string
        decoded = decode_author_string(raw_authors)
        print(f"  decode_author_string(): {repr(decoded)}")
        
        # Test full normalization
        row_dict = row.to_dict()
        article = normalize_wl_metadata(row_dict)
        print(f"  normalize_wl_metadata().authors: {repr(article.authors)}")

if __name__ == "__main__":
    debug_author_pipeline()