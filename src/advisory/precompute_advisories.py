"""
Precompute advisories entrypoint for APOLLO.

This script:
1. Loads articles from session or file
2. Builds advisory queue
3. Processes entire corpus offline
4. Persists advisories to disk

Supports large-scale (2k-10k) batches with crash-safe checkpointing.

Usage:
    python precompute_advisories.py [--limit N] [--protocol-version VERSION] [--checkpoint FILE]

Goal:
Researchers open APOLLO with advisories already materialized.
No runtime LLM calls needed during screening.
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.advisory.advisory_models import AdvisoryConfig
from src.advisory.advisory_queue import get_advisory_queue, build_queue
from src.advisory.advisory_worker import run_worker
from src.advisory.advisory_cache import get_advisory_cache, store_advisory


CHECKPOINT_DIR = Path(__file__).parent.parent.parent / "data" / "checkpoints"


def load_articles_from_session() -> List:
    """Load articles from Streamlit session if available."""
    try:
        import streamlit as st

        if "articles" in st.session_state:
            articles = st.session_state.get("articles", [])
            if articles:
                print(f"Loaded {len(articles)} articles from session")
                return articles

        if "screened_articles" in st.session_state:
            articles = st.session_state.get("screened_articles", [])
            if articles:
                print(f"Loaded {len(articles)} screened articles from session")
                return articles

    except ImportError:
        pass

    return []


def load_articles_from_json(file_path: str) -> List:
    """Load articles from JSON file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and "articles" in data:
        return data["articles"]

    raise ValueError(f"Unexpected JSON structure in {file_path}")


def load_articles_from_csv(file_path: str) -> List:
    """Load articles from CSV file."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas required for CSV loading")

    df = pd.read_csv(file_path)

    articles = []
    for idx, row in df.iterrows():
        article = {
            "article_id": row.get("article_id", f"idx_{idx}"),
            "title": row.get("title", ""),
            "abstract": row.get("abstract", ""),
            "literature_type": row.get("literature_type", "WL")
        }

        for col in df.columns:
            if col not in ["article_id", "title", "abstract", "literature_type"]:
                article[col] = row.get(col)

        articles.append(article)

    return articles


def load_articles_from_directory(dir_path: str) -> List:
    """Load articles from directory of JSON files."""
    path = Path(dir_path)
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    articles = []

    for json_file in path.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                article = json.load(f)
                articles.append(article)
        except Exception as e:
            print(f"Warning: Failed to load {json_file}: {e}")

    print(f"Loaded {len(articles)} articles from {dir_path}")
    return articles


def get_articles(source: Optional[str] = None) -> List:
    """
    Get articles from various sources.

    Priority:
    1. Session (Streamlit)
    2. File path (JSON/CSV)
    3. Directory
    """
    if source is None:
        articles = load_articles_from_session()
        if articles:
            return articles

        default_paths = [
            "data/articles.json",
            "data/screened_articles.json",
            "exports/articles.json"
        ]

        for p in default_paths:
            if Path(p).exists():
                print(f"Using default: {p}")
                return load_articles_from_json(p)

        raise ValueError("No articles found. Provide --source or ensure session has articles.")

    path = Path(source)

    if not path.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    if path.is_dir():
        return load_articles_from_directory(source)

    if path.suffix == ".json":
        return load_articles_from_json(source)

    if path.suffix == ".csv":
        return load_articles_from_csv(source)

    raise ValueError(f"Unsupported source type: {source}")


def save_checkpoint(state: dict, checkpoint_path: Path) -> None:
    """Atomically persist checkpoint to disk."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = checkpoint_path.with_suffix(".tmp")
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, default=str)
    tmp.replace(checkpoint_path)
    print(f"  Checkpoint saved: {checkpoint_path.name} ({len(state.get('completed', []))}/{len(state.get('completed', [])) + state.get('remaining', 0)})


def load_checkpoint(checkpoint_path: Path) -> Optional[Dict]:
    """Load checkpoint if it exists and is valid."""
    if not checkpoint_path.exists():
        return None
    try:
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Warning: Corrupt checkpoint {checkpoint_path}: {e}")
        return None


def run_precompute(
    source: Optional[str] = None,
    limit: Optional[int] = None,
    protocol_version: str = "1.0",
    skip_existing: bool = True,
    config: Optional[AdvisoryConfig] = None,
    checkpoint_interval: int = 100,
    checkpoint_name: Optional[str] = None,
    resume: bool = False,
) -> Dict:
    """
    Run precomputation pipeline with crash-safe checkpointing.

    Args:
        source: Articles source (file/directory/session)
        limit: Maximum articles to process
        protocol_version: Protocol version
        skip_existing: Skip articles with existing advisories
        config: Advisory configuration
        checkpoint_interval: Save checkpoint every N items
        checkpoint_name: Custom checkpoint filename stem
        resume: Resume from last checkpoint

    Returns:
        Processing summary
    """
    print("=" * 60)
    print("APOLLO Advisory Precompute")
    print(f"Protocol version: {protocol_version}")
    print("=" * 60)

    config = config or AdvisoryConfig()

    print("\n[1/4] Loading articles...")
    articles = get_articles(source)
    print(f"  Loaded {len(articles)} articles")

    if limit:
        articles = articles[:limit]
        print(f"  Limited to {limit} articles")

    print("\n[2/4] Building advisory queue...")
    if resume:
        ckpt_name = checkpoint_name or "precompute"
        ckpt_path = CHECKPOINT_DIR / f"{ckpt_name}.json"
        ckpt = load_checkpoint(ckpt_path)
        if ckpt:
            completed_ids = set(ckpt.get("completed", []))
            new_articles = [a for a in articles if a.get("article_id") not in completed_ids]
            print(f"  Resuming: {len(completed_ids)} already done, {len(new_articles)} remaining")
            articles = new_articles
        else:
            print("  No checkpoint found; starting fresh")

    queue = get_advisory_queue(config)
    state = queue.build_from_articles(
        articles,
        protocol_version=protocol_version,
        skip_existing=skip_existing
    )
    print(f"  Queue built: {state.status_summary}")

    print("\n[3/4] Processing advisories...")
    start_time = datetime.now()

    result = run_worker(max_items=limit, config=config)

    elapsed = (datetime.now() - start_time).total_seconds()

    print("\n[4/4] Final statistics...")
    stats = queue.get_stats()

    print(f"\n{'=' * 60}")
    print("PRECOMPLETE COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total articles:     {stats['total']}")
    print(f"Processed:          {result['processed']}")
    print(f"Succeeded:          {result['succeeded']}")
    print(f"Failed:             {result['failed']}")
    print(f"Remaining:          {result['remaining']}")
    print(f"Completion rate:    {stats['completion_rate']:.1%}")
    print(f"Time elapsed:       {elapsed:.1f}s")
    print(f"Throughput:         {result['processed'] / max(elapsed, 1):.2f} items/sec")
    print(f"{'=' * 60}")

    return {
        **result,
        **stats,
        "elapsed_seconds": elapsed
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Precompute advisories for APOLLO corpus"
    )

    parser.add_argument(
        "--source",
        "-s",
        help="Articles source (JSON/CSV file or directory)"
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Maximum articles to process"
    )

    parser.add_argument(
        "--protocol-version",
        "-p",
        default="1.0",
        help="Protocol version (default: 1.0)"
    )

    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Process all articles, skip existing advisories"
    )

    parser.add_argument(
        "--rate-limit",
        type=int,
        default=20,
        help="Max requests per minute (default: 20)"
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=3.0,
        help="Sleep between requests in seconds (default: 3.0)"
    )

    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Checkpoint every N items (default: 100)"
    )

    parser.add_argument(
        "--checkpoint-name",
        help="Checkpoint filename stem (default: auto)"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint"
    )

    args = parser.parse_args()

    config = AdvisoryConfig(
        max_requests_per_minute=args.rate_limit,
        sleep_seconds=args.sleep
    )

    try:
        result = run_precompute(
            source=args.source,
            limit=args.limit,
            protocol_version=args.protocol_version,
            skip_existing=not args.no_skip_existing,
            config=config,
            checkpoint_interval=args.checkpoint_interval,
            checkpoint_name=args.checkpoint_name,
            resume=args.resume,
        )

        sys.exit(0 if result['failed'] == 0 else 1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
