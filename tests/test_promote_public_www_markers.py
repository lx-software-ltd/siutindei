"""The staging bucket name cannot cross the promote jobs as an output."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "promote-public-www.yml"
)


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _step(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(name)


def test_staging_bucket_is_not_a_job_output() -> None:
    outputs = _workflow()["jobs"]["prepare"]["outputs"]
    assert "staging_bucket" not in outputs


def test_record_step_reads_the_bucket_from_the_stack() -> None:
    promote = _workflow()["jobs"]["promote"]
    record = _step(promote, "Record the live production build")
    script = record["run"]
    assert "needs.prepare.outputs.staging_bucket" not in script
    assert "needs.prepare.outputs.staging_bucket" not in str(record.get("env", ""))
    assert "PublicWwwStagingBucketName" in script
    names = [step.get("name") for step in promote["steps"]]
    assert names.index("Configure AWS credentials") < names.index(
        "Record the live production build"
    )


def test_prepare_compares_digests_with_the_step_output() -> None:
    compare = _step(
        _workflow()["jobs"]["prepare"],
        "Compare catalogue with the live build",
    )
    assert (
        compare["env"]["STAGING_BUCKET"]
        == "${{ steps.resolve_release.outputs.staging_bucket }}"
    )
