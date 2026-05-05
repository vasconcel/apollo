import os
import json
import logging
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def read_tsv_file(file_path: str) -> pd.DataFrame:
    """Read TSV file and return DataFrame with Position, Title, URL columns."""
    df = pd.read_csv(file_path, sep='\t')
    required_cols = {'Position', 'Title', 'URL'}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise ValueError(f"Missing required columns: {missing}")
    return df


def scrape_url(url: str, timeout: int = 30) -> Optional[str]:
    """Scrape main text content from a URL using requests and BeautifulSoup."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for tag in ['script', 'style', 'nav', 'header', 'footer', 'aside']:
            for element in soup.find_all(tag):
                element.decompose()
        
        main_content = None
        for tag in ['article', 'main', 'div[@role="main"]']:
            main_content = soup.find(tag)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.body
        
        text_elements = main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
        text_content = []
        for elem in text_elements:
            text = elem.get_text(strip=True)
            if len(text) > 20:
                text_content.append(text)
        
        full_text = ' '.join(text_content[:100])
        
        if len(full_text) < 100:
            full_text = soup.get_text(separator=' ', strip=True)[:5000]
        
        return full_text[:5000]
        
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
    
    client = Groq(api_key=api_key)
    
    rq_context = "\n".join([f"- {rq}" for rq in research_questions])
    
    system_prompt = f"""
You are a Senior Research Assistant specialized in Multivocal Literature Reviews (MLR).
Your task is to evaluate Grey Literature (GL) articles for thematic saturation checking.

### RESEARCH QUESTIONS:
{rq_context}

### PROJECT THEMES (Current Knowledge Base):
{project_themes if project_themes else "No themes defined yet."}

### INSTRUCTIONS:
Analyze the article content against the current project themes.
Determine if this article:
1. Adds NEW thematic evidence (new patterns, insights, or perspectives)
2. Reaches THEMATIC SATURATION (confirms existing themes without new evidence)

### OUTPUT FORMAT:
Return ONLY valid JSON with this exact structure:
{{
    "is_new": boolean,
    "reasoning": "Detailed explanation of why this is new or redundant",
    "suggested_tags": ["tag1", "tag2", ...] (max 5 tags, relevant to themes/RQs)
}}

### DECISION CRITERIA:
- is_new = true: Article provides new evidence, patterns, or perspectives not in existing themes
- is_new = false: Article confirms existing themes without novel contributions (saturation reached)
- Consider: novel methodologies, new populations, different contexts, contradictory findings
"""
    
    user_content = f"""
TITLE: {article_title}

CONTENT:
{article_content[:3000]}
"""
    
    for attempt in range(max_retries):
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
            
            result = json.loads(response.choices[0].message.content)
            
            logger.info(f"Saturation check for '{article_title[:30]}...': is_new={result.get('is_new')}")
            
            return {
                "is_new": result.get("is_new", False),
                "reasoning": result.get("reasoning", ""),
                "suggested_tags": result.get("suggested_tags", [])
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            if attempt == max_retries - 1:
                return {"is_new": False, "reasoning": "Invalid response format", "suggested_tags": []}
                
        except Exception as e:
            logger.error(f"API error: {e}")
            if attempt == max_retries - 1:
                return {"is_new": False, "reasoning": f"API error: {str(e)}", "suggested_tags": []}
            
            time.sleep(1 * (2 ** attempt))
    
    return {"is_new": False, "reasoning": "Max retries exceeded", "suggested_tags": []}


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
        
        time.sleep(0.5)
    
    return results