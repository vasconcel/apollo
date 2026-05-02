"""
PDF Text Extraction Module for AI Document Analysis.
Extracts clean text from PDF files for LLM processing.
"""
import os
import pdfplumber
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def extract_text_from_pdf(
    file_path: str,
    max_pages: int = 50,
    merge_pages: bool = True
) -> dict:
    """
    Extract clean text from a PDF file.
    
    Args:
        file_path: Path to PDF file
        max_pages: Maximum pages to extract (for very long PDFs)
        merge_pages: If True, merge all text into one string
        
    Returns:
        Dictionary with text, page_count, metadata
    """
    if not os.path.exists(file_path):
        logger.error(f"PDF file not found: {file_path}")
        return {
            "text": "",
            "page_count": 0,
            "error": "File not found"
        }
    
    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            
            # Limit pages if needed
            pages_to_process = min(page_count, max_pages)
            extracted_pages = []
            
            for i in range(pages_to_process):
                page = pdf.pages[i]
                text = page.extract_text()
                
                if text and text.strip():
                    extracted_pages.append({
                        "page": i + 1,
                        "text": text.strip()
                    })
            
            if merge_pages:
                # Combine all pages
                full_text = "\n\n".join([p["text"] for p in extracted_pages])
                
                return {
                    "text": full_text,
                    "page_count": page_count,
                    "pages_extracted": len(extracted_pages),
                    "truncated": page_count > max_pages
                }
            else:
                # Return structured pages
                return {
                    "text": extracted_pages,
                    "page_count": page_count,
                    "pages_extracted": len(extracted_pages),
                    "truncated": page_count > max_pages
                }
                
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return {
            "text": "",
            "page_count": 0,
            "error": str(e)
        }


def extract_page_as_image(
    file_path: str,
    page_num: int = 1,
    dpi: int = 150
) -> Optional[bytes]:
    """
    Extract a page as image for visual analysis.
    
    Args:
        file_path: Path to PDF
        page_num: Page number (1-indexed)
        dpi: Resolution for rendering
        
    Returns:
        Image bytes or None
    """
    try:
        from pdf2image import convert_from_path
        
        images = convert_from_path(
            file_path,
            first_page=page_num,
            last_page=page_num,
            dpi=dpi
        )
        
        if images:
            # Convert PIL image to bytes
            import io
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue()
            
    except Exception as e:
        logger.error(f"PDF image extraction error: {e}")
        return None


def get_pdf_metadata(file_path: str) -> dict:
    """
    Get PDF metadata (title, author, etc.)
    
    Args:
        file_path: Path to PDF
        
    Returns:
        Dictionary with metadata
    """
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    
    try:
        with pdfplumber.open(file_path) as pdf:
            meta = pdf.metadata or {}
            
            return {
                "title": meta.get("/Title", ""),
                "author": meta.get("/Author", ""),
                "subject": meta.get("/Subject", ""),
                "creator": meta.get("/Creator", ""),
                "producer": meta.get("/Producer", ""),
                "page_count": len(pdf.pages)
            }
    except Exception as e:
        return {"error": str(e)}


def quick_preview(file_path: str, max_chars: int = 1000) -> str:
    """
    Get a quick preview of PDF text (first N characters).
    
    Args:
        file_path: Path to PDF
        max_chars: Maximum characters to return
        
    Returns:
        Preview string
    """
    result = extract_text_from_pdf(file_path, max_pages=5)
    
    if result.get("error"):
        return f"Error: {result['error']}"
    
    text = result["text"]
    return text[:max_chars] + "..." if len(text) > max_chars else text