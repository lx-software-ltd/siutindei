"""GET and PUT /v1/admin/import-settings."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub
from app.api.admin_request import parse_object_body
from app.db.engine import get_engine
from app.services.import_settings import (
    load_import_settings,
    serialize_import_settings,
    update_import_settings,
)
from app.utils import json_response


def handle_import_settings(event: Mapping[str, Any], method: str) -> dict[str, Any]:
    """Read or replace import behaviour."""
    if method == "GET":
        with Session(get_engine()) as session:
            row = load_import_settings(session)
            return json_response(200, serialize_import_settings(row), event=event)
    if method == "PUT":
        body = parse_object_body(event)
        with Session(get_engine()) as session:
            row = update_import_settings(
                session,
                body,
                updated_by=_get_user_sub(event),
            )
            payload = serialize_import_settings(row)
            session.commit()
        return json_response(200, payload, event=event)
    return json_response(404, {"error": "Not found"}, event=event)
