# src/core/snowballing.py
import requests

def get_paper_references(doi: str) -> list:
    """Ultra-defensive parser for Semantic Scholar API."""
    if not doi or not str(doi).strip():
        return []
    
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}/references"
    params = {"fields": "title,authors,year,abstract,externalIds"}
    
    references = []
    try:
        response = requests.get(url, params=params, timeout=15)
        if not response.ok:
            return []
        
        data = response.json()
        if not data: return []
        
        # Fixing NoneType Exception for cases where "data" key exists but value is null
        items = data.get("data") or []
        
        for item in items:
            if not item: continue
            cited_paper = item.get("citedPaper")
            if not cited_paper: continue
            
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