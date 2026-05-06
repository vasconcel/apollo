from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    def _clean_old_requests(self, user_id: str):
        """Remove requests older than 1 minute."""
        cutoff = datetime.utcnow() - timedelta(minutes=1)
        self.requests[user_id] = [
            ts for ts in self.requests[user_id]
            if ts > cutoff
        ]
    
    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit."""
        self._clean_old_requests(user_id)
        
        if len(self.requests[user_id]) >= self.requests_per_minute:
            return False
        
        self.requests[user_id].append(datetime.utcnow())
        return True
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        auth_header = request.headers.get("authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from app.auth.auth import decode_token
                token = auth_header.replace("Bearer ", "")
                payload = decode_token(token)
                user_id = payload.get("user_id", "anonymous") if payload else "anonymous"
            except:
                user_id = "anonymous"
        else:
            user_id = "anonymous"
        
        if not self._check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for user: {user_id}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
        
        response = await call_next(request)
        return response