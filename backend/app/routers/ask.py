from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

from ..schemas.models import AskInput, AskResponse
from ..services.llm_client import (
    ask_llm,
    ask_llm_orchestrated,
    DEFAULT_MODEL,
    _post_chat,
    _extract_json,
    _run_tool,
    stream_compose,
    SYSTEM_PROMPT,
    llm_status as _llm_status,
)


router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(data: AskInput):
    # Quick provider health check for clearer errors
    st = _llm_status()
    if not st.get("ok"):
        msg = st.get("error") or "LLM not configured"
        return AskResponse(answer=f"LLM provider not ready: {msg}", model=st.get("model", DEFAULT_MODEL))
    # Try orchestrated advisor path first; fallback to plain chat
    analytics = data.analytics.model_dump() if getattr(data, "analytics", None) else {}
    model = data.model or DEFAULT_MODEL
    # Force to backend default model; UI string is advisory only
    
    resp = ask_llm_orchestrated(
        analytics=analytics, question=data.question, model=model
    )
    if not resp.get("answer") or "Unable to compose" in resp.get("answer", ""):
        resp = ask_llm(analytics=analytics, question=data.question, model=model)
    answer = resp.get("answer") or "LLM returned no content. Verify OPENAI_API_KEY, model name, and account limits."
    return AskResponse(answer=answer, model=resp.get("model", DEFAULT_MODEL))


@router.post("/ask/stream")
def ask_stream(data: AskInput):
    # Early health check for clearer UX
    st = _llm_status()
    if not st.get("ok"):
        def sse(event: dict):
            return f"data: {json.dumps(event, default=str)}\n\n".encode()
        def iter_err():
            yield sse({"type": "error", "message": f"LLM provider not ready: {st.get('error') or 'missing configuration'}"})
            yield sse({"type": "done"})
        return StreamingResponse(iter_err(), media_type="text/event-stream")
    # Plan tools (non-stream)
    model = data.model or DEFAULT_MODEL
    # Force to backend default model; UI string is advisory only
    analytics = data.analytics.model_dump() if getattr(data, "analytics", None) else {}
    question = data.question

    planner_system = (
        "You are a planner for a finance assistant. "
        "Decide which tools to call to answer the user's question precisely. "
        "Return ONLY a JSON object with keys: intent (string), tools (array of {name, params}), missing_inputs (array of strings). "
        "Supported tools and params: {\"mortgage_payment\":[\"principal\",\"house_price\",\"down_payment\",\"down_payment_percent\",\"annual_rate\",\"term_years\",\"monthly_taxes\",\"property_tax_rate_annual\",\"monthly_insurance\",\"insurance_rate_annual\",\"monthly_hoa\",\"monthly_pmi\",\"pmi_rate_annual\",\"ltv_pmi_threshold\"],\"affordability\":[\"monthly_income\",\"monthly_debt_payments\",\"annual_rate\",\"term_years\",\"down_payment\",\"down_payment_percent\",\"property_tax_rate_annual\",\"insurance_rate_annual\",\"monthly_hoa\",\"pmi_rate_annual\",\"ltv_pmi_threshold\",\"dti_front\",\"dti_back\"]}. "
        "If inputs are missing, list them in missing_inputs and keep tools empty."
    )
    plan_text = _post_chat(model, [
        {"role": "system", "content": planner_system},
        {"role": "user", "content": question},
        {"role": "user", "content": "Available analytics summary JSON:"},
        {"role": "user", "content": json.dumps(analytics, default=str)},
    ], timeout=60) or ""
    plan = _extract_json(plan_text) or {}

    tools_to_run = plan.get("tools") or []
    missing = plan.get("missing_inputs") or []
    results = {}
    for t in tools_to_run:
        name = t.get("name")
        params = t.get("params") or {}
        tool_name, out = _run_tool(name, params)
        results[tool_name] = out

    def sse_iter():
        def sse(event: dict):
            return f"data: {json.dumps(event, default=str)}\n\n".encode()

        # Send tools result first
        yield sse({"type": "tools", "results": results, "missing": missing})
        if missing and not results:
            # Ask for missing inputs as a simple message
            msg = "Please provide: " + ", ".join(missing)
            yield sse({"type": "message", "content": msg})
            yield sse({"type": "done"})
            return

        # Stream composition with error handling and fallback
        token_count = 0
        try:
            for chunk in stream_compose(analytics, question, results, model=model, timeout=60):
                if chunk:
                    token_count += len(chunk)
                    yield sse({"type": "token", "content": chunk})
        except Exception as e:
            # Try graceful fallback to non-stream completion
            try:
                compose_prompt = (
                    "Answer the user's question using ONLY the provided analytics and tool_results. "
                    "Numbers must come from tool_results or analytics; do not invent. "
                    "If appropriate, show assumptions clearly and suggest 1-2 scenarios.\n\n"
                    + "Analytics JSON:\n" + json.dumps(analytics, default=str) + "\n\n"
                    + "Tool results JSON:\n" + json.dumps(results, default=str) + "\n\n"
                    + "User question:\n" + question
                )
                content = _post_chat(model, [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": compose_prompt},
                ], timeout=60)
                if content:
                    yield sse({"type": "message", "content": content})
                else:
                    yield sse({"type": "error", "message": str(e)})
            except Exception as ee:
                yield sse({"type": "error", "message": f"{str(e)}; fallback failed: {str(ee)}"})
            finally:
                yield sse({"type": "done"})
            return

        # Fallback to non-stream if nothing was produced
        if token_count == 0:
            compose_prompt = (
                "Answer the user's question using ONLY the provided analytics and tool_results. "
                "Numbers must come from tool_results or analytics; do not invent. "
                "If appropriate, show assumptions clearly and suggest 1-2 scenarios.\n\n"
                + "Analytics JSON:\n" + json.dumps(analytics, default=str) + "\n\n"
                + "Tool results JSON:\n" + json.dumps(results, default=str) + "\n\n"
                + "User question:\n" + question
            )
            content = _post_chat(model, [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": compose_prompt},
            ], timeout=60)
            if content:
                yield sse({"type": "message", "content": content})
            else:
                yield sse({"type": "error", "message": "LLM returned no content. Verify OPENAI_API_KEY, model name, and billing status."})

        yield sse({"type": "done"})

    return StreamingResponse(sse_iter(), media_type="text/event-stream")


# Document Q&A endpoint removed in OpenAI-only build
