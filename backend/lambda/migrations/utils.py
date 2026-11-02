"""Utility helpers for migrations Lambda."""

from __future__ import annotations

import time
from typing import Any

import psycopg
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.utils.logging import get_logger

logger = get_logger(__name__)


def _run_with_retry(func: Any, *args: Any) -> None:
    """Retry migration operations to wait for DB readiness."""
    func_name = getattr(func, "__name__", str(func))
    max_attempts = 10
    delay = 5.0
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            func(*args)
            logger.info(f"Operation {func_name} completed successfully")
            return
        except Exception as exc:  # pragma: no cover - best effort retry
            error_type = type(exc).__name__
            error_msg = str(exc)
            safe_msg = _sanitize_error_message(error_msg)
            logger.warning(
                f"Attempt {attempt + 1}/{max_attempts} for {func_name} failed",
                extra={
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "error_type": error_type,
                    "error_message": safe_msg,
                    "function": func_name,
                },
            )
            last_error = exc
            if attempt < max_attempts - 1:
                logger.info(f"Retrying {func_name} in {delay:.1f} seconds...")
                time.sleep(delay)
                delay = min(delay * 1.5, 30.0)
    if last_error:
        raise last_error


def _sanitize_error_message(msg: str) -> str:
    """Remove potential secrets from error messages."""
    import re

    msg = re.sub(r"://[^:]+:[^@]+@", "://***:***@", msg)
    msg = re.sub(r"password=[A-Za-z0-9+/=]{50,}", "password=***REDACTED***", msg)
    return msg


def _escape_config(value: str) -> str:
    """Escape percent signs for configparser interpolation."""
    return value.replace("%", "%%")


def _psycopg_connect(database_url: str) -> psycopg.Connection:
    """Connect using keyword args to avoid DSN parsing issues."""
    try:
        url = make_url(database_url)
    except ArgumentError:
        url = make_url(f"postgresql://{database_url}")

    connect_kwargs: dict[str, Any] = {
        "user": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port,
        "dbname": url.database,
    }
    sslmode = url.query.get("sslmode")
    if sslmode:
        connect_kwargs["sslmode"] = sslmode

    return psycopg.connect(
        **{key: value for key, value in connect_kwargs.items() if value is not None}
    )


def _truthy(value: Any) -> bool:
    """Return True for common truthy string values."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "y"}
