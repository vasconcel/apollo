"""
Utility functions for replicability packages.
"""
import os
import zipfile
import json
import shutil
from datetime import datetime
from pathlib import Path


def create_replication_package(
    output_dir: str = "output",
    config_file: str = "project_config.json"
) -> str:
    """
    Create a timestamped ZIP package with all research artifacts.
    
    Args:
        output_dir: Directory to save the ZIP file
        config_file: Path to project config
        
    Returns:
        Path to created ZIP file
    """
    # Create timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"aims_replication_{timestamp}.zip"
    package_path = os.path.join(output_dir, package_name)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        
        # 1. Project Configuration
        if os.path.exists(config_file):
            zipf.write(config_file, f"project_config.json")
        
        # 2. Database file
        db_path = "aims.db"
        if os.path.exists(db_path):
            zipf.write(db_path, "aims_database.db")
        
        # 3. Exported CSVs
        export_files = [
            "output/traceability_matrix.csv",
            "output/fragments_with_sources.csv", 
            "output/codes.csv",
            "output/themes.csv"
        ]
        for f in export_files:
            if os.path.exists(f):
                zipf.write(f, os.path.basename(f))
        
        # 4. BibTeX export
        bib_path = "output/final_included.bib"
        if os.path.exists(bib_path):
            zipf.write(bib_path, "final_included.bib")
        
        # 5. Logs directory
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            for log_file in os.listdir(logs_dir):
                if log_file.endswith(".log"):
                    zipf.write(
                        os.path.join(logs_dir, log_file),
                        f"logs/{log_file}"
                    )
        
        # 6. README with metadata
        readme_content = f"""AIMS Replication Package
Generated: {datetime.now().isoformat()}

Contents:
- project_config.json: Research protocol configuration
- aims_database.db: SQLite database with all research data
- *.csv: Exported research artifacts
- final_included.bib: BibTeX for final included articles

To replicate: Use AIMS pipeline with the same project_config.json
"""
        zipf.writestr("README.txt", readme_content)
    
    return package_path


def get_package_contents(package_path: str) -> dict:
    """
    Get contents of a replication package without extracting.
    
    Args:
        package_path: Path to ZIP file
        
    Returns:
        Dictionary with file list and sizes
    """
    with zipfile.ZipFile(package_path, 'r') as zipf:
        info = {
            "files": zipf.namelist(),
            "total_size": sum(f.file_size for f in zipf.filelist)
        }
    return info