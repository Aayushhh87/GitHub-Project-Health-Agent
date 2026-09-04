---
name: Static analysis boundary
description: Durable safety rule for dependency and test analysis
---

Dependency and test analysis must operate only on repository text already collected under the existing file, size, and total-source limits. Package managers, repository scripts, dependency installation, and repository tests must never be invoked.

**Why:** Dependency manifests and lockfiles are untrusted input, and running their tooling can install code or execute arbitrary lifecycle scripts.

**How to apply:** Prefer standard-library parsing and conservative path/content detection. Optional audit tools may be used only against metadata when already available and when they cannot install dependencies or execute repository code.