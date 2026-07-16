"""
Rate limiting utilities for API endpoints.

Provides in-memory rate limiting for AI endpoints to prevent abuse.
"""
import time
import logging
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request, Depends

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using sliding window.
    
    For production with multiple workers, use Redis-based rate limiting.
    """
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
    
    def check(self, key: str) -> bool:
        """
        Check if a request is allowed for the given key.
        
        Args:
            key: Unique identifier (e.g., user_id or IP)
            
        Returns:
            True if request allowed, False if rate limited
        """
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
        
        # Check limit
        if len(self._requests[key]) >= self.max_requests:
            return False
        
        # Record request
        self._requests[key].append(now)
        return True
    
    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        self._requests.pop(key, None)
    
    def get_remaining(self, key: str) -> int:
        """Get remaining requests for a key."""
        now = time.time()
        cutoff = now - self.window_seconds
        current = len([t for t in self._requests[key] if t > cutoff])
        return max(0, self.max_requests - current)


# Global rate limiter instances
ai_rate_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=60)


async def check_ai_rate_limit(request: Request) -> None:
    """
    FastAPI dependency that checks AI endpoint rate limit.
    
    Uses client IP as key. Raises 429 if rate limited.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    if not ai_rate_limiter.check(client_ip):
        remaining_seconds = ai_rate_limiter.window_seconds
        logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="יותר מדי בקשות. נסה שוב בעוד דקה.",
            headers={"Retry-After": str(remaining_seconds)},
        )
