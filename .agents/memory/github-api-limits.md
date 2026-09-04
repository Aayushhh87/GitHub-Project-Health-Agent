---
name: GitHub API limits
description: Development and preview behavior when GitHub REST requests are unauthenticated or rate-limited.
---

Unauthenticated GitHub REST calls can be rate-limited by the shared development egress even for small public repositories. The ingestion pipeline must keep working without a token, but surface a safe application-level 429 message and never expose authorization headers.

**Why:** A live preview smoke test reached GitHub's rate limit while mocked backend tests remained deterministic and green.

**How to apply:** Keep `GITHUB_TOKEN` optional, use mocked HTTP responses for automated tests, and treat a live 429 as an environment limitation rather than silently falling back to fake repository data.