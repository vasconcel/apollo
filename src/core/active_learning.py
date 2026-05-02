"""
Active Learning Module for AI-Assisted Pre-Screening.
Fetches recent human decisions to create few-shot context for the LLM.
"""
import sqlite3
import pandas as pd
from typing import Dict, List, Any, Optional


def get_training_context(db, reviewer_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Fetch recent Include/Exclude decisions to create few-shot training context.
    
    Args:
        db: Database instance
        reviewer_id: ID of the reviewer to learn from
        limit: Number of recent decisions to fetch per class
        
    Returns:
        Dictionary with includes, excludes formatted for prompt injection
    """
    conn = sqlite3.connect(db.db_path)
    
    # Get recent INCLUDEs
    includes = pd.read_sql_query("""
        SELECT a.title, a.abstract, sd.exclusion_reason, sd.criteria_snapshot
        FROM screening_decisions sd
        JOIN articles a ON sd.article_id = a.id
        WHERE sd.reviewer_id = ? AND sd.decision = 'include'
        ORDER BY sd.created_at DESC
        LIMIT ?
    """, conn, params=(reviewer_id, limit))
    
    # Get recent EXCLUDEs
    excludes = pd.read_sql_query("""
        SELECT a.title, a.abstract, sd.exclusion_reason, sd.criteria_snapshot
        FROM screening_decisions sd
        JOIN articles a ON sd.article_id = a.id
        WHERE sd.reviewer_id = ? AND sd.decision = 'exclude'
        ORDER BY sd.created_at DESC
        LIMIT ?
    """, conn, params=(reviewer_id, limit))
    
    conn.close()
    
    # Format into few-shot examples
    include_examples = []
    for _, row in includes.iterrows():
        text = f"Title: {row['title'][:100]}..."
        if row.get('abstract'):
            text += f"\nAbstract: {row['abstract'][:200]}..."
        include_examples.append(text)
    
    exclude_examples = []
    for _, row in excludes.iterrows():
        text = f"Title: {row['title'][:100]}..."
        if row.get('abstract'):
            text += f"\nAbstract: {row['abstract'][:200]}..."
        if row.get('exclusion_reason'):
            text += f"\nExcluded because: {row['exclusion_reason']}"
        exclude_examples.append(text)
    
    return {
        "include_examples": include_examples,
        "exclude_examples": exclude_examples,
        "total_includes": len(includes),
        "total_excludes": len(excludes)
    }


def format_few_shot_prompt(context: Dict[str, Any], settings: Dict[str, Any]) -> str:
    """
    Format training context into a few-shot prompt for the LLM.
    
    Args:
        context: Output from get_training_context()
        settings: Research protocol settings
        
    Returns:
        Formatted prompt string
    """
    # Format inclusion examples
    include_block = "\n\n".join([
        f"Example {i+1} (INCLUDED):\n{ex}"
        for i, ex in enumerate(context["include_examples"][:10])
    ])
    
    # Format exclusion examples  
    exclude_block = "\n\n".join([
        f"Example {i+1} (EXCLUDED):\n{ex}"
        for i, ex in enumerate(context["exclude_examples"][:10])
    ])
    
    # Build protocol context
    ic_context = "\n".join([f"- {k}: {v}" for k, v in settings.get("inclusion_criteria", {}).items()])
    ec_context = "\n".join([f"- {k}: {v}" for k, v in settings.get("exclusion_criteria", {}).items()])
    
    prompt = f"""
You are analyzing articles based on a reviewer's previous decisions.

### INCLUSION CRITERIA:
{ic_context}

### EXCLUSION CRITERIA:
{ec_context}

### YOUR TRAINING EXAMPLES (INCLUDED by this reviewer):
{include_block}

### YOUR TRAINING EXAMPLES (EXCLUDED by this reviewer):
{exclude_block}

### HOW TO USE:
Based on the patterns above, evaluate the new articles below.
Provide each decision with confidence (0-100%).
"""
    
    return prompt


def get_pending_articles_for_screening(db, reviewer_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get pending articles ready for batch AI screening.
    
    Args:
        db: Database instance
        reviewer_id: ID of reviewer
        limit: Maximum articles to fetch
        
    Returns:
        List of article dictionaries with metadata
    """
    conn = sqlite3.connect(db.db_path)
    
    articles = pd.read_sql_query("""
        SELECT a.id, a.title, a.abstract, a.authors, a.year, a.literature_type
        FROM articles a
        WHERE a.id NOT IN (
            SELECT article_id FROM screening_decisions WHERE reviewer_id = ?
        )
        ORDER BY a.id
        LIMIT ?
    """, conn, params=(reviewer_id, limit))
    
    conn.close()
    
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "abstract": row["abstract"] or "",
            "authors": row["authors"] or "Unknown",
            "year": row["year"],
            "literature_type": row["literature_type"]
        }
        for _, row in articles.iterrows()
    ]


def batch_predict_prompt(articles: List[Dict], few_shot_context: str) -> tuple:
    """
    Create a batch prediction prompt and article list for the LLM.
    
    Args:
        articles: List of article metadata
        few_shot_context: Formatted few-shot context
        
    Returns:
        Tuple of (prompt, articles_list)
    """
    # Format articles for batch evaluation
    articles_text = "\n\n".join([
        f"Article {i+1}:\nID: {a['id']}\nTitle: {a['title'][:100]}...\nAbstract: {a['abstract'][:150]}..."
        for i, a in enumerate(articles)
    ])
    
    prompt = f"""{few_shot_context}

### NEW ARTICLES TO EVALUATE:
{articles_text}

### RESPONSE FORMAT (JSON array):
[{{"id": <article_id>, "decision": "include"|"exclude", "confidence": <0-100>, "reason": "<brief>"}}, ...]

Evaluate all articles based on the patterns from training."""
    
    return prompt, articles


def get_queued_predictions(article_ids: List[int], db) -> Dict[int, Dict]:
    """
    Get existing AI predictions for articles.
    
    Args:
        article_ids: List of article IDs
        db: Database instance
        
    Returns:
        Dictionary mapping article_id to prediction
    """
    if not article_ids:
        return {}
    
    conn = sqlite3.connect(db.db_path)
    
    # Check for existing predictions in session_state would be handled in app.py
    # This is for the database check if we store predictions
    
    conn.close()
    return {}