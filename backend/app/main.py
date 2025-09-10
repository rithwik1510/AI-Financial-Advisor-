from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import parse, analyze, ask
from .routers import tools
from .routers import templates_api
from .routers import llm_status


def create_app() -> FastAPI:
    app = FastAPI(title="AI Financial Advisor (Local)", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(parse.router, prefix="/api", tags=["parse"])
    app.include_router(analyze.router, prefix="/api", tags=["analyze"])
    app.include_router(ask.router, prefix="/api", tags=["ask"])
    app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
    app.include_router(llm_status.router, prefix="/api", tags=["llm"])
    app.include_router(templates_api.router, prefix="/api", tags=["templates"])

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
