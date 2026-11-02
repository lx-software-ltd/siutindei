"""Centralized database engine management.

This module provides a unified interface for creating and managing
SQLAlchemy engines with settings appropriate for Lambda execution.
"""

from __future__ import annotations

import os
import time
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.db.connection import get_database_url

# Module-level engine cache for connection reuse across Lambda invocations.
# IAM engines are kept for ten minutes, inside the 15-minute token lifetime.
_IAM_ENGINE_TTL_SECONDS = 600
_ENGINE_CACHE: dict[str, tuple[float, Engine]] = {}


def get_engine(
    use_cache: bool = True,
    pool_class: type | None = None,
) -> Engine:
    """Get or create a SQLAlchemy engine.

    Password authentication reuses one engine for the life of the container.
    IAM authentication reuses one engine for ten minutes so the auth token
    stays inside its lifetime. Every IAM caller, including admin and health,
    gets that one-connection pool. Do not open a second session on the same
    engine before the first session commits or rolls back. An explicit
    ``pool_class`` skips the cache so the override is honored.

    Args:
        use_cache: Whether to use the engine cache.
        pool_class: Override the connection pool class.

    Returns:
        A configured SQLAlchemy engine.
    """
    use_iam_auth = _use_iam_auth()
    if pool_class is not None:
        use_cache = False
    cache_key = "iam" if use_iam_auth else "default"
    now = time.monotonic()
    if use_cache:
        cached = _cached_engine(cache_key, now, use_iam_auth)
        if cached is not None:
            return cached

    database_url = get_database_url()
    pool_settings = _get_pool_settings(use_iam_auth, pool_class)

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=_get_connect_args(),
        **pool_settings,
    )

    if use_cache:
        _ENGINE_CACHE[cache_key] = (now, engine)

    return engine


def _cached_engine(
    cache_key: str,
    now: float,
    use_iam_auth: bool,
) -> Engine | None:
    cached = _ENGINE_CACHE.get(cache_key)
    if cached is None:
        return None
    created_at, engine = cached
    if use_iam_auth and now - created_at >= _IAM_ENGINE_TTL_SECONDS:
        engine.dispose()
        del _ENGINE_CACHE[cache_key]
        return None
    return engine


def clear_engine_cache() -> None:
    """Clear the engine cache.

    Useful for testing or when connection settings change.
    """
    for _created_at, engine in _ENGINE_CACHE.values():
        engine.dispose()
    _ENGINE_CACHE.clear()


def _use_iam_auth() -> bool:
    """Return True if IAM authentication is enabled."""
    return str(os.getenv("DATABASE_IAM_AUTH", "")).lower() in {"1", "true", "yes"}


def _get_connect_args() -> dict[str, str]:
    """Return connection arguments for the database driver."""
    sslmode = os.getenv("DATABASE_SSLMODE", "require")
    return {"sslmode": sslmode}


def _get_pool_settings(
    use_iam_auth: bool,
    pool_class: type | None,
) -> dict[str, Any]:
    """Return connection pool settings tuned for Lambda.

    IAM auth uses one connection recycled every ten minutes.
    An explicit pool class, including NullPool, is honored.
    Password auth uses the small Lambda pool from the environment.

    Args:
        use_iam_auth: Whether IAM authentication is being used.
        pool_class: Optional pool class override.

    Returns:
        Dictionary of pool configuration options.
    """
    if pool_class is not None:
        return {"poolclass": pool_class}

    if use_iam_auth:
        return {
            "pool_size": 1,
            "max_overflow": 0,
            "pool_recycle": _IAM_ENGINE_TTL_SECONDS,
        }

    return {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "1")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "0")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
    }
