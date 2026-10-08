# Bugbot

Review for behavior, security, and contract drift. Mechanical checks
already cover formatting, file length, focused tests, Lambda doc drift,
OpenAPI route drift, and agent-rule shape.

## Zones

Red paths need an explicit human approval noted in the pull request.
The list is `docs/architecture/zones.md`. Flag a red-path edit that
does not mention that approval. Content-kind board briefs are exempt
and may only change `content/**`.

## Invariants

- In-VPC Lambdas call Cognito and external HTTP through
  `app.services.aws_proxy`, and OpenRouter only through
  `app.services.openrouter_client`.
- Do not use `Cors.ALL_ORIGINS`. Secret CDK parameters set `noEcho`.
- A new or changed endpoint updates the CDK route, the OpenAPI spec,
  and `docs/architecture/lambdas.md` in the same change.
- Admin lists stay on the table-first primitives in
  `.cursor/skills/admin-crud-screen/SKILL.md`.
- Public website copy stays out of components. Do not use
  `dangerouslySetInnerHTML`, `eval`, or inline `<svg>`.
- Do not log raw emails, and do not use `print()` in production Python.

## Skip

- Do not ask for a coverage target above the ratchet in
  `.github/workflows/test.yml` (`--cov-fail-under=35`).
- Do not ask to move rules back into `.cursorrules`. That file is a
  pointer. Rules live in `.cursor/rules/`.
- Do not file issues from `NOTE:`, `SECURITY NOTE:`, or
  `next-env.d.ts` comments.
