# GitHub Project Health Agent

An evidence-driven foundation for analyzing the health of public GitHub repositories.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the Replit preview API adapter
- `pnpm --filter @workspace/github-project-health-agent run dev` — run the Replit preview UI
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `PYTHONPATH=backend python -m pytest backend/tests` — run portable backend tests
- Required backend env: optional `GITHUB_TOKEN`, optional `GEMINI_API_KEY` (and optional `GEMINI_MODEL`)

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Portable API: FastAPI + Pydantic + httpx + google-genai
- Preview API adapter: Express 5
- Portable frontend: Next.js + TypeScript
- Preview frontend: React + Vite
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `backend/app/main.py` — portable FastAPI entrypoint
- `backend/app/api/routes/analysis.py` — analysis route (scoring + optional Gemini synthesis)
- `backend/app/github/` — GitHub REST client boundaries and URL parsing
- `backend/app/models/report.py` — typed report contract
- `backend/app/utils/filtering.py` — source collection limits and filters
- `backend/app/ai/analyzer.py` — Gemini AI synthesis
- `backend/app/scoring/engine.py` — deterministic scoring
- `frontend/app/` — portable Next.js UI
- `frontend/lib/api.ts` — frontend API boundary
- `lib/api-spec/openapi.yaml` — shared preview API contract
- `artifacts/github-project-health-agent/` — live Replit preview UI

## Architecture decisions

- The portable source is kept in root `frontend/` and `backend/`; Replit artifacts are preview adapters.
- GitHub access is REST-only and token-based through environment variables.
- AI narrative synthesis uses the official `google-genai` SDK and fails open when the key is missing.
- The OpenAPI document generates the preview TypeScript client and Zod schemas.

## Product

Users can submit a public GitHub repository URL, receive validation feedback, and
see scores plus optional Gemini narrative synthesis when `GEMINI_API_KEY` is set.

## User preferences

- Portability is a hard requirement: avoid Replit-specific services in the portable app.

## Gotchas

- Re-run API codegen after editing `lib/api-spec/openapi.yaml`.
- Set `GEMINI_API_KEY` in `backend/.env` to enable AI synthesis; scoring works without it.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
