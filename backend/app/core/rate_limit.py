"""
Shared rate limiting configuration.

Defines the global SlowAPI limiter instance to avoid circular imports between
routers and the FastAPI app.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Global limiter instance reused by the app and routers
limiter = Limiter(key_func=get_remote_address, default_limits=["1000/hour"])

# Re-export handler and exception for app wiring
rate_limit_handler = _rate_limit_exceeded_handler
rate_limit_exception = RateLimitExceeded
