# src/core/utils.py
"""AIMS Utility Functions."""
import logging
import os
from datetime import datetime
import shutil


def get_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """Create a logger with file and console handlers."""
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(f"{log_dir}/{name}_{timestamp}.log")
    ch = logging.StreamHandler()
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def snapshot(filepath: str, snapshot_dir: str = "data/snapshots") -> str | None:
    """Create a timestamped snapshot of a file."""
    if os.path.exists(filepath):
        os.makedirs(snapshot_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = os.path.basename(filepath)
        shutil.copy(filepath, f"{snapshot_dir}/{ts}_{name}")
        return f"{snapshot_dir}/{ts}_{name}"
    return None