"""Staging upload uses s3-cloudfront-deploy and leaves the path invalidation."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-public-www-staging.yml"
SCRIPT = ROOT / "scripts" / "deploy" / "deploy-public-www.sh"

FAKE_AWS = """\
#!/usr/bin/env python3
import os
import sys

args = sys.argv[1:]
with open(os.environ["AWS_LOG"], "a", encoding="utf-8") as handle:
    handle.write(" ".join(args) + "\\n")
if args[:1] == ["s3"]:
    sys.exit("staging external upload must not call s3")
if args[:2] == ["cloudformation", "describe-stacks"]:
    print("resolved-value")
elif args[:2] == ["cloudfront", "create-invalidation"]:
    print("invalidation")
else:
    sys.exit("unexpected aws " + " ".join(args))
"""


def test_staging_workflow_uploads_with_the_shared_action() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "s3-cloudfront-deploy@" in text
    assert "bucket-output: PublicWwwStagingBucketName" in text
    assert 'distribution-output: ""' in text
    assert "profile: next-site" in text
    assert "stale-while-revalidate=60" in text
    assert "marker-cache: no-store, max-age=0" in text
    assert "marker-content-type: text/plain; charset=utf-8" in text
    assert 'staging-robots: "true"' in text
    assert 'dry-run: "false"' in text
    assert "PUBLIC_WWW_UPLOAD: external" in text
    assert "sync-exclude:" not in text


def _run(
    tmp_path: Path, upload: str, environment: str
) -> subprocess.CompletedProcess[str]:
    aws = tmp_path / "aws"
    aws.write_text(FAKE_AWS, encoding="utf-8")
    aws.chmod(aws.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "aws.log"
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    env["AWS_LOG"] = str(log)
    env["PUBLIC_WWW_ENVIRONMENT"] = environment
    env["PUBLIC_WWW_UPLOAD"] = upload
    env["PUBLIC_WWW_STACK_NAME"] = "lxsoftware-siutindei-public-www"
    return subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_external_staging_upload_skips_s3(tmp_path: Path) -> None:
    completed = _run(tmp_path, "external", "staging")
    log = (tmp_path / "aws.log").read_text(encoding="utf-8")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "s3 " not in log
    assert "cloudfront create-invalidation" in log
    assert "/robots.txt" in log
    assert "S3 upload already completed" in completed.stdout


def test_external_upload_refuses_production(tmp_path: Path) -> None:
    completed = _run(tmp_path, "external", "production")
    assert completed.returncode != 0
    assert "only supported for staging" in completed.stdout + completed.stderr
