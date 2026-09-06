# GitHub Project Health Agent

GitHub Project Health Agent is an evidence-driven system that analyzes a
public GitHub repository and produces a structured Project Health Report.

## Current phase

**Phase 5 — AI Analysis + Deterministic Scoring**

The system collects repository evidence via the GitHub REST API, runs
deterministic analyzers (quality, security, dependencies, tests), computes
weighted category scores, and optionally synthesizes a narrative with Gemini
when `GEMINI_API_KEY` is configured.

## Planned architecture

```text
frontend/  Next.js + TypeScript + Tailwind-ready UI
backend/   FastAPI + Pydantic + httpx GitHub REST client + google-genai
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
- google-genai for optional Gemini AI synthesis
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

## Local setup

### Backend

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Secrets are supplied only through environment variables. Never commit `.env`
files or real credentials. `GITHUB_TOKEN` is optional and is used for higher
GitHub API rate limits. `GEMINI_API_KEY` enables optional AI narrative
synthesis (scoring still runs without it). `GEMINI_MODEL` defaults to
`gemini-2.0-flash`.

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
`artifacts/api-server`. These are a preview adapter around the same contract;
the portable source of truth remains `frontend/` and `backend/`.

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

The response contains typed repository information, category scores, overall
score, summary, findings, recommendations, and optional AI synthesis fields.

To try the API locally:

```bash
curl http://localhost:8000/
curl -X POST http://localhost:8000/api/analyze \\
  -H "Content-Type: application/json" \\
  -d '{"repository_url":"https://github.com/torvalds/linux"}'
```

## Tests

With the backend dependencies installed:

```bash
cd backend
pytest
```

## Safety limits

The filtering foundation defines configurable defaults:

- `MAX_FILES=500`
- `MAX_FILE_SIZE=200 KB`
- `MAX_TOTAL_SOURCE_SIZE=10 MB`

They can be overridden through environment variables.

## Remaining work

- Optional UI polish for score visualization
- Optional richer documentation analyzer signals
