# Plan: Pin HTTPS without the broken handler argument

**Status**: Done
**Zone**: yellow

## Goal

HTTPS crawls connect to the checked public IP and present the website name during TLS. A proxy crash fails the run once, with a readable error. Timeouts still retry.

## Non-goals

No change to `aws_proxy.py`. No deploy in this change.

## Files

- `backend/src/app/services/enrichment/fetch.py`
- `backend/src/app/services/enrichment/run.py`
- `tests/test_org_enrichment.py`

## Invariants this change preserves

The connection target stays the IP from `public_address`. Certificate checks still use the website hostname. Private, loopback, and credentialed URLs stay refused.

## Done when

`pytest tests/test_org_enrichment.py` passes, including a fetch that uses the real HTTPS handler and a crawl that fails immediately on `LambdaInvocationError`. `pre-commit run mypy --all-files` passes.

## Rollback

Revert the commit. In-flight runs keep their current status.

## Open questions

None.
