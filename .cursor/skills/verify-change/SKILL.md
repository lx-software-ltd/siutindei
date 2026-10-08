---
name: verify-change
description: Choose the commands that prove a change and record the evidence in the pull request.
---

# Verify a change

Run the narrowest command that exercises the edit, then the area lint.

- Python: `pytest tests/<relevant_test>.py` and, before commit, `pre-commit run ruff-format --all-files`.
- Admin web: `npm run lint` and `npm run typecheck` in `apps/admin_web`. Dev server is `npm run dev` on port 3000.
- Public website: `npm run lint` and `npm test` in `apps/public_www`. Dev server port is 3100.
- CDK: `npm run lint` and `npm run build` in `backend/infrastructure` when a stack changed.
- Agent rules: `python3 scripts/validate_agent_rules.py`.

A UI behavior change is verified in the browser (click, type, submit, and the other screens that share the state), not by a single screenshot.

When admin web behavior changes, update `apps/admin_web/e2e`. Keep mock responses aligned with `docs/api/*.yaml`.

Paste the commands and the result into the pull request. CI remains the merge gate.

## Done

The pull request lists the zone, the checks you ran, and the docs or seed decision. Local harness scripts pass.
