"""Build and cache local Lambda bundles for CDK asset staging."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

PIP_VERSION = "25.3"
TARGET_PLATFORM = "manylinux_2_17_aarch64"
TARGET_IMPLEMENTATION = "cp"
TARGET_PYTHON_VERSION = "3.12"
CACHE_FORMAT_VERSION = "1"
DEFAULT_CACHE_RETENTION = 3
CACHE_RETENTION_ENV_VAR = "LAMBDA_DEPS_CACHE_RETENTION"
PIP_INSTALL_ATTEMPTS = 3
# A truncated PyPI simple-index body is a 200 with invalid JSON. Pip does
# not retry that, and one occurrence fails the whole backend deploy.
RETRYABLE_PIP_MARKERS = (
    "JSONDecodeError",
    "Unterminated string",
    "IncompleteRead",
    "ReadTimeoutError",
    "ConnectTimeoutError",
    "Read timed out",
    "ConnectionResetError",
    "RemoteDisconnected",
    "NewConnectionError",
    "ProtocolError",
    "SSLEOFError",
    "Temporary failure in name resolution",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "504 Gateway Timeout",
)


def _ensure_python_version() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required to build Lambda bundles.")


class PipCommandError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, output: str) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output
        super().__init__(
            f"Command {command!r} returned non-zero exit status {returncode}."
        )


def _pip_output_is_retryable(output: str) -> bool:
    return any(marker in output for marker in RETRYABLE_PIP_MARKERS)


def _retry_sleep_seconds(failed_attempt: int) -> int:
    return 2 * failed_attempt


def _run_pip(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    output_parts: list[str] = []
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        output_parts.append(line)
    returncode = process.wait()
    if returncode != 0:
        raise PipCommandError(command, returncode, "".join(output_parts))


def _run_pip_retrying(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    *,
    on_retry: Callable[[], None] | None = None,
) -> None:
    for attempt in range(1, PIP_INSTALL_ATTEMPTS + 1):
        try:
            _run_pip(command, cwd, env)
            return
        except PipCommandError as exc:
            if attempt >= PIP_INSTALL_ATTEMPTS or not _pip_output_is_retryable(
                exc.output
            ):
                raise
            logger.warning(
                "Retryable pip failure on attempt %s of %s; retrying.",
                attempt,
                PIP_INSTALL_ATTEMPTS,
            )
            time.sleep(_retry_sleep_seconds(attempt))
            if on_retry is not None:
                on_retry()


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing source path: {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _cleanup_bundle(output_dir: Path) -> None:
    for cache_dir in output_dir.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
    for cache_file in output_dir.rglob("*.pyc"):
        cache_file.unlink()
    for cache_file in output_dir.rglob("*.pyo"):
        cache_file.unlink()


def _parse_cache_retention_value(value: str) -> int:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Cache retention count cannot be empty.")

    try:
        retention_count = int(stripped)
    except ValueError as exc:
        raise ValueError("Cache retention count must be a positive integer.") from exc

    if retention_count < 1:
        raise ValueError("Cache retention count must be at least 1.")
    return retention_count


def _cache_retention_arg(value: str) -> int:
    try:
        return _parse_cache_retention_value(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _default_cache_retention() -> int:
    env_value = os.getenv(CACHE_RETENTION_ENV_VAR)
    if env_value is None:
        return DEFAULT_CACHE_RETENTION
    try:
        return _parse_cache_retention_value(env_value)
    except ValueError as exc:
        raise SystemExit(f"Invalid {CACHE_RETENTION_ENV_VAR}: {exc}") from exc


def _dependency_cache_key(requirements: Path) -> str:
    hasher = hashlib.sha256()
    hasher.update(requirements.read_bytes())
    hasher.update(CACHE_FORMAT_VERSION.encode("utf-8"))
    hasher.update(PIP_VERSION.encode("utf-8"))
    hasher.update(TARGET_PLATFORM.encode("utf-8"))
    hasher.update(TARGET_IMPLEMENTATION.encode("utf-8"))
    hasher.update(TARGET_PYTHON_VERSION.encode("utf-8"))
    return hasher.hexdigest()


def _pip_env(build_root: Path) -> dict[str, str]:
    home_dir = build_root / "home"
    pip_cache_dir = build_root / "pip-cache"
    python_user_base = build_root / "python-user-base"
    home_dir.mkdir(parents=True, exist_ok=True)
    pip_cache_dir.mkdir(parents=True, exist_ok=True)
    python_user_base.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "PIP_CACHE_DIR": str(pip_cache_dir),
            "PYTHONUSERBASE": str(python_user_base),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
    )
    return env


def _build_dependency_cache(
    source_root: Path,
    requirements: Path,
    cache_dir: Path,
    env: dict[str, str],
) -> None:
    cache_root = cache_dir.parent
    cache_root.mkdir(parents=True, exist_ok=True)
    temp_cache_dir = cache_root / f".{cache_dir.name}.tmp"
    _remove_tree(temp_cache_dir)
    temp_cache_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Installing Lambda Python dependencies into cache...")

    def reset_temp_cache() -> None:
        _remove_tree(temp_cache_dir)
        temp_cache_dir.mkdir(parents=True, exist_ok=True)

    _run_pip_retrying(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            f"pip=={PIP_VERSION}",
            "--no-warn-script-location",
        ],
        cwd=source_root,
        env=env,
    )
    _run_pip_retrying(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements),
            "-t",
            str(temp_cache_dir),
            "--no-compile",
            "--platform",
            TARGET_PLATFORM,
            "--only-binary=:all:",
            "--implementation",
            TARGET_IMPLEMENTATION,
            "--python-version",
            TARGET_PYTHON_VERSION,
        ],
        cwd=source_root,
        env=env,
        on_retry=reset_temp_cache,
    )
    _cleanup_bundle(temp_cache_dir)
    _remove_tree(cache_dir)
    temp_cache_dir.rename(cache_dir)


def _write_cache_marker(cache_dir: Path, cache_key: str) -> None:
    marker_file = cache_dir / ".ready"
    marker_file.write_text(f"{cache_key}\n", encoding="utf-8")
    os.utime(marker_file, times=None)


def _touch_cache_marker(cache_dir: Path) -> None:
    marker_file = cache_dir / ".ready"
    os.utime(marker_file, times=None)


def _ready_caches(cache_root: Path) -> list[Path]:
    ready_caches: list[Path] = []
    for candidate in cache_root.iterdir():
        if not candidate.is_dir():
            continue
        if candidate.name.startswith("."):
            continue
        if not (candidate / ".ready").is_file():
            continue
        ready_caches.append(candidate)
    return ready_caches


def _cache_mtime(cache_dir: Path) -> float:
    return (cache_dir / ".ready").stat().st_mtime


def _prune_old_dependency_caches(
    cache_root: Path,
    active_cache: Path,
    retention_count: int,
) -> None:
    ready_caches = sorted(
        _ready_caches(cache_root),
        key=_cache_mtime,
        reverse=True,
    )
    for candidate in ready_caches[retention_count:]:
        if candidate == active_cache:
            continue
        logger.info(
            "Pruning stale Lambda dependency cache: %s",
            candidate.name[:12],
        )
        shutil.rmtree(candidate)


def _ensure_dependency_cache(
    source_root: Path,
    requirements: Path,
    cache_retention: int,
) -> Path:
    if not requirements.is_file():
        raise FileNotFoundError(f"Missing requirements file: {requirements}")

    build_root = source_root / ".lambda-build"
    cache_root = build_root / "deps-cache"
    key = _dependency_cache_key(requirements)
    cache_dir = cache_root / key
    marker_file = cache_dir / ".ready"
    env = _pip_env(build_root)
    cache_root.mkdir(parents=True, exist_ok=True)

    if marker_file.is_file():
        logger.info("Reusing cached Lambda dependencies: %s", key[:12])
        _touch_cache_marker(cache_dir)
        _prune_old_dependency_caches(cache_root, cache_dir, cache_retention)
        return cache_dir

    logger.info("No dependency cache found for requirements hash %s", key[:12])
    _build_dependency_cache(source_root, requirements, cache_dir, env)
    _write_cache_marker(cache_dir, key)
    logger.info("Lambda dependency cache ready: %s", key[:12])
    _prune_old_dependency_caches(cache_root, cache_dir, cache_retention)
    return cache_dir


def build_bundle(
    source_root: Path,
    output_dir: Path,
    cache_retention: int,
) -> None:
    requirements = source_root / "requirements.txt"
    dependency_cache = _ensure_dependency_cache(
        source_root,
        requirements,
        cache_retention,
    )

    _remove_tree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _copy_tree(dependency_cache, output_dir)
    _copy_tree(source_root / "lambda", output_dir / "lambda")
    _copy_tree(source_root / "src", output_dir / "src")
    _cleanup_bundle(output_dir)


def _parse_args() -> argparse.Namespace:
    default_retention = _default_cache_retention()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to backend source root.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory for the bundled assets.",
    )
    parser.add_argument(
        "--deps-only",
        action="store_true",
        help="Warm dependency cache without building bundle output.",
    )
    parser.add_argument(
        "--cache-retention",
        type=_cache_retention_arg,
        default=default_retention,
        help=(
            "Keep this many most-recent dependency cache keys "
            f"(default: {default_retention}, env: {CACHE_RETENTION_ENV_VAR})."
        ),
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _ensure_python_version()
    args = _parse_args()
    source_root = Path(args.source_root).resolve()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else source_root / ".lambda-build" / "base"
    )
    requirements = source_root / "requirements.txt"

    if args.deps_only:
        _ensure_dependency_cache(source_root, requirements, args.cache_retention)
        logger.info("Lambda dependency cache is ready.")
        return

    logger.info("Building Lambda bundle in %s", output_dir)
    build_bundle(source_root, output_dir, args.cache_retention)
    logger.info("Lambda bundle ready.")


if __name__ == "__main__":
    main()
