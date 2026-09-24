# Contributing

## Development setup

Use Python 3.11 or newer.

```bash
python -m pip install ".[dev,yaml]"
```

## Before opening a pull request

Run the same core checks enforced by CI:

```bash
python -m ruff check .
python -m coverage run -m pytest -q
python -m coverage report
python -m build --wheel
python -m pip install --force-reinstall dist/*.whl
python -m pip check
```

Functional changes must include a positive test and, when a guardrail or conditional
behavior is involved, a negative/control test. Changes to deterministic generation must
also prove identical output for repeated identical input.

## Security and data boundaries

- Never commit tokens, passwords, client secrets, production connection strings or private workspace identifiers.
- Do not add consumer-specific schemas, tables or environment authorization to the reusable core.
- SQL acceptance is intentionally fail-closed and read-only.
- Bearer credentials for Fabric must only be sent to the allowlisted Fabric HTTPS endpoint.
- Do not include upstream HTTP response bodies in user-visible errors.

## Release discipline

A release requires consistent `VERSION`, `pyproject.toml` and
`releases/v<version>.json` metadata. Consumers should pin the immutable
`source_sha` from the release manifest.

Do not reuse a version for different source content.
