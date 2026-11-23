"""The staging bucket name cannot cross the promote jobs as an output."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "promote-public-www.yml"
)


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job(name: str) -> str:
    text = _text()
    start = re.search(rf"^  {re.escape(name)}:\s*$", text, re.MULTILINE)
    if start is None:
        raise AssertionError(name)
    rest = text[start.end() :]
    nxt = re.search(r"^  [A-Za-z0-9_-]+:\s*$", rest, re.MULTILINE)
    if nxt is None:
        return rest
    return rest[: nxt.start()]


def _step(job: str, name: str) -> str:
    body = job.split(f"- name: {name}", 1)[1]
    next_step = body.find("\n      - name:")
    if next_step == -1:
        return body
    return body[:next_step]


def test_staging_bucket_is_not_a_job_output() -> None:
    outputs = _job("prepare").split("outputs:", 1)[1].split("\n    steps:", 1)[0]
    assert "staging_bucket:" not in outputs


def test_record_step_reads_the_bucket_from_the_stack() -> None:
    promote = _job("promote")
    record = _step(promote, "Record the live production build")
    assert "needs.prepare.outputs.staging_bucket" not in promote
    assert "PublicWwwStagingBucketName" in record
    assert promote.index("Configure AWS credentials") < promote.index(
        "Record the live production build"
    )


def test_prepare_compares_digests_with_the_step_output() -> None:
    compare = _step(_job("prepare"), "Compare catalogue with the live build")
    assert (
        "STAGING_BUCKET: ${{ steps.resolve_release.outputs.staging_bucket }}" in compare
    )
