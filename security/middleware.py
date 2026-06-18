"""
FastAPI middleware for IP blocking and security
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
from security.ip_blocker import ip_blocker

logger = logging.getLogger(__name__)


class IPBlockingMiddleware(BaseHTTPMiddleware):
    """Middleware to block suspicious IPs before reaching endpoints"""
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check if IP is blocked
        if ip_blocker.is_ip_blocked(client_ip):
            logger.warning(f"Blocked request from blocked IP: {client_ip} - {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied: Your IP has been blocked due to suspicious activity"}
            )
        
        # Process the request
        response = await call_next(request)
        
        # Track the request after getting response
        should_block, reason = await ip_blocker.track_request(
            client_ip, 
            request.url.path,
            response.status_code
        )
        
        if should_block:
            logger.warning(f"Blocking IP {client_ip}: {reason}")
            return JSONResponse(
                status_code=403,
                content={"detail": f"Access denied: {reason}"}
            )
        
        return response
