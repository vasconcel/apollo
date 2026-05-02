# src/core/snowballing.py
import requests
import time


def get_paper_references(doi: str, timeout: int = 15) -> list:
    """Ultra-defensive parser for Semantic Scholar API."""
    if not doi or not str(doi).strip():
        return []
    
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}/references"
    params = {"fields": "title,authors,year,abstract,externalIds,citationCount,influentialCitationCount"}
    
    references = []
    try:
        response = requests.get(url, params=params, timeout=timeout)
        if not response.ok:
            return []
        
        data = response.json()
        if not data:
            return []
        
        items = data.get("data") or []
        
        for item in items:
            if not item:
                continue
            cited_paper = item.get("citedPaper")
            if not cited_paper:
                continue
            
            authors_list = cited_paper.get("authors") or []
            authors = ", ".join([str(a.get("name", "")) for a in authors_list if a and a.get("name")])
            
            ext_ids = cited_paper.get("externalIds") or {}
            ref_doi = ext_ids.get("DOI", "")
            
            references.append({
                "title": cited_paper.get("title") or "Unknown Title",
                "authors": authors,
                "year": cited_paper.get("year"),
                "abstract": cited_paper.get("abstract") or "",
                "doi": ref_doi,
                "source": "snowballing",
                "literature_type": "PENDING"
            })
            
    except Exception as e:
        print(f"Snowballing error: {e}")
    
    return references


def get_paper_metadata(doi: str, timeout: int = 10) -> dict:
    """
    Fetch paper metadata from Semantic Scholar including citation counts.
    
    Args:
        doi: DOI of the paper
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with title, authors, year, citation_count, influential_citation_count, abstract
    """
    if not doi or not str(doi).strip():
        return {}
    
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    params = {
        "fields": "title,authors,year,abstract,citationCount,influentialCitationCount"
    }
    
    try:
        response = requests.get(url, params=params, timeout=timeout)
        if not response.ok:
            return {}
        
        data = response.json()
        if not data:
            return {}
        
        paper = data if isinstance(data, dict) else {}
        
        authors_list = paper.get("authors") or []
        authors = ", ".join([a.get("name", "") for a in authors_list if a and a.get("name")])
        
        return {
            "title": paper.get("title", ""),
            "authors": authors,
            "year": paper.get("year"),
            "abstract": paper.get("abstract", ""),
            "citation_count": paper.get("citationCount", 0),
            "influential_citation_count": paper.get("influentialCitationCount", 0)
        }
        
    except Exception as e:
        print(f"Metadata fetch error: {e}")
        return {}


def enrich_article_with_citations(doi: str, db_article_id: int = None) -> dict:
    """
    Fetch and return enriched article data with citation metrics.
    
    Args:
        doi: DOI of the article
        db_article_id: Optional database ID to update
        
    Returns:
        Enriched article metadata
    """
    metadata = get_paper_metadata(doi)
    
    if not metadata:
        return {
            "citation_count": 0,
            "influential_citation_count": 0
        }
    
    return {
        "citation_count": metadata.get("citation_count", 0),
        "influential_citation_count": metadata.get("influential_citation_count", 0),
        "year": metadata.get("year"),
        "title": metadata.get("title"),
        "authors": metadata.get("authors")
    }