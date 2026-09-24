# Report Builder Platform

Reusable platform for declarative, deterministic paginated report generation (RDL) and Microsoft Fabric-compatible definitions.

## Scope

The platform owns the generic ReportSpec contract, validation, deterministic RDL generation, Fabric payload creation and optional provider integration. Consumer projects own domain-specific queries, schemas, credentials and environment authorization.

## Versioning

The current canonical release is `v0.1.0`, recorded in `VERSION` and `releases/v0.1.0.json`.

For reproducible consumers, resolve the release manifest and pin the immutable `source_sha` rather than a movable branch or tag. The `v0.1.0` manifest points to:

`07463712333de28a7823491b53c5620bdd4e48b6`

This keeps the human-readable release version and the dependency source independently verifiable.

## Installation

Local checkout:

```bash
python -m pip install .
```

Pinned consumer installation for `v0.1.0`:

```text
report-builder-platform @ git+https://github.com/ericson-j-santos/report-builder-platform.git@07463712333de28a7823491b53c5620bdd4e48b6
```

## Quick start

```bash
report-builder validate --spec examples/items_by_status.json
report-builder generate --spec examples/items_by_status.json --output artifacts/ItemsByStatus.rdl
```

For development:

```bash
python -m pytest -q
```

## Quality baseline

Every pull request is expected to pass the same evidence-driven baseline on Python 3.11 and 3.14:

- Ruff linting;
- bytecode compilation;
- automated tests with branch coverage of at least 80%;
- wheel build, installation and `pip check`;
- installed-CLI positive E2E;
- deterministic/idempotent repeated generation;
- installed-CLI negative control proving write-capable SQL is rejected.

GitHub Actions dependencies are pinned to immutable commit SHAs. Functional evidence is valid only for the exact current commit under review.

## Security boundaries

The generic platform is fail-closed:

- accepted SQL is a single read-only `SELECT` or `WITH` statement;
- write/admin SQL, including SQL Server `SELECT ... INTO`, is rejected;
- Fabric workspace/report identifiers are validated before network activity;
- bearer tokens are used only at runtime;
- long-running-operation callbacks must remain on the HTTPS `api.fabric.microsoft.com/v1/` boundary;
- upstream HTTP response bodies are not echoed into structured failures.

Real Fabric publication is environment-specific and intentionally excluded from generic CI. Consumer projects own external authorization and runtime E2E evidence.

## Guardrails

- SQL is read-only and must start with `SELECT` or `WITH`.
- Destructive/DDL/EXEC commands fail closed.
- Inline credentials in connection strings fail closed.
- Identical ReportSpec input produces identical RDL.
- External publication credentials are accepted only at runtime.

See `docs/architecture.md` and `docs/migration-from-reqsys.md`.
