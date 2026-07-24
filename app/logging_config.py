"""
GenQuantis Platform — Production Logging Configuration
======================================================
Creates structured, rotating log files for DevOps analysis.

Log Files Generated (in ./logs/):
  - platform_access.log   → Every HTTP request: user, endpoint, method, latency, status
  - platform_errors.log   → Only 4xx/5xx responses and unhandled exceptions
  - platform_performance.log → Slow requests (>2s), docking jobs, screening jobs
  - platform_system.log   → Application lifecycle, startup, DB connections
"""

import logging
import os
import json
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

# ── Directory Setup ──────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── Custom JSON Formatter ────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    """
    Outputs each log record as a single JSON line.
    DevOps can ingest these directly into ELK, Loki, Datadog, etc.
    """
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra structured fields
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        return json.dumps(log_entry, default=str)


# ── Readable Console Formatter ───────────────────────────────────────
class ConsoleFormatter(logging.Formatter):
    """Colored, human-readable format for terminal output."""
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{color}[{timestamp}] [{record.levelname:^8}] {record.name}: {record.getMessage()}{self.RESET}"


def _create_file_handler(filename: str, level=logging.DEBUG, max_bytes=10*1024*1024, backup_count=5):
    """Creates a rotating file handler with JSON formatting."""
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=max_bytes,       # 10 MB per file
        backupCount=backup_count, # Keep 5 rotated files
        encoding="utf-8"
    )
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())
    return handler


def setup_logging():
    """
    Configures the platform's logging infrastructure.
    Call this once at application startup.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers on reload
    access_logger = logging.getLogger("genquantis.access")
    if any(isinstance(h, RotatingFileHandler) for h in access_logger.handlers):
        return

    # ── Console Handler (human-readable) ────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ConsoleFormatter())

    # ── File Handlers (JSON, machine-parseable) ─────────────────────
    access_handler = _create_file_handler("platform_access.log")
    error_handler = _create_file_handler("platform_errors.log", level=logging.WARNING)
    perf_handler = _create_file_handler("platform_performance.log")
    system_handler = _create_file_handler("platform_system.log")

    # ── Named Loggers ────────────────────────────────────────────────
    # Access Logger — every request
    access_logger.addHandler(access_handler)
    access_logger.addHandler(console_handler)
    access_logger.setLevel(logging.DEBUG)
    access_logger.propagate = False

    # Error Logger — 4xx/5xx and exceptions
    error_logger = logging.getLogger("genquantis.errors")
    error_logger.addHandler(error_handler)
    error_logger.addHandler(console_handler)
    error_logger.setLevel(logging.WARNING)
    error_logger.propagate = False

    # Performance Logger — slow queries, job durations
    perf_logger = logging.getLogger("genquantis.performance")
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.DEBUG)
    perf_logger.propagate = False

    # System Logger — startup, shutdown, DB events
    system_logger = logging.getLogger("genquantis.system")
    system_logger.addHandler(system_handler)
    system_logger.addHandler(console_handler)
    system_logger.setLevel(logging.DEBUG)
    system_logger.propagate = False

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    system_logger.info("📋 GenQuantis Logging System Initialized", extra={
        "extra_data": {"log_directory": LOG_DIR, "event": "LOGGING_INIT"}
    })
