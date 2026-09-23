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

## Guardrails

- SQL is read-only and must start with `SELECT` or `WITH`.
- Destructive/DDL/EXEC commands fail closed.
- Inline credentials in connection strings fail closed.
- Identical ReportSpec input produces identical RDL.
- External publication credentials are accepted only at runtime.

See `docs/architecture.md` and `docs/migration-from-reqsys.md`.
