"""Synchronization helpers for migrations Lambda."""

from __future__ import annotations

import os

from psycopg import sql

from app.utils.logging import get_logger

from .secrets import _load_db_user_secret, _validate_db_username
from .utils import _psycopg_connect

logger = get_logger(__name__)

_ALLOWED_PROXY_USERS = {"siutindei_app", "siutindei_admin"}


def _sync_proxy_user_passwords(database_url: str) -> None:
    """Ensure proxy user passwords match Secrets Manager values."""
    secret_arns = [
        os.getenv("DATABASE_APP_USER_SECRET_ARN"),
        os.getenv("DATABASE_ADMIN_USER_SECRET_ARN"),
    ]
    user_secrets = [
        _load_db_user_secret(secret_arn) for secret_arn in secret_arns if secret_arn
    ]

    if not user_secrets:
        return

    with _psycopg_connect(database_url) as connection:
        with connection.cursor() as cursor:
            for username, password in user_secrets:
                _validate_db_username(username, _ALLOWED_PROXY_USERS)
                cursor.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s",
                    (username,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError(f"Database role {username} does not exist")
                alter_query = sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(username),
                    sql.Literal(password),
                )
                cursor.execute(alter_query)
                logger.info(
                    "Updated database password for proxy user",
                    extra={"db_user": username},
                )
        connection.commit()


def _sync_active_countries(database_url: str) -> None:
    """Sync geographic_areas active flags based on ACTIVE_COUNTRY_CODES env var."""
    raw = os.getenv("ACTIVE_COUNTRY_CODES", "").strip()
    if not raw:
        logger.info("ACTIVE_COUNTRY_CODES not set, skipping country sync")
        return

    codes = [code.strip().upper() for code in raw.split(",") if code.strip()]
    if not codes:
        logger.info("ACTIVE_COUNTRY_CODES is empty, skipping country sync")
        return

    logger.info(f"Syncing active countries to: {codes}")

    with _psycopg_connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables "
                "  WHERE table_name = 'geographic_areas'"
                ")"
            )
            exists = cursor.fetchone()
            if not exists or not exists[0]:
                logger.info("geographic_areas table does not exist yet, skipping")
                return

            cursor.execute(
                "UPDATE geographic_areas SET active = false WHERE level = 'country'"
            )

            cursor.execute(
                "UPDATE geographic_areas SET active = true "
                "WHERE level = 'country' AND code = ANY(%s)",
                (codes,),
            )

            cursor.execute(
                "SELECT code, name, active FROM geographic_areas "
                "WHERE level = 'country' ORDER BY display_order"
            )
            rows = cursor.fetchall()
            for code, name, active in rows:
                status = "ACTIVE" if active else "inactive"
                logger.info(f"  Country {code} ({name}): {status}")

        connection.commit()

    logger.info("Country activation sync complete")
