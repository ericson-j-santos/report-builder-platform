# Migration from ReqSys

Source reference: `ericson-j-santos/reqsys-v2-enterprise-real`.

## Extracted in increment 1

- deterministic RDL 2016 generation;
- ReportSpec validation;
- Fabric PaginatedReportDefinition payload generation;
- optional Fabric API client;
- local E2E contract tests;
- negative controls for inline secrets, invalid references and destructive SQL.

## Intentionally not extracted

- ReqSys tables, queries and business vocabulary;
- ReqSys workspace/environment identifiers;
- ReqSys gateway/workflow authorization;
- deployment or promotion configuration.

The ReqSys repository should eventually consume a versioned release of this platform and keep only its domain adapter/specifications.
