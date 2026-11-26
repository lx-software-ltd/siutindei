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
| [`apps/siutindei_app/`](apps/siutindei_app/) | The Flutter mobile app. |
| [`apps/admin_web/`](apps/admin_web/) | The admin console. |
| [`apps/public_www/`](apps/public_www/) | The public website. |
| [`backend/`](backend/) | The Python API (`lambda/` and `src/`), the database migrations (`db/`), and the AWS CDK app (`infrastructure/`). |
| [`shared/`](shared/) | Fixtures and the home wizard choices the apps share. |
| [`content/`](content/) | Editorial copy for board briefs of kind `content`. The apps do not import it. |
| [`tests/`](tests/) | Backend tests. |
| [`scripts/`](scripts/) | Checks, code generation, the board policy, and deploy scripts. |
| [`docs/`](docs/) | Architecture, API specs, deployment runbooks, and legal notes. |

## Working here

Read [`AGENTS.md`](AGENTS.md) before changing anything. Autonomy
follows [`docs/architecture/zones.md`](docs/architecture/zones.md), which
says which paths need a plan or an approval first.

## Documentation

- [`docs/architecture/overview.md`](docs/architecture/overview.md): the
  components and how they fit together.
- [`docs/architecture/security.md`](docs/architecture/security.md): the
  security controls.
- [`docs/architecture/setup.md`](docs/architecture/setup.md): deployment
  prerequisites and configuration.
- [`docs/architecture/zones.md`](docs/architecture/zones.md): which paths
  need a plan or an approval first.
- [`docs/architecture/decisions.md`](docs/architecture/decisions.md):
  architecture decisions.
- [`docs/architecture/public-www.md`](docs/architecture/public-www.md): the
  public website, its staging environment, and promotion.
- [`docs/architecture/admin-web-ui.md`](docs/architecture/admin-web-ui.md):
  the admin console layout.
- [`docs/architecture/lambdas.md`](docs/architecture/lambdas.md): the
  Lambda catalogue.
- [`docs/architecture/database-schema.md`](docs/architecture/database-schema.md):
  the Aurora schema.
- [`docs/architecture/audit-logging.md`](docs/architecture/audit-logging.md):
  database audit logging.
- [`docs/architecture/aws-assets-map.md`](docs/architecture/aws-assets-map.md)
  and [`docs/architecture/aws-messaging.md`](docs/architecture/aws-messaging.md):
  assets and messaging.
- [`docs/architecture/data-quality.md`](docs/architecture/data-quality.md),
  [`docs/architecture/category-suggestions.md`](docs/architecture/category-suggestions.md),
  and [`docs/architecture/organization-suggestions.md`](docs/architecture/organization-suggestions.md):
  catalogue quality and suggestions.
- [`docs/architecture/github-rulesets.md`](docs/architecture/github-rulesets.md):
  the rulesets on `main`, `staging`, and `v*` tags.
- [`docs/architecture/cloudflare-optimization.md`](docs/architecture/cloudflare-optimization.md):
  Cloudflare.
- [`docs/architecture/backend-assessment.md`](docs/architecture/backend-assessment.md):
  the backend assessment.
- [`docs/architecture/executive-board-autonomy-siutindei-appendix-a.md`](docs/architecture/executive-board-autonomy-siutindei-appendix-a.md):
  the Executive Board hand-off.
- [`docs/api/public.yaml`](docs/api/public.yaml),
  [`docs/api/admin.yaml`](docs/api/admin.yaml), and
  [`docs/api/partner.yaml`](docs/api/partner.yaml): the API specs.
- [`docs/deployment/admin-web.md`](docs/deployment/admin-web.md),
  [`docs/deployment/android-play-store.md`](docs/deployment/android-play-store.md),
  [`docs/deployment/ios-testflight.md`](docs/deployment/ios-testflight.md),
  and [`docs/deployment/launch-checklist.md`](docs/deployment/launch-checklist.md):
  the runbooks and the launch checklist.
- [`docs/legal/README.md`](docs/legal/README.md) and
  [`docs/legal/store-disclosures.md`](docs/legal/store-disclosures.md):
  where the privacy policy and terms live, and the store disclosures.
- [`docs/plans/README.md`](docs/plans/README.md) and
  [`docs/research/README.md`](docs/research/README.md): open plans and
  the research memos behind them.
- [`docs/board-dry-run.md`](docs/board-dry-run.md): the board dry run.
- [`docs/imports/lxsoftware-board-catalog-params.md`](docs/imports/lxsoftware-board-catalog-params.md):
  board catalog parameters.
- [`docs/remediation/public-www-and-api-remediation.md`](docs/remediation/public-www-and-api-remediation.md):
  public website and search API remediation.
- Mobile app notes start at
  [`apps/siutindei_app/docs/getting-started.md`](apps/siutindei_app/docs/getting-started.md).
  The layer notes are linked from
  [`apps/siutindei_app/README.md`](apps/siutindei_app/README.md).

## Security

To report a vulnerability, follow [`SECURITY.md`](SECURITY.md). Do not open a
public issue.

## Licence

Licensed under the Apache License, Version 2.0. The full text is in
[`LICENSE`](LICENSE).
