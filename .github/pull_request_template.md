## Problem

Describe the concrete problem and why it belongs in the reusable platform.

## Change

Describe the smallest root-cause change.

## Risk

- [ ] No secrets or sensitive identifiers added
- [ ] Consumer/platform boundary preserved
- [ ] SQL/security guardrails preserved or strengthened
- [ ] No external Fabric mutation in generic CI

## Validation

- [ ] Lint
- [ ] Automated tests
- [ ] Branch coverage gate
- [ ] Package build and install
- [ ] Positive E2E/smoke
- [ ] Negative/control case when applicable
- [ ] Determinism/idempotency when applicable

Evidence must refer to the current PR HEAD SHA. A green run from another SHA is not sufficient.

## Release impact

State whether this is unreleased only or requires a new immutable release manifest.
