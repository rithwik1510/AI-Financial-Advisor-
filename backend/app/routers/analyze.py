from __future__ import annotations

from fastapi import APIRouter

from ..schemas.models import AnalyzeInput, AnalyzeResult
from ..services.analytics import compute_analytics


router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResult)
def analyze(data: AnalyzeInput):
    result = compute_analytics(
        transactions=[t.model_dump() for t in data.transactions],
        liquid_savings=data.liquid_savings,
        monthly_debt_payments=data.monthly_debt_payments,
        budgets=data.budgets,
        category_rules=data.category_rules,
    )
    return result
