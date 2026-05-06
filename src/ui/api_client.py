"""
APOLLO API Client - Simplified for EC/IC/QC operations
"""
import os
import requests
from typing import Optional


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")


class APIClient:
    """Client for APOLLO API - Decision Support Layer."""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or API_BASE_URL
    
    def _get_headers(self, user_id: str) -> dict:
        return {"X-User-ID": user_id}
    
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


client = APIClient()