"""
APOLLO CLI - Single Export Endpoint
Usage: python scripts/process_atlas.py input.xlsx [--no-llm]

Output: APOLLO_Selection_Criteria.xlsx (single file, 3 sheets)
"""
import sys
import argparse
from pathlib import Path
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.atlas_processor import export_apollo_selection_criteria

__version__ = "1.0.0"
__protocol_version__ = "1.0"


def main():
    parser = argparse.ArgumentParser(description="APOLLO - EC/IC/QC Decision Engine")
    parser.add_argument("input", nargs="?", help="Input ATLAS Excel file (default: ATLAS_Master_Initial_Search.xlsx)")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM reasoning")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--version", action="store_true", help="Show version information")
    
    args = parser.parse_args()
    
    if args.version:
        print(f"APOLLO {__version__}")
        print(f"Protocol {__protocol_version__}")
        sys.exit(0)
    
    # Default input file
    input_file = args.input if args.input else "ATLAS_Master_Initial_Search.xlsx"
    
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    try:
        output_path = export_apollo_selection_criteria(
            input_path=input_file,
            output_filename="APOLLO_Selection_Criteria.xlsx",
            enable_llm=not args.no_llm
        )
        
        print(f"\n✓ Export complete: {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()