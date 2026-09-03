# GitHub Project Health Agent

An evidence-driven foundation for analyzing the health of public GitHub repositories.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the Replit preview API adapter
- `pnpm --filter @workspace/github-project-health-agent run dev` — run the Replit preview UI
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `PYTHONPATH=backend python -m pytest backend/tests` — run portable backend tests
- Required backend env: optional `GITHUB_TOKEN`, reserved `OPENROUTER_API_KEY`

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Portable API: FastAPI + Pydantic + httpx
- Preview API adapter: Express 5
- Portable frontend: Next.js + TypeScript
- Preview frontend: React + Vite
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `backend/app/main.py` — portable FastAPI entrypoint
- `backend/app/api/routes/analysis.py` — Phase 1 analysis route
- `backend/app/github/` — GitHub REST client boundaries and URL parsing
- `backend/app/models/report.py` — typed report contract
- `backend/app/utils/filtering.py` — source collection limits and filters
- `frontend/app/` — portable Next.js UI
- `frontend/lib/api.ts` — frontend API boundary
- `lib/api-spec/openapi.yaml` — shared preview API contract
- `artifacts/github-project-health-agent/` — live Replit preview UI

## Architecture decisions

- The portable source is kept in root `frontend/` and `backend/`; Replit artifacts are preview adapters.
- The Phase 1 analyzer returns a typed placeholder report instead of pretending to score without evidence.
- GitHub access is REST-only and token-based through environment variables.
- The OpenAPI document generates the preview TypeScript client and Zod schemas.

## Product

Users can submit a public GitHub repository URL, receive validation feedback, and
see the typed Phase 1 report shape with category coverage and next-step guidance.

## User preferences

- Portability is a hard requirement: avoid Replit-specific services in the portable app.

## Gotchas

- Re-run API codegen after editing `lib/api-spec/openapi.yaml`.
- Do not introduce analyzers or scoring until their controlled phase is requested.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
