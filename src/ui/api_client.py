import os
import requests
from typing import Optional


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")


class APIClient:
    """Client for AIMS API."""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or API_BASE_URL
    
    def _get_headers(self, user_id: str) -> dict:
        return {"X-User-ID": user_id}
    
    def get_pending_articles(self, review_id: int, user_id: str) -> list:
        """Get pending articles for screening."""
        response = requests.get(
            f"{self.base_url}/screening/pending",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("articles", [])
    
    def submit_decision(self, review_id: int, user_id: str, article_id: int,
                        decision: str, exclusion_reason: str = None,
                        criteria: dict = None) -> dict:
        """Submit screening decision."""
        response = requests.post(
            f"{self.base_url}/screening/decision",
            json={
                "review_id": review_id,
                "reviewer_id": user_id,
                "article_id": article_id,
                "decision": decision,
                "exclusion_reason": exclusion_reason,
                "criteria": criteria
            },
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_progress(self, review_id: int, user_id: str) -> dict:
        """Get user's screening progress."""
        response = requests.get(
            f"{self.base_url}/screening/progress",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_dashboard_stats(self, review_id: int, user_id: str) -> dict:
        """Get dashboard statistics."""
        response = requests.get(
            f"{self.base_url}/stats/dashboard",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_prisma_stats(self, review_id: int, user_id: str) -> dict:
        """Get PRISMA statistics."""
        response = requests.get(
            f"{self.base_url}/stats/prisma",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def get_article_count(self, review_id: int, user_id: str) -> int:
        """Get article count."""
        response = requests.get(
            f"{self.base_url}/articles/count",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("count", 0)
    
    def add_article(self, review_id: int, user_id: str, article_data: dict) -> int:
        """Add new article."""
        article_data["review_id"] = review_id
        response = requests.post(
            f"{self.base_url}/articles",
            json=article_data,
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("article_id")
    
    def get_included_articles(self, review_id: int, user_id: str) -> list:
        """Get articles ready for extraction."""
        response = requests.get(
            f"{self.base_url}/articles/included",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("articles", [])
    
    def get_fragments(self, review_id: int, user_id: str, rq_code: str) -> list:
        """Get fragments for research question."""
        response = requests.get(
            f"{self.base_url}/extraction/fragments/{rq_code}",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("fragments", [])
    
    def get_codes(self, review_id: int, user_id: str, rq_code: str) -> list:
        """Get codes for research question."""
        response = requests.get(
            f"{self.base_url}/extraction/codes/{rq_code}",
            params={"review_id": review_id},
            headers=self._get_headers(user_id),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("codes", [])


client = APIClient()