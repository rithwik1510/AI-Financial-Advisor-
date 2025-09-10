from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional, Tuple, List, Iterable

import requests
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    load_dotenv(find_dotenv())
except Exception:
    pass

from .tools import mortgage_payment, affordability


# Provider: OpenAI-compatible chat completions (OpenAI, Groq, Together, Fireworks, OpenRouter, Azure OpenAI)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DEFAULT_MODEL = OPENAI_MODEL


SYSTEM_PROMPT = (
    "You are a privacy-first financial coach. Be supportive, non-judgmental, and clear. "
    "Explain concepts simply. Use exact dollars and percentages when helpful. "
    "Never claim to access external data; all data is provided by the user locally. "
    "Remind users their data never leaves their system when appropriate."
)


def _openai_generate(messages: List[Dict[str, str]], model: Optional[str], stream: bool = False, timeout: int = 60) -> Iterable[str] | str | None:
    """Call OpenAI-compatible chat.completions endpoint and optionally simulate streaming."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    model = model or OPENAI_MODEL

    # Map messages to OpenAI format
    oai_msgs: List[Dict[str, Any]] = []
    system_texts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    if system_texts:
        oai_msgs.append({"role": "system", "content": "\n\n".join(system_texts)})
    for m in messages:
        role = m.get("role")
        if role in ("user", "assistant"):
            oai_msgs.append({"role": ("assistant" if role == "assistant" else "user"), "content": m.get("content", "")})

    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": model,
        "messages": oai_msgs,
        "temperature": 0.2,
        "stream": False,  # simulate streaming consistently
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=(10, timeout))
    except Exception:
        return None
    if not r.ok:
        return None
    try:
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        # Try standard Chat Completions content
        content = (choice.get("message") or {}).get("content")
        # Fallbacks for some "compatible" providers
        if not content:
            # Some return plain text in `text`
            content = choice.get("text") or None
        if not content:
            # Some wrap output text elsewhere
            content = data.get("output_text") or None
    except Exception:
        content = None
    if not stream:
        return content
    def gen() -> Iterable[str]:
        if not content:
            return
        chunk = 160
        for i in range(0, len(content), chunk):
            yield content[i:i+chunk]
    return gen()


def chat_probe(model: Optional[str] = None, timeout: int = 12) -> Dict[str, Any]:
    """Perform a minimal chat completion and return raw status + excerpt for debugging."""
    if not OPENAI_API_KEY:
        return {"ok": False, "status": None, "error": "OPENAI_API_KEY not set"}
    model = model or OPENAI_MODEL
    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0.0,
        "stream": False,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=(10, timeout))
        excerpt = r.text[:2000]
        if not r.ok:
            return {"ok": False, "status": r.status_code, "error": excerpt}
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "status": r.status_code, "error": excerpt}
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or choice.get("text") or data.get("output_text")
        return {"ok": True, "status": r.status_code, "content": content, "finish_reason": (choice.get("finish_reason") if isinstance(choice, dict) else None)}
    except Exception as e:
        return {"ok": False, "status": None, "error": str(e)}


def _post_chat(model: str, messages: List[Dict[str, str]], timeout: int) -> Optional[str]:
    out = _openai_generate(messages, model=model, stream=False, timeout=timeout)
    return out if isinstance(out, str) else None


def llm_status(timeout: int = 8) -> Dict[str, Any]:
    """Lightweight health check for the configured LLM provider with error details."""
    model = DEFAULT_MODEL
    if not OPENAI_API_KEY or str(OPENAI_API_KEY).strip() == "":
        return {"ok": False, "provider": LLM_PROVIDER, "model": model, "error": "OPENAI_API_KEY not set"}
    try:
        r = requests.get(f"{OPENAI_BASE_URL}/models", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, timeout=(5, timeout))
        if r.ok:
            return {"ok": True, "provider": LLM_PROVIDER, "model": model, "error": None}
        return {"ok": False, "provider": LLM_PROVIDER, "model": model, "error": f"HTTP {r.status_code}: {r.text}"}
    except Exception as e:
        return {"ok": False, "provider": LLM_PROVIDER, "model": model, "error": str(e)}


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = "\n".join([line for line in t.splitlines() if not line.strip().startswith("```")])
    try:
        return json.loads(t)
    except Exception:
        pass
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        blob = t[start : end + 1]
        try:
            return json.loads(blob)
        except Exception:
            return None
    return None


def _run_tool(name: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    try:
        if name == "mortgage_payment":
            return name, mortgage_payment(params)
        if name == "affordability":
            return name, affordability(params)
    except Exception as e:
        return name, {"error": str(e)}
    return name, {"error": "unknown tool"}


TOOLS_SPEC = {
    "mortgage_payment": {
        "desc": "Compute monthly mortgage PI and PITI given principal or price + down payment.",
        "params": [
            "principal", "house_price", "down_payment", "down_payment_percent",
            "annual_rate", "term_years", "monthly_taxes", "property_tax_rate_annual",
            "monthly_insurance", "insurance_rate_annual", "monthly_hoa",
            "monthly_pmi", "pmi_rate_annual", "ltv_pmi_threshold",
        ],
    },
    "affordability": {
        "desc": "Max home price under 28/36 DTI caps with PITI breakdown.",
        "params": [
            "monthly_income", "monthly_debt_payments", "annual_rate", "term_years",
            "down_payment", "down_payment_percent", "property_tax_rate_annual",
            "insurance_rate_annual", "monthly_hoa", "pmi_rate_annual", "ltv_pmi_threshold",
            "dti_front", "dti_back",
        ],
    },
}


def ask_llm(analytics: Dict[str, Any], question: str, model: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Here is a JSON summary of my finances."},
        {"role": "user", "content": json.dumps(analytics, default=str)},
        {"role": "user", "content": question},
    ]
    content = _post_chat(model, messages, timeout) or ""
    return {"answer": content, "model": model}


def ask_llm_orchestrated(analytics: Dict[str, Any], question: str, model: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL
    planner_system = (
        "You are a planner for a finance assistant. "
        "Decide which tools to call to answer the user's question precisely. "
        "Return ONLY a JSON object with keys: intent (string), tools (array of {name, params}), missing_inputs (array of strings). "
        "Supported tools and params: " + json.dumps({k: v["params"] for k, v in TOOLS_SPEC.items()}) + ". "
        "If inputs are missing, list them in missing_inputs and keep tools empty."
    )
    plan_messages = [
        {"role": "system", "content": planner_system},
        {"role": "user", "content": question},
        {"role": "user", "content": "Available analytics summary JSON:"},
        {"role": "user", "content": json.dumps(analytics, default=str)},
    ]
    plan_text = _post_chat(model, plan_messages, timeout) or ""
    plan = _extract_json(plan_text) or {}

    tools_to_run = plan.get("tools") or []
    missing = plan.get("missing_inputs") or []

    results: Dict[str, Any] = {}
    for t in tools_to_run:
        name = t.get("name")
        if name not in TOOLS_SPEC:
            continue
        params = t.get("params") or {}
        tool_name, out = _run_tool(name, params)
        results[tool_name] = out

    if missing and not results:
        ask_missing = (
            "Ask the user for the following missing inputs and explain why they matter: "
            + ", ".join(missing)
        )
        compose_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ask_missing},
        ]
        content = _post_chat(model, compose_messages, timeout) or ("Please provide: " + ", ".join(missing))
        return {"answer": content, "model": model}

    compose_prompt = (
        "Answer the user's question using ONLY the provided analytics and tool_results. "
        "Numbers must come from tool_results or analytics; do not invent. "
        "If appropriate, show assumptions clearly and suggest 1-2 scenarios.\n\n"
        + "Analytics JSON:\n" + json.dumps(analytics, default=str) + "\n\n"
        + "Tool results JSON:\n" + json.dumps(results, default=str) + "\n\n"
        + "User question:\n" + question
    )
    compose_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": compose_prompt},
    ]
    content = _post_chat(model, compose_messages, timeout)
    if content:
        return {"answer": content, "model": model}
    return {"answer": "Unable to compose an answer.", "model": model}


def ask_llm_with_files(files: List[Tuple[bytes, str]], question: str, model: Optional[str] = None, timeout: int = 90) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL
    # Not supported with the OpenAI Chat Completions path in this build
    return {"answer": "", "model": model, "error": "Document Q&A is not available with the current LLM provider. Attach CSV/XLSX or paste text."}


def stream_compose(analytics: Dict[str, Any], question: str, tool_results: Dict[str, Any], model: Optional[str] = None, timeout: int = 60) -> Iterable[str]:
    model = model or DEFAULT_MODEL
    prompt = (
        "Answer the user's question using ONLY the provided analytics and tool_results. "
        "Numbers must come from tool_results or analytics; do not invent. "
        "If appropriate, show assumptions clearly and suggest 1-2 scenarios.\n\n"
        + "Analytics JSON:\n" + json.dumps(analytics, default=str) + "\n\n"
        + "Tool results JSON:\n" + json.dumps(tool_results, default=str) + "\n\n"
        + "User question:\n" + question
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    gen = _openai_generate(messages, model=model, stream=True, timeout=timeout)
    if isinstance(gen, str) or gen is None:
        return iter(())
    return gen
