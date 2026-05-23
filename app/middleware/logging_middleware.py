"""
GenQuantis Platform — Request Logging Middleware
================================================
Captures every HTTP request with:
  - User identity (from JWT token)
  - Request method, path, query params
  - Response status code
  - Request processing time (latency in ms)
  - Client IP address
  - User-Agent string
"""

import time
import logging
import hmac
import hashlib
import json
import base64
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Threshold in seconds — requests slower than this are flagged
SLOW_REQUEST_THRESHOLD = 2.0

# Secret key — must match auth config (dependencies.py)
SECRET_KEY = "super-secret-key-change-this"

access_logger = logging.getLogger("genquantis.access")
error_logger = logging.getLogger("genquantis.errors")
perf_logger = logging.getLogger("genquantis.performance")


def _extract_user_email(request: Request) -> str:
    """Silently extract user email from the Authorization header token, if present."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            # Match the platform's custom HMAC token format from dependencies.py
            padding = 4 - (len(token) % 4)
            if padding < 4:
                token += "=" * padding
            decoded = base64.urlsafe_b64decode(token).decode()
            payload_str, signature = decoded.rsplit(".", 1)
            expected_sig = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
            if signature != expected_sig:
                return "invalid_token"
            payload = json.loads(payload_str)
            return payload.get("email", "authenticated_user")
        except Exception:
            return "invalid_token"
    return "anonymous"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        # Extract metadata before processing
        user_email = _extract_user_email(request)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""

        # Skip logging for static assets (CSS, JS, images) to reduce noise
        if path.startswith("/static/"):
            response = await call_next(request)
            return response
        
        # Process the request
        status_code = 500  # Default in case of unhandled exception
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            error_logger.error(
                f"UNHANDLED EXCEPTION on {method} {path}",
                extra={"extra_data": {
                    "event": "UNHANDLED_EXCEPTION",
                    "user": user_email,
                    "method": method,
                    "path": path,
                    "query": query,
                    "client_ip": client_ip,
                    "latency_ms": latency_ms,
                    "error": str(exc),
                    "error_type": type(exc).__name__
                }}
            )
            raise

        # Calculate latency
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Build structured log record
        log_data = {
            "event": "HTTP_REQUEST",
            "user": user_email,
            "method": method,
            "path": path,
            "query": query,
            "status": status_code,
            "latency_ms": latency_ms,
            "client_ip": client_ip,
            "user_agent": user_agent[:120],  # Truncate long UAs
        }

        # Access log — every request
        access_logger.info(
            f"{method} {path} → {status_code} ({latency_ms}ms) [{user_email}]",
            extra={"extra_data": log_data}
        )

        # Error log — 4xx and 5xx
        if status_code >= 400:
            error_logger.warning(
                f"HTTP {status_code}: {method} {path} [{user_email}]",
                extra={"extra_data": log_data}
            )

        # Performance log — slow requests
        if latency_ms > SLOW_REQUEST_THRESHOLD * 1000:
            perf_logger.warning(
                f"⚠️ SLOW REQUEST: {method} {path} took {latency_ms}ms [{user_email}]",
                extra={"extra_data": {
                    **log_data,
                    "event": "SLOW_REQUEST",
                    "threshold_ms": SLOW_REQUEST_THRESHOLD * 1000
                }}
            )

        # Performance log — computational endpoints always logged
        if any(segment in path for segment in ["/docking/", "/screening/", "/optimization/", "/admet/", "/preformulation/"]):
            perf_logger.info(
                f"🧪 COMPUTE: {method} {path} → {status_code} ({latency_ms}ms) [{user_email}]",
                extra={"extra_data": {
                    **log_data,
                    "event": "COMPUTE_REQUEST"
                }}
            )

        return response
