# Security

This repository is public. Do not commit secrets, tokens, passwords, client secrets, private workspace identifiers, production connection details or sensitive data.

Connection strings embedded in ReportSpec are validated to reject inline credential material. Runtime credentials for external providers must come from the execution environment and must never be logged.
