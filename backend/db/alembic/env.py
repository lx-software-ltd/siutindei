from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, pool

config = context.config

# Alembic's version_num column is varchar(32) by default
MAX_REVISION_LENGTH = 32


def validate_revision_lengths() -> None:
    """Ensure all revision IDs fit in alembic_version.version_num (varchar(32))."""
    script_dir = ScriptDirectory.from_config(config)
    violations = [
        f"  {script.revision} ({len(script.revision)} chars)"
        for script in script_dir.walk_revisions()
        if len(script.revision) > MAX_REVISION_LENGTH
    ]
    if violations:
        raise RuntimeError(
            f"Revision IDs must be ≤{MAX_REVISION_LENGTH} characters:\n"
            + "\n".join(violations)
        )


validate_revision_lengths()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

base_dir = Path(__file__).resolve().parents[2]
sys.path.append(str(base_dir / "src"))

from app.db import models  # noqa: F401,E402
from app.db.base import Base  # noqa: E402

target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the database URL from environment variables."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for Alembic migrations.")
    return url


def _escape_for_config(value: str) -> str:
    """Escape percent signs for configparser interpolation."""
    return value.replace("%", "%%")


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    config.set_main_option("sqlalchemy.url", _escape_for_config(get_database_url()))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
