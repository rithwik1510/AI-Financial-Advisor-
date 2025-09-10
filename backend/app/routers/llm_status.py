from __future__ import annotations

from fastapi import APIRouter

from ..services.llm_client import llm_status, chat_probe


router = APIRouter()


@router.get("/llm/status")
def status():
    return llm_status()


@router.get("/llm/ping")
def ping():
    """Perform a minimal chat completion to surface provider response details."""
    return chat_probe()
