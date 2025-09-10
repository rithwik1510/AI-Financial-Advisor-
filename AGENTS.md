# Repository Guidelines (OpenAI-compatible)

## Project Structure & Module Organization
- `backend/app/` – FastAPI app: `routers/`, `services/`, `schemas/`, `main.py`.
- `frontend/` – React + Vite UI: `src/components/`, `src/styles/`, `index.html`.
- `analyze_financial_data.py` – optional local CLI analyzer.
- Do not edit generated/vendor folders: `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`.
- Backend: add endpoints under `backend/app/routers`; keep business logic in `backend/app/services` (pure, testable). Frontend UI pieces live in `frontend/src/components`.

## Build, Test, and Development Commands
- Backend (dev):
  - One‑command runner (Windows PowerShell):
    - `backend/run_dev.ps1` → creates venv, installs deps, prompts for `GEMINI_API_KEY` (saved to `backend/.env`), starts Uvicorn on http://localhost:8000
  - Manual:
    ```bash
    cd backend && python -m venv .venv
    .venv\Scripts\activate  # Windows (or: source .venv/bin/activate)
    pip install -r requirements.txt
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```
- Frontend (dev/build):
  - `frontend/run_dev.ps1` to install and start Vite on http://localhost:5173
  - Or manually:
    ```bash
    cd frontend && npm install
    npm run dev   # http://localhost:5173
    npm run build && npm run preview
    ```
- CLI utility:
  ```bash
  python analyze_financial_data.py --input <folder> --output analysis.json
  ```

## LLM Provider (OpenAI-compatible)
- Required env: `OPENAI_API_KEY`.
- Optional: `OPENAI_BASE_URL` (default `https://api.openai.com/v1`), `OPENAI_MODEL` (default `gpt-4o-mini`).
- `.env` loading: backend auto-loads nearest `.env` (via `python-dotenv`). See `backend/.env.example`.
- Health check: `GET /api/llm/status` (returns precise error messages when misconfigured).

## Coding Style & Naming Conventions
- Python: PEP 8 (4 spaces), type hints. Pydantic models in PascalCase; API fields snake_case. Keep I/O in routers; computations in `services/`. Small, single‑purpose functions with docstrings.
- TypeScript/React: functional components, PascalCase filenames (e.g., `FileUpload.tsx`, `SettingsModal.tsx`). Keep API calls in `src/api.ts`. Use Tailwind utilities; avoid inline styles.
- Filenames and modules should be descriptive; avoid abbreviations. Avoid default exports for utilities; components may default‑export.

## Testing Guidelines
- No formal tests yet. When adding:
  - Backend: `pytest` under `backend/tests/` (`test_*.py`). Mock Gemini/network.
  - Frontend: `vitest` + Testing Library under `frontend/src/__tests__/` (`*.test.tsx`).
  - Aim for high coverage on `services/` (analytics, parsing, tools). Keep tests deterministic.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.
- PRs: focused scope, clear description, linked issues, validation steps, and screenshots for UI changes. Ensure backend runs and `npm run build` succeeds.
- Exclude artifacts (`dist/`, `.venv/`, `node_modules/`) from commits. Keep diffs minimal; avoid drive‑by formatting.

## Security & Configuration Tips
- Parsing and analytics run locally. Q&A uses Gemini; only analytics summaries and your question (or attached docs when using `/api/ask/docs`) are sent to the provider.
- Do not log or persist raw statements. Never commit secrets.
- Optional envs: `ENABLE_OCR=1` (for OCR pipeline), `GEMINI_MODEL`.

---

## Current Architecture & Features (Updated)

Backend
- Endpoints: `/api/parse` (CSV/XLSX only), `/api/analyze`, `/api/ask`, `/api/ask/stream` (SSE), `/api/tools/{mortgage_payment,affordability}`, `/api/llm/status`, `/api/health`.
- Analytics: category auto‑labeling, savings rate, DTI, emergency‑fund months, discretionary share, anomalies, recurring detection, health score.
- Budgets: `AnalyzeInput` accepts `budgets` and `category_rules`; response includes `budget_variance` (avg monthly actual vs target).
- LLM: OpenAI‑compatible chat completions via `OPENAI_API_KEY`. Document Q&A (`/api/ask/docs`) is not supported in this build.
- Dev scripts: `backend/run_dev.ps1` prompts and stores `OPENAI_API_KEY` in `.env` and starts Uvicorn.

Frontend
- Chat: file attach (CSV/XLSX → local analytics; PDF doc Q&A is disabled in this build), streaming responses, tool‑aware planner.
- Tool result cards: PITI and Affordability cards with collapsible details, “Edit assumptions”, and inline recalc.
- Drag‑and‑drop: composer accepts files; shows chips with size and remove.
- Message UX: Copy/Quote/Regenerate actions on hover; timestamps; jump‑to‑latest pill; Shift+Enter newline.
- Budgets UI: set monthly targets; Dashboard shows Budgets vs Actual (avg monthly) table.
- Command palette: Ctrl/Cmd+K → New/Rename/Delete chat, Check LLM, Toggle model, Open Settings.
- Sidebar: thread menu (⋯) with Rename/Pin/Delete; pinned threads float to top.
- Theme: consistent purple→fuchsia gradient, zinc surfaces/borders, subtle glass + motion; tokens in `src/styles/index.css`.

Known Constraints
- `/api/parse` deliberately ignores PDFs; PDF document Q&A is not available in this build. OCR remains optional (`ENABLE_OCR=1`).
- No persistence beyond localStorage; zero server‑side storage of user data.

---

## Immediate Next (Roadmap)
- PDF JSON “Review & Import” flow: ask Gemini for strict JSON + citations; validate; user confirms to merge into analytics.
- Category rules UI: define contains/regex → category; recompute analytics with diffs; persist rules locally.
- Micro‑polish: icon set consolidation, tokenized buttons across views, skeletons on tool recalc.
