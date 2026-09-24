# AGENTS.md

This repository contains the reusable Report Builder Platform core.

## Operating contract

1. Preserve the generic boundary: consumer-specific tables, credentials, workspace IDs and business vocabulary do not belong in this repository.
2. Treat ReportSpec validation as fail-closed. New syntax must be explicitly supported and tested before acceptance.
3. Generated RDL must remain deterministic for identical inputs and identity namespaces.
4. SQL accepted by the platform must remain read-only and single-statement.
5. Runtime credentials must never be committed, embedded in ReportSpec, emitted in structured output or copied into exception messages.
6. Fabric requests may send bearer credentials only to the allowlisted HTTPS Fabric API host.
7. Every functional change requires:
   - automated tests;
   - positive validation;
   - negative/control validation when a guardrail is involved;
   - idempotency/determinism validation when generation is affected;
   - installed-package CLI smoke when CLI behavior is affected.
8. Do not treat build success, HTTP success or an isolated log line as E2E evidence.
9. Keep `VERSION`, `pyproject.toml` and release manifests consistent for releases.
10. Consumers must pin an immutable release `source_sha`; movable branches are not a release contract.
11. External Fabric mutation is never part of generic CI. Real publication requires environment-specific authorization and evidence in the consumer project.
12. Never weaken a validation, test or security gate only to make CI green.

## Required local/CI checks

```bash
python -m ruff check .
python -m coverage run -m pytest -q
python -m coverage report
python -m build --wheel
python -m pip install --force-reinstall dist/*.whl
python -m pip check
```

The canonical operational rules for ChatGPT-driven work remain in
`ericson-j-santos/chatgpt-operational-rules`.
