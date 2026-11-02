"""Proposal list filters must not collide with the lifecycle kind argument."""

from __future__ import annotations

from dataclasses import replace

from app.services.data_quality import proposal_lifecycle


def test_location_kind_filter_reaches_the_query() -> None:
    seen: dict[str, object] = {}

    def fake_list(session, **filters):
        del session
        seen.update(filters)
        return {"items": []}

    kind = proposal_lifecycle.ProposalKind.LOCATIONS
    original = proposal_lifecycle._OPS[kind]
    proposal_lifecycle._OPS[kind] = replace(original, list_proposals=fake_list)
    try:
        payload = proposal_lifecycle.list_proposals(
            kind,
            None,
            status="pending",
            kind=None,
        )
    finally:
        proposal_lifecycle._OPS[kind] = original

    assert payload == {"items": []}
    assert seen["status"] == "pending"
    assert seen["kind"] is None
