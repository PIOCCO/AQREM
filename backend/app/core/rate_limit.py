"""Rate limiting for expensive/authenticated API routes."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])

# LLM / batch answering — per IP (use Redis backend in multi-instance production).
LLM_GENERATE_LIMIT = "30/minute"
RETRIEVAL_PREVIEW_LIMIT = "60/minute"
AUTH_LOGIN_LIMIT = "20/minute"
