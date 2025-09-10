<div align="center">

# 💸 AI Financial Advisor (Local‑First + OpenAI)

Understand your money, privately. Upload CSV/XLSX statements, get clear analytics and a financial health score, and chat with an AI coach powered by an OpenAI‑compatible API. Your files stay on your machine — only a summarized analytics JSON and your question are sent to the LLM.

</div>

## ✨ Features

- 🔐 Local parsing & analytics (CSV/XLSX) — no server‑side storage
- 📊 Insights: savings rate, DTI, emergency months, discretionary share, anomalies, recurring detection, health score
- 🧮 Tools: Mortgage Payment (PITI) & Affordability calculators with assumptions
- 💬 Chat: streaming answers using your analytics + tools (OpenAI Chat Completions)
- 🧩 Budgets: optional monthly targets and variance table
- ⚡ FastAPI backend + React (Vite + Tailwind) frontend

> Note: PDF document Q&A is disabled in this build. For best results, attach CSV/XLSX exports.

## 🧭 Project Layout

- `backend/` — FastAPI API (parse, analyze, ask, tools)
- `frontend/` — React + Tailwind UI (uploader, dashboard, chat)
- `analyze_financial_data.py` — standalone local CLI analyzer (optional)

## 🚀 Quick Start

Backend (Windows PowerShell)
- `backend/run_dev.ps1` → creates venv, installs deps, prompts for `OPENAI_API_KEY`, starts Uvicorn at http://localhost:8000

Backend (manual)
```
cd backend
python -m venv .venv
.venv\Scripts\activate  # or: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

LLM Config (OpenAI‑compatible)
- Required: `OPENAI_API_KEY`
- Optional: `OPENAI_BASE_URL` (default `https://api.openai.com/v1`), `OPENAI_MODEL` (default `gpt-4o-mini`)
- Health checks:
  - `GET /api/health` → `{ status: "ok" }`
  - `GET /api/llm/status` → provider readiness
  - `GET /api/llm/ping` → tiny chat probe (useful for quota/model errors)

Frontend (dev)
```
cd frontend
npm install
npm run dev   # http://localhost:5173
```

## 🛠️ API Endpoints (high‑level)

- `POST /api/parse` — multipart CSV/XLSX → normalized transactions (PDF ignored)
- `POST /api/analyze` — transactions → analytics + health metrics (+ optional budgets)
- `POST /api/ask` — analytics + question → LLM answer (OpenAI Chat Completions)
- `POST /api/ask/stream` — SSE streaming composition with tools
- `POST /api/tools/{mortgage_payment, affordability}` — calculators
- `GET /api/llm/status` — provider config check
- `GET /api/llm/ping` — minimal completion probe

## 🔒 Privacy

- Parsing and analytics run locally.
- Only the analytics JSON + your question are sent to the LLM.
- No server‑side persistence; the UI uses localStorage for convenience only.

## 📦 CLI Analyzer

```
python analyze_financial_data.py --input <folder> --output analysis.json
```

## 🌐 Deploy (Showcase)

Frontend (GitHub Pages) — build and publish `frontend/dist` to `gh-pages` (or Netlify/Vercel). The UI expects the API at the same origin; for Pages, set a public API URL and configure axios base URL (or host the backend on Render/Railway and enable CORS for your Pages domain).

Backend (Render/Railway/FlyIO)
- Deploy `backend/` as a Python service (start: `uvicorn app.main:app --host 0.0.0.0 --port 8000`)
- Set env: `OPENAI_API_KEY`, optionally `OPENAI_MODEL`
- Add CORS origin for your frontend domain in `app/main.py` if needed

## 🧑‍💻 Tech Stack

- Backend: FastAPI, Pydantic v2, Pandas, Requests
- Frontend: React, Vite, Tailwind
- LLM: OpenAI‑compatible Chat Completions

---

If you use this for a portfolio/demo, consider adding a brief video or screenshots of:
- Upload → Parse → Analyze dashboard
- Tool result cards (PITI/Affordability)
- Chat answering a question using the analytics

Made with care for privacy and clarity. ✨

