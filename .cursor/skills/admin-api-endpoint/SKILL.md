---
name: admin-api-endpoint
description: Add or change an API route across the Lambda, API Gateway, OpenAPI, and the Lambda catalog.
---

# API endpoint

1. Handle the path in the Lambda. For `/v1/admin/*`, add one `AdminRoute` row to `_ADMIN_ROUTES` in `backend/src/app/api/admin_routes.py` (resource, handler, `methods`, `sub`, `has_id`, `safe`, and `admin_only` when importer JWTs must be rejected). Do not extend an if-chain in `admin.py`. User routes go in `handle_user_routes`, manager resources in `handle_manager_routes`, and partner routes in `backend/src/app/api/partner_routes.py`. A new data-quality proposal family adds a `ProposalKind` and routes through `handle_proposals` in `admin_proposals.py`. The API Gateway path must match exactly.
2. Register the resource and method in `backend/infrastructure/lib/api-stack.ts` with the right authorizer. Set `apiKeyRequired` when the route needs an API key.
3. Update `docs/api/admin.yaml` or `docs/api/search.yaml` (or `docs/api/partner.yaml` for partner routes), including new component schemas.
4. Update `docs/architecture/lambdas.md` when a function is added or gains routes. Do not copy endpoint parameter lists into architecture docs.
5. In-VPC code calls Cognito and external HTTP only through `app.services.aws_proxy`.

## Done

`python3 scripts/check_openapi_routes.py` and `node scripts/check-lambda-docs.mjs` pass.
