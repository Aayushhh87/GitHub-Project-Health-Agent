# Phase 1 foundation notes

Phase 1 is intentionally a contract-and-boundaries milestone. It does not
claim to assess a repository yet.

## Evidence boundary

The future analyzer should use the GitHub REST API through
`backend/app/github/client.py`. It should pass repository paths through
`backend/app/utils/filtering.py` before requesting file contents. The client
must never shell out to `git clone`, download an archive, or execute repository
code.

## Report boundary

`HealthReport` is the stable boundary between future analyzers and the user
interface. A score may remain `null` until evidence for that category has been
collected and evaluated. Findings must retain severity, description, and
evidence so recommendations can be traced back to observable repository
signals.
