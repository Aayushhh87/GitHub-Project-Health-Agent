# GitHub Project Health Agent

GitHub Project Health Agent is an evidence-driven system that analyzes a
public GitHub repository and produces a structured Project Health Report.

## Current phase

**Phase 1 — Portable Project Foundation**

This phase establishes the API contract, repository URL validation, GitHub REST
client boundaries, source-file filtering limits, typed report models, and a
small web interface. The `/api/analyze` endpoint currently validates the
repository URL and returns a structured placeholder report. It does not yet
download repository evidence or calculate a score.

## Planned architecture

```text
frontend/  Next.js + TypeScript + Tailwind-ready UI
backend/   FastAPI + Pydantic + httpx GitHub REST client
docs/      Architecture and product documentation
```

The backend and frontend are intentionally separate so the project can be
continued with Claude Code or another coding agent from its GitHub repository.
GitHub REST API access will be the source of repository evidence; repositories
will not be cloned or downloaded with shell commands.

## Technology stack

- Python 3.11+
- FastAPI and Pydantic
- httpx for GitHub REST API requests
- Next.js, TypeScript, and React
- React + Vite preview app in `artifacts/github-project-health-agent`
- GitHub REST API
- pytest for backend tests

No authentication, database, queue, cache, agent framework, automatic code
fixing, commits, pull requests, or issue creation are part of this phase.

## Folder structure

```text
github-project-health-agent/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── types/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   ├── github/
│   │   ├── analyzer/
│   │   ├── ai/
│   │   ├── scoring/
│   │   ├── models/
│   │   └── utils/
│   └── tests/
├── artifacts/
│   ├── api-server/                  # local preview API adapter
│   └── github-project-health-agent/ # Replit preview UI
├── docs/
├── README.md
└── .gitignore
```

The future analyzer, AI, and scoring directories are reserved architectural
boundaries; they are intentionally empty until their controlled phases begin.

## Local setup

### Backend

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Secrets are supplied only through environment variables. Never commit `.env`
files or real credentials. `GITHUB_TOKEN` is optional in Phase 1 and is
reserved for later GitHub API evidence collection. `OPENROUTER_API_KEY` is
reserved for the later AI phase.

### Frontend

In a second terminal:

```bash
cd frontend
pnpm install
pnpm dev
```

The Next.js development server proxies `/api/*` to `http://localhost:8000` by
default. Set `BACKEND_URL` to point to another local backend, or set
`NEXT_PUBLIC_API_BASE_URL` when the browser should call an API directly.

### Replit preview

The workspace preview uses the React + Vite app under
`artifacts/github-project-health-agent` and the existing API service under
`artifacts/api-server`. These are a preview adapter around the same Phase 1
contract; the portable source of truth remains `frontend/` and `backend/`.

## API

### `GET /`

Returns:

```json
{ "status": "ok" }
```

### `POST /api/analyze`

Request:

```json
{
  "repository_url": "https://github.com/owner/repository"
}
```

The response contains typed repository information, category score placeholders,
summary, findings, recommendations, and the current development phase.

To try the API locally:

```bash
curl http://localhost:8000/
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"repository_url":"https://github.com/torvalds/linux"}'
```

## Tests

With the backend dependencies installed:

```bash
cd backend
pytest
```

The initial suite covers the health endpoint, valid and invalid GitHub URLs,
trailing slashes, `.git` suffixes, and invalid repository input.

## Safety limits

The filtering foundation defines configurable defaults:

- `MAX_FILES=500`
- `MAX_FILE_SIZE=200 KB`
- `MAX_TOTAL_SOURCE_SIZE=10 MB`

They can be overridden through environment variables when the future evidence
collector is implemented.

## Remaining work

- Connect `GitHubClient` to repository metadata, trees, and file contents.
- Apply filtered evidence collection with the safety limits.
- Implement security, dependency, code quality, and test analyzers.
- Add evidence-backed AI synthesis.
- Add scoring and the final dashboard.
