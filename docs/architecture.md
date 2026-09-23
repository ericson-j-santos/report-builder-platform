# Architecture

## Contract

`ReportSpec JSON/YAML -> validate_spec -> generate_rdl -> validate_rdl -> Fabric-compatible payload`

## Principles

- Schema-driven input.
- Deterministic output for identical input.
- Fail-closed validation.
- SQL datasets are read-only: only SELECT or CTE (WITH) are accepted.
- No inline password, user credential, client secret or access token in connection strings.
- External publication is optional and requires credentials supplied only at runtime.
- No consumer-specific database/table/workspace is part of the platform contract.

## Consumer boundary

Consumers such as ReqSys own their domain-specific ReportSpec, datasource mapping and environment authorization. This repository owns the reusable generator, validators and provider adapters.
