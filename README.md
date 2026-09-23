# Report Builder Platform

Reusable platform for declarative, deterministic paginated report generation (RDL) and Microsoft Fabric-compatible definitions.

## Scope

The platform owns the generic ReportSpec contract, validation, deterministic RDL generation, Fabric payload creation and optional provider integration. Consumer projects own domain-specific queries, schemas, credentials and environment authorization.

## Quick start

```bash
python -m pytest -q
python -m report_builder.report_factory validate --spec examples/items_by_status.json
python -m report_builder.report_factory generate --spec examples/items_by_status.json --output artifacts/ItemsByStatus.rdl
```

## Guardrails

- SQL is read-only and must start with `SELECT` or `WITH`.
- Destructive/DDL/EXEC commands fail closed.
- Inline credentials in connection strings fail closed.
- Identical ReportSpec input produces identical RDL.
- External publication credentials are accepted only at runtime.

See `docs/architecture.md` and `docs/migration-from-reqsys.md`.
