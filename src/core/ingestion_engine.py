"""
APOLLO Ingestion Engine - ATLAS Excel Loader

Loads and normalizes ATLAS Excel exports. Schema v2.0 compatible.
Separated from atlas_processor for testability.
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any


class ATLASLoader:
    """Load and parse ATLAS Excel exports - Schema v2.0 compatible."""
    
    WL_REQUIRED_COLUMNS = {"Title"}
    WL_RECOMMENDED_COLUMNS = {"Global_ID", "Local_ID", "Abstract"}
    GL_REQUIRED_COLUMNS = {"Title", "URL"}
    GL_RECOMMENDED_COLUMNS = {"Source_File"}
    
    WL_SHEET_ALIASES = ["WL", "wl", "White Literature", "white literature", "WHITE LITERATURE"]
    GL_SHEET_ALIASES = ["GL", "gl", "Grey Literature", "grey literature", "GREY LITERATURE"]
    
    @staticmethod
    def find_sheet(xl: pd.ExcelFile, possible_names: List[str]) -> Optional[str]:
        available = xl.sheet_names
        for name in possible_names:
            if name in available:
                return name
        return None
    
    @staticmethod
    def validate_wl_schema(df: pd.DataFrame) -> Dict[str, any]:
        columns = set(df.columns)
        missing_required = ATLASLoader.WL_REQUIRED_COLUMNS - columns
        missing_recommended = ATLASLoader.WL_RECOMMENDED_COLUMNS - columns
        
        return {
            "is_valid": len(missing_required) == 0,
            "missing_required": sorted(missing_required),
            "missing_recommended": sorted(missing_recommended),
            "warnings": [f"Missing recommended WL columns: {sorted(missing_recommended)}" if missing_recommended else None],
            "row_count": len(df),
            "schema_version": "2.0"
        }
    
    @staticmethod
    def validate_gl_schema(df: pd.DataFrame) -> Dict[str, any]:
        columns = set(df.columns)
        missing_required = ATLASLoader.GL_REQUIRED_COLUMNS - columns
        missing_recommended = ATLASLoader.GL_RECOMMENDED_COLUMNS - columns
        
        return {
            "is_valid": len(missing_required) == 0,
            "missing_required": sorted(missing_required),
            "missing_recommended": sorted(missing_recommended),
            "warnings": [f"Missing recommended GL columns: {sorted(missing_recommended)}" if missing_recommended else None],
            "row_count": len(df),
            "schema_version": "2.0"
        }
    
    @staticmethod
    def load_atlas_file(file_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        try:
            xl = pd.ExcelFile(file_path)
        except Exception as e:
            raise ValueError(f"Cannot open Excel file {file_path}: {e}")
        
        wl_sheet = ATLASLoader.find_sheet(xl, ATLASLoader.WL_SHEET_ALIASES)
        gl_sheet = ATLASLoader.find_sheet(xl, ATLASLoader.GL_SHEET_ALIASES)
        
        if not wl_sheet:
            raise ValueError(f"Cannot find WL sheet. Expected one of: {ATLASLoader.WL_SHEET_ALIASES}")
        if not gl_sheet:
            raise ValueError(f"Cannot find GL sheet. Expected one of: {ATLASLoader.GL_SHEET_ALIASES}")
        
        wl_df = pd.read_excel(file_path, sheet_name=wl_sheet)
        gl_df = pd.read_excel(file_path, sheet_name=gl_sheet)
        
        return wl_df, gl_df
    
    @staticmethod
    def normalize_wl_columns(df: pd.DataFrame) -> pd.DataFrame:
        cols_to_ensure = ["Global_ID", "Local_ID", "Library", "Authors", "Year",
                          "Venue", "Publisher", "DOI", "URL", "Abstract", "Keywords",
                          "Literature_Type", "Search_String", "Retrieval_Date", "Language",
                          "Completeness_Score", "Duplicate_Flag", "Detected_Source",
                          "Parser_Used", "Provenance_Trace"]
        for col in cols_to_ensure:
            if col not in df.columns:
                df[col] = ""
        return df
    
    @staticmethod
    def normalize_gl_columns(df: pd.DataFrame) -> pd.DataFrame:
        cols_to_ensure = ["#", "Title", "URL", "Source_File", "Detected_Source",
                          "Parser_Used", "Metadata_Completeness", "Provenance_Trace"]
        for col in cols_to_ensure:
            if col not in df.columns:
                df[col] = ""
        return df