import os
import json
import logging
import time
import random
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List
from functools import wraps
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_ARTICLE_CONTENT_LENGTH = 15000


def retry_on_api_error(max_retries: int = 3, base_delay: float = 1.0, exponential: bool = True):
    """
    Decorator to retry functions that may fail due to API rate limits or network issues.
    Handles RateLimitError, Timeout, and ConnectionError.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    is_retryable = any([
                        'rate' in error_msg and 'limit' in error_msg,
                        'timeout' in error_msg,
                        'connection' in error_msg,
                        'temporarily unavailable' in error_msg,
                        '503' in error_msg,
                        '502' in error_msg,
                        '429' in error_msg,
                    ])
                    if not is_retryable or attempt == max_retries - 1:
                        raise
                    last_exception = e
                    delay = base_delay * (2 ** attempt) if exponential else base_delay
                    logger.warning(f"Retryable error: {e}. Retry {attempt + 1}/{max_retries} in {delay:.1f}s...")
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


def _clean_text(html_content: bytes) -> str:
    """Extract and clean text from HTML content with encoding fallback."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception:
        html_content = b'<html><body>' + html_content[:500000] + b'</body></html>'
        soup = BeautifulSoup(html_content, 'html.parser')
    
    for tag in ['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'iframe']:
        for element in soup.find_all(tag):
            element.decompose()
    
    for tag in soup.find_all(True):
        if tag.name in ['span', 'div']:
            style = tag.get('style', '')
            if 'display:none' in str(style) or 'visibility:hidden' in str(style):
                element.decompose()
    
    main_content = None
    for tag in ['article', 'main', 'div[@role="main"]', 'section']:
        main_content = soup.find(tag)
        if main_content:
            break
    
    if not main_content:
        main_content = soup.body
    
    if not main_content:
        main_content = soup
    
    text_elements = main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre'])
    text_content = []
    for elem in text_elements:
        text = elem.get_text(strip=True)
        if len(text) > 30:
            text = ' '.join(text.split())
            text_content.append(text)
    
    full_text = ' '.join(text_content[:80])
    
    if len(full_text) < 200:
        full_text = soup.get_text(separator=' ', strip=True)
        full_text = ' '.join(full_text.split())
    
    return full_text[:20000] if full_text else ""


def scrape_url(url: str, timeout: int = 30) -> Optional[str]:
    """Scrape main text content from a URL using requests and BeautifulSoup."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        raw_content = response.content
        enc = response.encoding or 'utf-8'
        
        if enc.lower() not in ['utf-8', 'iso-8859-1', 'windows-1252']:
            try:
                text = raw_content.decode(enc)
            except (UnicodeDecodeError, LookupError):
                decoded = False
                for encoding in ['utf-8', 'windows-1252', 'iso-8859-1', 'latin-1']:
                    try:
                        text = raw_content.decode(encoding)
                        decoded = True
                        break
                    except UnicodeDecodeError:
                        continue
                if not decoded:
                    text = raw_content.decode('utf-8', errors='ignore')
        else:
            text = response.text
        
        content_bytes = text.encode('utf-8') if isinstance(text, str) else raw_content
        full_text = _clean_text(content_bytes)
        
        if full_text and len(full_text) < 100:
            logger.warning(f"Minimal content scraped from {url}: {len(full_text)} chars")
        
        return full_text if full_text else None
        
    except requests.RequestException as e:
        logger.error(f"Scraping error for {url}: {e}")
        return None


def evaluate_thematic_saturation(
    article_content: str,
    article_title: str,
    project_themes: str,
    research_questions: List[str],
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Evaluate if article provides new thematic evidence or thematic saturation reached.
    
    Returns:
        Dict with is_new (bool), reasoning (str), suggested_tags (list)
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY not found in environment variables.")
        return {
            "is_new": False,
            "reasoning": "API key not configured",
            "suggested_tags": []
        }
    
    return _call_saturation_api(api_key, article_content, article_title, project_themes, research_questions)


@retry_on_api_error(max_retries=3, base_delay=2.0)
def _call_saturation_api(
    api_key: str,
    article_content: str,
    article_title: str,
    project_themes: str,
    research_questions: List[str]
) -> Dict[str, Any]:
    """Internal function to call the saturation API with retry support."""
    client = Groq(api_key=api_key)
    
    rq_context = "\n".join([f"- {rq}" for rq in research_questions])
    
    system_prompt = f"""
You are a Senior Research Assistant specialized in Multivocal Literature Reviews (MLR).
Your task is to evaluate Grey Literature (GL) articles for thematic saturation checking per Garousi et al. (2019).

### RESEARCH QUESTIONS (Base all decisions on these):
{rq_context}

### PROJECT THEMES (Established knowledge base - avoid redudancy):
{project_themes if project_themes else "No themes defined yet."}

### INSTRUCTIONS (STRICT):
Your goal is to identify if the NEW article provides unique evidence NOT present in the existing themes or recent context.
1. If the article ONLY confirms what is already known WITHOUT adding new practical insights, challenges, or stage-specific details, mark 'is_new' as false.
2. Only mark 'is_new' as true if the article provides genuinely new: methodologies, populations, contexts, contradictory findings, or practitioner insights.
3. Be conservative - prefer false (saturation) when uncertain.

### OUTPUT FORMAT:
Return ONLY valid JSON with this exact structure:
{{
    "is_new": boolean,
    "reasoning": "Detailed explanation of why this is new or redundant",
    "suggested_tags": ["tag1", "tag2", ...] (max 5 tags, relevant to themes/RQs)
}}

### DECISION CRITERIA:
- is_new = true: Article provides NEW evidence, patterns, or perspectives NOT in existing themes
- is_new = false: Article confirms existing themes without novel contributions (saturation reached)
- Consider: novel methodologies, new populations, different contexts, contradictory findings
"""

    user_content = f"""
TITLE: {article_title}

CONTENT:
{article_content[:MAX_ARTICLE_CONTENT_LENGTH] if len(article_content) > MAX_ARTICLE_CONTENT_LENGTH else article_content}
"""
    
    if len(article_content) > MAX_ARTICLE_CONTENT_LENGTH:
        logger.info(f"Content truncated from {len(article_content)} to {MAX_ARTICLE_CONTENT_LENGTH} chars for '{article_title[:30]}...'")
    
    rq_context = rq_context if rq_context.strip() else "No research questions defined yet."
    project_themes = project_themes if project_themes.strip() else "No established themes yet."
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = raw_content
        
        result = json.loads(json_str)
        
        is_new = result.get("is_new", False)
        decision = "Accepted" if is_new else "Skipped (saturation)"
        reasoning = result.get("reasoning", "")[:150]
        
        logger.info(f"Saturation decision for '{article_title[:30]}...': {decision}")
        logger.info(f"Reasoning: {reasoning}")
        
        return {
            "is_new": is_new,
            "reasoning": result.get("reasoning", ""),
            "suggested_tags": result.get("suggested_tags", [])
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {"is_new": False, "reasoning": "Invalid response format from LLM", "suggested_tags": []}


def process_gl_ingestion(
    tsv_data: pd.DataFrame,
    project_themes: str,
    research_questions: List[str],
    progress_callback=None
) -> List[Dict[str, Any]]:
    """
    Process GL ingestion: scrape URLs, evaluate saturation, return results.
    
    Args:
        tsv_data: DataFrame with columns Position, Title, URL
        project_themes: Current project themes summary
        research_questions: List of research question strings
        progress_callback: Optional callback function(current, total, status)
    
    Returns:
        List of result dicts with article data and saturation evaluation
    """
    results = []
    total = len(tsv_data)
    
    for idx, row in tsv_data.iterrows():
        position = row.get('Position', idx + 1)
        title = row.get('Title', '')
        url = row.get('URL', '')
        
        if progress_callback:
            progress_callback(idx + 1, total, f"Scraping: {title[:40]}...")
        
        scraped_content = scrape_url(url)
        
        if not scraped_content:
            results.append({
                "position": position,
                "title": title,
                "url": url,
                "content": None,
                "saturation": {
                    "is_new": False,
                    "reasoning": "Failed to scrape content",
                    "suggested_tags": []
                },
                "status": "failed"
            })
            continue
        
        if progress_callback:
            progress_callback(idx + 1, total, f"Evaluating saturation: {title[:40]}...")
        
        saturation = evaluate_thematic_saturation(
            scraped_content,
            title,
            project_themes,
            research_questions
        )
        
        results.append({
            "position": position,
            "title": title,
            "url": url,
            "content": scraped_content,
            "saturation": saturation,
            "status": "processed" if saturation.get("is_new") else "saturated"
        })
        
        if idx < total - 1:
            delay = random.uniform(1.5, 3.5)
            logger.info(f"Polite delay: sleeping {delay:.1f}s before next URL")
            time.sleep(delay)
    
    return results