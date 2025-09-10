Backend (FastAPI)

Local-first API that parses PDF/CSV statements, normalizes and analyzes transactions, computes a financial health score, and generates advice via a hosted LLM (OpenAI-compatible).

Endpoints

- POST /api/parse â€” multipart PDF/CSV â†’ normalized transactions
- POST /api/analyze â€” transactions â†’ analytics, savings rate, DTI, health score
- POST /api/ask â€” analytics + question â†’ advice via OpenAI-compatible API
- GET /api/health â€” readiness check

Run (dev)

1) Create a venv and install deps:
   - python -m venv .venv
   - .venv\\Scripts\\Activate (Windows) or source .venv/bin/activate (macOS/Linux)
   - pip install -r requirements.txt

2) Start the API
   - uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

3) Configure LLM provider (OpenAI-compatible)
   - Set environment variable `OPENAI_API_KEY` to your API key.
   - Optional: set `OPENAI_BASE_URL` (default `https://api.openai.com/v1`) and `OPENAI_MODEL` (default `gpt-4o-mini`).

Document Q&A\r\n- PDF document Q&A is not available in this build. For accurate analytics and advice, attach CSV/XLSX exports or paste text excerpts.
