# Changelog

All notable changes to the reusable platform are recorded here.

## Unreleased

### Security

- Reject multi-statement SQL and SQL Server `SELECT ... INTO` writes.
- Validate Fabric workspace/report identifiers as UUIDs before network activity.
- Restrict Fabric long-running-operation callbacks to the allowlisted HTTPS API host.
- Stop echoing upstream Fabric HTTP response bodies in exception messages.

### Quality

- Add Python 3.11/3.14 CI matrix.
- Add Ruff linting and branch coverage gate.
- Build and install the wheel before installed-CLI E2E checks.
- Add positive, negative and deterministic/idempotent CLI controls.
- Add repository contribution and evidence requirements.

## 0.1.0 - 2026-09-23

- Extract reusable deterministic RDL 2016 generation.
- Add ReportSpec validation and Fabric-compatible payload generation.
- Add consumer-specific deterministic identity namespace support.
- Publish immutable release source metadata for ReqSys consumption.
