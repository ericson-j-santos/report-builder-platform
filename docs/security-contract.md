# T-SQL and database permission boundary

Issue: #7. These rules apply to every report dataset, both before RDL generation
and before Fabric create/update.

## Admission

- Parse with SQLGlot **T-SQL** dialect, raising parser errors.
- Accept exactly one query root (SELECT, WITH/CTE SELECT, or read-only set operation).
- Traverse the entire AST with an explicit allowlist; unsupported functions,
  table-valued sources, unknown constructs, SELECT INTO, assignments, hints,
  recursive CTEs, and statements containing DML/DDL/EXEC fail closed.
- Comments, string literals, and quoted identifiers are syntax, **not** regex
  indications of executable SQL. Unrecognized valid SQL is intentionally rejected.
- This protects against accidental write-capable report SQL, but SQLGlot is a
  parser/transpiler, **not** SQL Server's authoritative security engine.

## Mandatory connection permissions

SQL Server MUST enforce the least-privilege boundary on the principal actually
used for report execution: **read-only access to approved tables/views only**,
no db_owner, db_datawriter, DDL, EXECUTE, schema/object writes or server admin.
Use a dedicated reporting identity; integrated security and
ApplicationIntent=ReadOnly are not substitutes for ACLs.

The API `publish_to_fabric(..., sql_connection=...)` now fails closed without
a live SQL Server DB-API connection. Immediately before Fabric network mutation
it queries effective server/database/schema/object permissions under this
connection, fails closed for rights beyond read-only, and verifies **both**
the exact SQL Server instance reported by SERVERPROPERTY(ServerName) and the
database against ReportSpec's Data Source/Server and Initial Catalog/Database.
Aliases, hostnames and instance aliases must match the registered instance
name exactly; any ambiguity is deliberately blocked. This is a **preflight
control**, not a proof that Fabric's gateway uses the same principal.

The CLI `publish` requires a trusted ODBC DSN name in
`REPORT_BUILDER_READ_ONLY_DSN`, `FABRIC_ACCESS_TOKEN` supplied at runtime,
and the optional `mssql` extra (pyodbc plus an already installed SQL Server
ODBC driver). DSN config and credentials must never be committed. The DSN
name contains no credential; connection errors are sanitized. No network call
to Fabric occurs if the preflight fails.

### External promotion gates (not satisfied by library unit tests)

1. Confirm the runtime identity and effective permissions of the *Fabric
   report data source/gateway* match the independently verified connection.
2. Perform a controlled negative write-permission check against a dedicated
   disposable DEV object; do not run DML on production data.
3. Read the identity, permissions, rendering and export results independently
   for the same DEV report and correlation_id.
4. Preserve the existing ReqSys generator until its pinned-source_sha migration
   has passed READY_FOR_PR and complete E2E gates.

## RDL geometry

Widths may be expressed in `in`, `cm`, `mm`, or `pt`. Every width is
normalized to inches using decimal arithmetic; zero, malformed and oversized
values fail. Table width must match the sum of column widths within 0.000002
inches and fit the printable page width (7.5in portrait, 10in landscape).
RDL geometry is checked **on both create and update before any Fabric request**.

This release is not proof of Fabric rendering/export/email delivery, which
require a separately authorized real DEV integration test.


### Standalone DEV read-only probe

The installed CLI supports `report-builder sql-preflight --spec <ReportSpec.json>`.
This command uses the same integrated-security DSN and permission checks as
`publish`, but needs **no Fabric token** and performs **no Fabric API calls**.
It reports only booleans, not server names, login names, database identities
or connection strings. Repeating it is read-only and idempotent.

Passing this check **does not** confirm the principal configured in Fabric's
gateway. To validate that separate gate, first use the official Power BI
REST `Get Datasources In Group` (paginated report -> gatewayId/datasourceId),
then `Gateways - Get Datasource` to confirm server/database and credential
type, with the permissions required by Microsoft. A gateway datasource's
user-access list does not reveal the SQL Server login actually executing
the query. Only a separately authorized DEV report rendering a controlled
`ORIGINAL_LOGIN()/USER_NAME()/DB_NAME()/SERVERPROPERTY()` diagnostic,
followed by independent export/readback and restricted-permission negative
control, can attest that effective SQL identity end to end.

No Fabric mutation or security-role change is authorized by this probe.
No host, identity, DSN or real SQL Server session has been verified by
the library CI; environment-specific SQL E2E remains blocked until
the existing governed runtime is available and validated.
