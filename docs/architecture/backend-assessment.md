# Backend Improvement Assessment

> **Date:** 2026-03-02
> **Branch:** `cursor/backend-improvements-assessment-04ed`
> **Scope:** All Python code under `backend/`, `tests/`, and related Lambda handlers.
> **Remediation commit:** `f238cdd`
> **Status (2026-11-02):** Every item is fixed. Later code still has a few
> unlogged `except Exception:` blocks (for example
> `backend/src/app/db/catalog_locks.py` and
> `backend/src/app/services/enrichment/fetch.py`), so the checklist's
> `except Exception:` line is open.

---

## How to use this document

Each item below is a self-contained task. Items are grouped by severity.
Within each item you will find:

- **What:** a description of the problem.
- **Where:** exact file paths and line numbers.
- **Why it matters:** impact if left unfixed.
- **Fix:** concrete steps to resolve it.

After completing a fix, tick the checkbox and note the commit SHA.

---

## Critical

### C-1: `create_organization` / `update_organization` trapped inside helper function

- [x] **Fixed**

**What:** In `OrganizationRepository`, the methods `create_organization` (line 108)
and `update_organization` (line 131) are indented inside `_escape_like_pattern`,
making them nested functions instead of class methods. They are unreachable via
`repo.create_organization()`.

**Where:** `backend/src/app/db/repositories/organization.py`, lines 108–155.

**Why it matters:** Any future code (or test) that calls
`OrganizationRepository.create_organization()` will raise `AttributeError`.
Production currently avoids this because admin routes use a different code path
(`_create_organization` in `admin_resource_organization.py`), but the bug is
latent.

**Fix:**
1. Dedent `create_organization` and `update_organization` by one level so they
   are methods of `OrganizationRepository`.
2. Verify that `_escape_like_pattern` ends cleanly before the next method.
3. Run `pre-commit run ruff-format --all-files` and confirm no indentation errors.
4. Run existing tests to confirm no regressions.

---

### C-2: Test fixtures and repository tests are stale / broken

- [x] **Fixed**

**What:** Test fixtures reference columns and methods that no longer exist in the
schema.

**Where:**
- `tests/conftest.py`, line 88 — `sample_organization_data`: omits the
  now-required `manager_id` column.
- `tests/conftest.py`, line 119 — `sample_location_data`: uses `district`
  (dropped in migration `0015_drop_loc_dist_ctry`); should use `area_id`.
- `tests/conftest.py`, lines 130–138 — `sample_location`: builds a `Location`
  with `district`.
- `tests/test_repositories.py`, lines 136–175 — `TestLocationRepository`: calls
  `repo.create_location(district=...)` and `repo.find_by_district()`, neither of
  which exist on `LocationRepository`.

**Why it matters:** Repository tests are silently skipped in CI (no
`TEST_DATABASE_URL`), masking the fact that they would fail against the real
schema. The test suite provides a false sense of coverage.

**Fix:**
1. Update `sample_organization_data` to include `manager_id` (use a UUID
   string, e.g., `'00000000-0000-0000-0000-000000000001'`).
2. Update `sample_location_data` to use `area_id` instead of `district`.
   Create a `sample_geographic_area` fixture that inserts a `GeographicArea`
   row and reference its `id`.
3. Update `sample_location` to match.
4. Rewrite `TestLocationRepository` to use the current `LocationRepository` API
   (e.g., `find_by_area` instead of `find_by_district`).
5. Check other fixtures (`sample_schedule_data`, etc.) for staleness against
   current models.
6. Run `pytest tests/` (with SQLite) and confirm all non-PostgreSQL tests pass.

---

## High

### H-1: Exception details leaked in 500 responses

- [x] **Fixed**

**What:** The catch-all error handlers return `"detail": str(exc)` in the HTTP
response body. This can expose internal information (table names, file paths,
library versions) to API consumers.

**Where:**
- `backend/src/app/api/admin.py`, lines 214–216.
- `backend/src/app/api/search.py`, lines 74–76.

**Why it matters:** Information leakage. An attacker can trigger errors to
fingerprint the stack.

**Fix:**
1. Remove the `"detail": str(exc)` key from both 500 response bodies.
2. The exception is already logged via `logger.exception()` on the preceding
   line, so no diagnostic information is lost.
3. Final response: `{"error": "Internal server error"}`.

---

### H-2: PII (email) logged without masking in `define_auth_challenge`

- [x] **Fixed**

**What:** The Cognito Define Auth Challenge trigger logs the user's email
address in plain text at four locations.

**Where:** `backend/lambda/auth/define_auth_challenge/handler.py`, lines 26, 35,
41, 46.

```python
logger.debug(f"Define auth challenge for {username}", ...)
logger.info(f"Auth successful for {username}")
logger.warning(f"Max auth attempts reached for {username}")
logger.debug(f"Issuing custom challenge for {username}")
```

**Why it matters:** Violates the project's mandatory security rule: "NEVER log
PII (emails, names) without masking."

**Fix:**
1. Import `mask_email` from `app.utils.logging`.
2. Replace every bare `{username}` in log messages with `{mask_email(username)}`.
3. Audit the other auth triggers (`create_auth_challenge`, `verify_auth_challenge`,
   `post_authentication`) for the same issue — `post_authentication` already uses
   `mask_email`; verify the others do too.

---

### H-3: Silent exception swallowing in `admin_cognito.py`

- [x] **Fixed**

**What:** Two `except Exception:` blocks catch and discard exceptions without
logging or binding.

**Where:**
- `backend/src/app/api/admin_cognito.py`, line 167 — groups lookup for user
  listing.
- `backend/src/app/api/admin_cognito.py`, line 306 — `_fetch_last_auth_time`.

```python
except Exception:
    user_data["groups"] = []
```

```python
except Exception:
    return None
```

**Why it matters:** Cognito API failures (throttling, permission errors, network
issues) become invisible in CloudWatch, making debugging impossible.

**Fix:**
1. Bind the exception: `except Exception as exc:`.
2. Log it: `logger.warning("Failed to fetch groups for user", extra={"error": str(exc)})`.
3. Optionally narrow to `except ClientError as exc:` if only AWS errors are
   expected, with a separate `except Exception` for truly unexpected failures.

---

## Medium

### M-1: Duplicated utility functions across authorizer Lambdas

- [x] **Fixed**

**What:** Three functions are copy-pasted across authorizer handlers:

| Function          | Lines | Files                                           |
|-------------------|-------|-------------------------------------------------|
| `_get_header()`   | ~8    | `cognito_group/handler.py`, `cognito_user/handler.py`, `device_attestation/handler.py` |
| `_extract_token()` | ~10  | `cognito_group/handler.py`, `cognito_user/handler.py` |
| `_policy()`       | ~35   | `cognito_group/handler.py`, `cognito_user/handler.py`, `device_attestation/handler.py` |

**Where:**
- `backend/lambda/authorizers/cognito_group/handler.py`, lines 31–89.
- `backend/lambda/authorizers/cognito_user/handler.py`, lines 29–87.
- `backend/lambda/authorizers/device_attestation/handler.py`, lines 30–61.

**Fix:**
1. Create `backend/lambda/authorizers/_common.py`.
2. Move `_get_header`, `_extract_token`, and `_policy` into it.
3. Import from `_common` in each handler.
4. Note: `device_attestation`'s `_policy` does not broaden the resource for
   caching like the cognito authorizers do. Unify the logic with an optional
   `broaden_resource` parameter (default `True`), or keep a separate slim
   version. Document the difference.

**Resolution:** the shared helpers live in
`backend/src/app/auth/authorizer_helpers.py` (`get_header`, `extract_token`,
`policy`),
not in `backend/lambda/authorizers/_common.py`.

---

### M-2: Duplicated feedback-star helpers

- [x] **Fixed**

**What:** Two identical functions exist in two files:

| Function                       | File 1 (lines)              | File 2 (lines)              |
|-------------------------------|-----------------------------|-----------------------------|
| `_safe_adjust_feedback_stars` | `admin_feedback.py:556–564` | `admin_tickets.py:542–550`  |
| `_feedback_stars_per_approval`| `admin_feedback.py:567–575` | `admin_tickets.py:553–561`  |

**Where:**
- `backend/src/app/api/admin_feedback.py`, lines 556–575.
- `backend/src/app/api/admin_tickets.py`, lines 542–561.

**Fix:**
1. Create `backend/src/app/utils/feedback.py` (or add to an existing utils
   module).
2. Move both functions there.
3. Import from the shared module in both `admin_feedback.py` and
   `admin_tickets.py`.

---

### M-3: Duplicated limit-validation pattern

- [x] **Fixed**

**What:** The same limit parsing and range-check code is repeated in at least
four modules:

```python
limit = parse_int(_query_param(event, "limit")) or 50
if limit < 1 or limit > 200:
    raise ValidationError("limit must be between 1 and 200", field="limit")
```

**Where:**
- `backend/src/app/api/admin_crud.py`, lines 105–107.
- `backend/src/app/api/admin_audit.py`, lines 79–81.
- `backend/src/app/api/admin_feedback.py`, lines 297–299.
- `backend/src/app/api/admin_tickets.py`, lines 292–294.

**Fix:**
1. Add a helper to `backend/src/app/api/admin_request.py` (or a new shared
   location):

   ```python
   def parse_limit(event: Mapping[str, Any], *, default: int = 50, max_limit: int = 200) -> int:
       limit = parse_int(_query_param(event, "limit")) or default
       if limit < 1 or limit > max_limit:
           raise ValidationError(
               f"limit must be between 1 and {max_limit}", field="limit"
           )
       return limit
   ```

2. Replace all four (or more) inline blocks with a call to `parse_limit(event)`.

---

### M-4: Overly broad `except Exception` in 15+ locations

- [x] **Fixed**

**What:** Many handlers use `except Exception as exc:` where more specific
exception types would be appropriate and safer.

**Where (non-exhaustive):**
- `backend/src/app/api/admin_cognito.py`: lines 75, 122.
- `backend/src/app/api/admin_feedback.py`: lines 242, 285, 560.
- `backend/src/app/api/admin_tickets.py`: lines 200, 283, 546.
- `backend/src/app/api/admin_ticket_notifications.py`: line 167.
- `backend/src/app/api/admin_suggestions.py`: line 252.
- `backend/src/app/api/admin_resource_pricing.py`: line 107.
- `backend/src/app/auth/jwt_validator.py`: lines 177, 240, 290.
- `backend/src/app/services/aws_proxy.py`: lines 113, 197, 206.
- `backend/src/app/api/health.py`: line 108.

**Fix:**
1. For each location, identify the expected exception type:
   - AWS calls → `botocore.exceptions.ClientError`
   - DB calls → `sqlalchemy.exc.SQLAlchemyError`
   - Proxy calls → `app.exceptions.AwsProxyError` (if defined) or `RuntimeError`
   - JWT calls → `jwt.exceptions.PyJWTError`
2. Narrow the `except` clause accordingly.
3. Keep a final `except Exception` only in top-level safety-net handlers (like
   `_safe_handler`) and ensure it logs the full traceback.

---

### M-5: `_handle_approve_reject_ticket` is ~190 lines and handles 5+ ticket types

- [x] **Fixed**

**What:** A single function handles approval/rejection for access requests,
suggestions, feedback, org creation, and location creation tickets. It's hard to
read, test, and extend.

**Where:** `backend/src/app/api/admin_tickets.py`, lines 351–539.

**Fix:**
1. Extract per-ticket-type handlers:
   - `_approve_access_request(session, ticket, body, event)`
   - `_approve_suggestion(session, ticket, body, event)`
   - `_approve_feedback(session, ticket, body, event)`
   - `_approve_org_creation(session, ticket, body, event)`
   - `_approve_location_creation(session, ticket, body, event)`
2. Have `_handle_approve_reject_ticket` dispatch to the correct sub-handler
   based on `ticket.ticket_type`.
3. Each sub-handler should be independently testable.

---

### M-6: No working integration tests in CI

- [x] **Fixed**

**What:**
- `backend/requirements.txt` does not include `pytest` or `pytest-cov`.
- Repository tests in `tests/test_repositories.py` require PostgreSQL
  (`TEST_DATABASE_URL`) but CI doesn't provision one, so they're always skipped.
- No coverage reporting is generated.

**Where:**
- `backend/requirements.txt`.
- `.github/workflows/test.yml` (or equivalent CI config).

**Fix:**
1. Add `pytest>=8.0` and `pytest-cov>=5.0` to a `dev-requirements.txt` or
   a `[project.optional-dependencies]` section.
2. Add a PostgreSQL service container to the CI test job.
3. Set `TEST_DATABASE_URL` in the CI environment.
4. Add `--cov=app --cov-report=xml` to the pytest invocation.
5. Consider adding a coverage gate (e.g., fail if coverage drops below a
   threshold).

---

## Low

### L-1: No `pyproject.toml` for backend

- [x] **Fixed**

**What:** The backend uses only `requirements.txt`. Configuration for ruff,
mypy, and pytest is scattered or missing.

**Where:** `backend/` root.

**Fix:**
1. Create `backend/pyproject.toml` with:
   - `[project]` metadata.
   - `[tool.ruff]` — line length, target version, select rules.
   - `[tool.pytest.ini_options]` — test paths, markers.
   - `[tool.mypy]` — strict mode, ignore patterns.
2. Keep `requirements.txt` for Lambda bundling (it's simpler for `pip install
   -r` during CDK builds).

---

### L-2: Magic numbers without named constants

- [x] **Fixed**

**What:** Several numeric literals lack named constants.

**Where:**
- `backend/src/app/api/admin_suggestions.py`, line 114 — `100` for district max
  length. Use `MAX_DISTRICT_LENGTH = 100`.
- `backend/src/app/api/admin_cognito.py`, line 350 — `limit=1000` for org
  transfer query. Use `MAX_ORG_TRANSFER_LIMIT = 1000`.
- Various modules — the `1–200` limit range for pagination is repeated as raw
  integers. After M-3, this will be centralized.

**Fix:**
1. Define constants at module or package level.
2. Reference them in the code.

---

### L-3: Fragile Cognito filter string interpolation

- [x] **Fixed**

**What:** Cognito `ListUsers` calls build filter strings via f-string
interpolation.

**Where:** `backend/src/app/api/admin_cognito.py`, lines 86 and 243.

```python
Filter=f'sub = "{user_sub}"'
```

`user_sub` comes from JWT claims (trusted), but if it ever contained a `"` it
would break the Cognito filter syntax.

**Fix:**
1. Add a validation step that ensures `user_sub` matches the expected UUID
   pattern (`^[0-9a-f-]{36}$`) before interpolation.
2. Or use `user_sub.replace('"', '')` as a defensive measure.

---

### L-4: Inconsistent type-hint style

- [x] **Fixed**

**What:** Minor inconsistencies in type hint usage across the codebase.

**Where:**
- `backend/src/app/api/admin_request.py`, line 8 — imports `Tuple` from
  `typing` instead of using the built-in `tuple`.
- `backend/src/app/auth/jwt_validator.py`, line 269 — `from datetime import
  datetime, timezone` inside a function body instead of at module level.
- Several private helpers lack return type annotations.

**Fix:**
1. Replace `Tuple` with `tuple` in `admin_request.py`.
2. Move the `datetime` import to module level in `jwt_validator.py`.
3. Add return type annotations to private helpers across the codebase
   (best done incrementally).

---

### L-5: Detached ORM object accessed after session close

- [x] **Fixed**

**What:** In `_submit_user_feedback`, the `organization` object is used after
the `Session` context manager exits. Accessing already-loaded scalar attributes
on a detached SQLAlchemy instance works but is fragile.

**Where:** `backend/src/app/api/admin_feedback.py`, lines 170–191.

**Fix:**
1. Capture `organization_id` and `organization_name` as local variables inside
   the `with Session(...)` block.
2. Use those variables after the block closes instead of the detached ORM
   object.

---

### L-6: Missing seed data for newer tables

- [x] **Fixed**

**What:** Tables added in recent migrations lack seed data for local
development.

**Where:** `backend/db/seed/seed_data.sql`.

**Tables missing seed data:**
- `feedback_labels` (migration 0027).
- `organization_feedback` (migration 0027).
- `tickets` (useful for testing ticket workflows).

**Fix:**
1. Add representative seed rows for `feedback_labels` (e.g., "Service Quality",
   "Value for Money", "Facilities").
2. Optionally add a sample `organization_feedback` row.
3. Optionally add a sample `tickets` row.
4. Verify seed runs cleanly: `alembic upgrade head` → `psql -f seed_data.sql`.

---

### L-7: Missing type hints on auth Lambda handlers

- [x] **Fixed**

**What:** Several Cognito trigger handlers lack type annotations on
`lambda_handler`.

**Where:**
- `backend/lambda/auth/define_auth_challenge/handler.py`, line 15.
- `backend/lambda/auth/verify_auth_challenge/handler.py`, line 18.
- `backend/lambda/auth/create_auth_challenge/handler.py`, line 20.

**Fix:**
1. Add type hints:
   ```python
   def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
   ```
2. Add the necessary imports (`from typing import Any`).

---

## Verification checklist

After all fixes are applied:

- [ ] `pre-commit run --all-files` passes (ruff format + lint, mypy).
- [ ] `pytest tests/` passes with no skipped tests (except PostgreSQL-only if
  no DB available).
- [ ] No `str(exc)` in any HTTP 500 response body.
- [ ] `grep -r "except Exception:" backend/src/` returns only intentional
  safety-net handlers, each with logging.
- [ ] No bare email addresses in any `logger.*()` call under `backend/lambda/`.
- [ ] No duplicate function definitions across files (authorizer helpers,
  feedback-star helpers, limit validation).
