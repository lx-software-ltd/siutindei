"""Apply or dismiss enrichment proposals through the existing write paths."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.audit import AuditService
from app.db.models import Organization
from app.db.models.org_enrichment import OrgEnrichmentProposal
from app.exceptions import AppError, ValidationError
from app.services.enrichment.apply_rows import apply_one
from app.services.enrichment.constants import MAX_APPLY_IDS
from app.utils.logging import get_logger

logger = get_logger(__name__)

CopyImage = Any
_KIND_ORDER = {
    "update_organization": 0,
    "add_media": 1,
    "create_location": 2,
    "create_activity": 3,
    "create_pricing": 4,
    "create_schedule": 5,
}


def apply_proposals(
    session: Session,
    org_id: UUID,
    ids: list[str],
    overrides: dict[str, dict[str, Any]],
    *,
    user_id: str | None,
    request_id: str | None,
    copy_image: CopyImage | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    if not ids or len(ids) > MAX_APPLY_IDS:
        raise ValidationError("ids must contain 1 to 200 proposals", field="ids")
    org = session.get(Organization, org_id)
    if org is None:
        raise AppError("Organization not found", status_code=404)
    results: list[dict[str, Any]] = []
    pending: list[tuple[int, str, OrgEnrichmentProposal]] = []
    for index, raw_id in enumerate(ids):
        proposal = _load(session, org_id, raw_id)
        if proposal is None:
            results.append({"id": raw_id, "status": "error", "error": "not found"})
            continue
        if proposal.status != "pending":
            results.append({"id": raw_id, "status": "error", "error": "not pending"})
            continue
        pending.append((index, raw_id, proposal))
    logo_ids = {raw for _index, raw, proposal in pending if _is_logo(proposal)}
    if len(logo_ids) > 1:
        for raw in logo_ids:
            results.append({"id": raw, "status": "error", "error": "Pick one logo"})
        pending = [item for item in pending if item[1] not in logo_ids]
    pending.sort(key=lambda item: (_KIND_ORDER.get(item[2].kind, 99), item[0]))
    applied: list[OrgEnrichmentProposal] = []
    fields: list[str] = []
    for _index, raw_id, proposal in pending:
        override = overrides.get(raw_id)
        if override is None:
            override = {}
        if not isinstance(override, dict):
            results.append(
                {"id": raw_id, "status": "error", "error": "override must be an object"}
            )
            continue
        try:
            with session.begin_nested():
                _mark_reason(session)
                apply_one(
                    session,
                    org,
                    proposal,
                    override,
                    copy_image=copy_image,
                )
                proposal.status = "applied"
                proposal.decided_by = user_id
                proposal.decided_at = datetime.now(timezone.utc)
        except (ValidationError, AppError) as exc:
            results.append({"id": raw_id, "status": "error", "error": exc.message})
            continue
        except Exception:
            logger.exception(
                "Enrichment proposal was not applied",
                extra={"proposal_id": raw_id},
            )
            results.append(
                {
                    "id": raw_id,
                    "status": "error",
                    "error": "This change could not be saved.",
                }
            )
            continue
        fields.append(proposal.field or proposal.kind)
        applied.append(proposal)
        results.append({"id": raw_id, "status": "applied"})
    if applied:
        AuditService(session, user_id=user_id, request_id=request_id).log_custom(
            table_name="organizations",
            record_id=str(org_id),
            action="ENRICH_APPLY",
            new_values={
                "fields": fields,
                "proposal_ids": [str(row.id) for row in applied],
            },
        )
        run_ids = {str(row.run_id) for row in applied}
        if len(run_ids) == 1:
            _link_run(session, run_ids.pop())
    session.flush()
    quality_run_id = _stage_quality(session, org_id, applied, user_id)
    return results, quality_run_id


def _is_logo(proposal: OrgEnrichmentProposal) -> bool:
    proposed = (
        proposal.proposed_value if isinstance(proposal.proposed_value, dict) else {}
    )
    return proposal.kind == "add_media" and bool(proposed.get("logo"))


def dismiss_proposals(
    session: Session,
    org_id: UUID,
    ids: list[str],
    *,
    user_id: str | None,
) -> list[dict[str, Any]]:
    if not ids or len(ids) > MAX_APPLY_IDS:
        raise ValidationError("ids must contain 1 to 200 proposals", field="ids")
    results = []
    for raw_id in ids:
        proposal = _load(session, org_id, raw_id)
        if proposal is None or proposal.status != "pending":
            results.append({"id": raw_id, "status": "error", "error": "not pending"})
            continue
        proposal.status = "dismissed"
        proposal.decided_by = user_id
        proposal.decided_at = datetime.now(timezone.utc)
        results.append({"id": raw_id, "status": "dismissed"})
    session.flush()
    return results


def _stage_quality(
    session: Session,
    org_id: UUID,
    applied: list[OrgEnrichmentProposal],
    user_id: str | None,
) -> str | None:
    """Stage the quality run without letting a failure undo the apply."""
    if not applied:
        return None
    from app.services.data_quality.runs import stage_enrichment_run

    try:
        with session.begin_nested():
            return stage_enrichment_run(
                session,
                organization_id=org_id,
                activity_ids=[
                    str(row.entity_id)
                    for row in applied
                    if row.kind == "create_activity" and row.entity_id is not None
                ],
                include_locations=any(
                    row.kind in {"create_location", "create_activity"}
                    for row in applied
                ),
                requested_by=user_id,
            )
    except Exception:
        logger.exception(
            "Enrichment apply did not stage a data-quality run",
            extra={"organization_id": str(org_id)},
        )
        return None


def _load(session: Session, org_id: UUID, raw_id: str) -> OrgEnrichmentProposal | None:
    try:
        proposal_id = UUID(str(raw_id))
    except ValueError:
        return None
    row = session.get(OrgEnrichmentProposal, proposal_id)
    if row is None or str(row.org_id) != str(org_id):
        return None
    return row


def _mark_reason(session: Session) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT set_config('app.catalog_version_reason', 'enrichment', true)")
    )


def _link_run(session: Session, run_id: str | None) -> None:
    bind = session.get_bind()
    if not run_id or bind is None or bind.dialect.name != "postgresql":
        return
    session.execute(
        text(
            "UPDATE catalog_versions SET related_id = :run_id, "
            "reason = CASE WHEN reason IS NULL OR reason = '' "
            "THEN 'enrichment' ELSE reason END "
            "WHERE txid = txid_current() AND related_id IS NULL "
            "AND (reason IS NULL OR reason = '' OR reason = 'enrichment' "
            "OR reason = 'children' OR entity_type = 'media')"
        ),
        {"run_id": run_id},
    )
