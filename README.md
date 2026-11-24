# Siu Tin Dei

An app for searching and booking activities for children across Hong Kong and beyond.

This repository is the whole product: the mobile app families use to find
activities by age, district, price, time, and language; the admin console
where organisations, activities, schedules, and pricing are managed; the
public website; and the backend API they share.

This repository is public. Secrets and private personal data stay out of git.

## What is here

| Path | What it is |
| --- | --- |
| `apps/siutindei_app/` | The Flutter mobile app. |
| `apps/admin_web/` | The admin console. |
| `apps/public_www/` | The public website. |
| `backend/` | The Python API (`lambda/` and `src/`), the database migrations (`db/`), and the AWS CDK app (`infrastructure/`). |
| `shared/` | Fixtures and the home wizard choices the apps share. |
| `content/` | Editorial copy for board briefs of kind `content`. The apps do not import it. |
| `tests/` | Backend tests. |
| `scripts/` | Checks, code generation, the board policy, and deploy scripts. |
| `docs/` | Architecture, API specs, deployment runbooks, and legal notes. |

## Working here

Read [`AGENTS.md`](AGENTS.md) before changing anything. Agent instructions
live in `AGENTS.md`, `.cursor/rules/`, and `.cursor/skills/`. Autonomy
follows [`docs/architecture/zones.md`](docs/architecture/zones.md), which
says which paths need a plan or an approval first.

### Setup

All deployment prerequisites and configuration steps are now documented in
`docs/architecture/setup.md`.

## Documentation

- [`docs/architecture/overview.md`](docs/architecture/overview.md): the
  components and how they fit together.
- [`docs/architecture/security.md`](docs/architecture/security.md): the
  security controls.
- [`docs/architecture/setup.md`](docs/architecture/setup.md): deployment
  prerequisites and configuration.
- [`docs/architecture/public-www.md`](docs/architecture/public-www.md): the
  public website, its staging environment, and promotion.
- [`docs/api/`](docs/api/): the API specs.
- [`docs/deployment/`](docs/deployment/): the admin console and mobile
  runbooks, and the launch checklist.
- [`docs/legal/README.md`](docs/legal/README.md): where the privacy policy
  and terms live.

## Security

To report a vulnerability, follow [`SECURITY.md`](SECURITY.md). Do not open a
public issue.

## Licence

Licensed under the Apache License, Version 2.0. The full text is in
[`LICENSE`](LICENSE).
