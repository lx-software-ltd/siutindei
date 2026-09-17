# lx-software board catalog parameters

Do not copy CloudFormation parameter values into this repository.

The catalog importer switch and related overrides live in
`lx-software-ltd/lx-software` at
`backend/infrastructure/params/production.json` under the
`lxsoftware:` prefix:

- `lxsoftware:SiutindeiAdminApiBaseUrl`
- `lxsoftware:SiutindeiUserPoolId`
- `lxsoftware:SiutindeiBoardImporterClientId`
- `lxsoftware:SiutindeiBoardCatalogManagerId`
- `lxsoftware:SiutindeiBoardCatalogImportEnabled`

That file is the single source of truth. The lx-software Deploy Backend
job re-applies every `lxsoftware:*` key from it on each deploy, so a
CloudFormation rewrite from this repo is reverted on the next merge.

`scripts/ops/board-importer` only prints the keys after `setup`. Edit
`production.json` in lx-software to change the switch or manager id.
Leave `SiutindeiBoardCatalogImportEnabled` false until a remote board
Preview succeeds.
