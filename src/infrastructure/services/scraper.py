import logging
from io import BytesIO
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

logger = logging.getLogger(__name__)

UNPAYWALL_EMAIL = "apollo-slr@domain.com"


async def fetch_url_content(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines[:200])
    except Exception:
        logger.exception("Failed to fetch URL content: %s", url)
        return None


async def fetch_pdf_metadata_by_doi(doi: str) -> Optional[dict]:
    url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("Unpaywall lookup failed for DOI: %s", doi)
        return None

    oa_location = None
    for loc in data.get("oa_locations", []):
        if loc.get("url_for_pdf"):
            oa_location = loc
            break
    if not oa_location:
        oa_location = data.get("best_oa_location")
    if not oa_location:
        return None

    pdf_url = oa_location.get("url_for_pdf") or oa_location.get("url") or data.get("doi_url")
    if not pdf_url:
        return None

    full_text = None
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            pdf_resp = await client.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
            pdf_resp.raise_for_status()
            reader = PdfReader(BytesIO(pdf_resp.content))
            pages = []
            for i, page in enumerate(reader.pages):
                if i >= 5:
                    break
                text = page.extract_text() or ""
                pages.append(text)
            combined = "\n".join(pages)[:15000]
            full_text = combined.strip()
    except Exception:
        logger.exception("PDF extraction failed for: %s", pdf_url)

    return {"full_text": full_text or "", "pdf_url": pdf_url}
