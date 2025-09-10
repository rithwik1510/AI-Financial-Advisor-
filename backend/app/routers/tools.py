from __future__ import annotations

from fastapi import APIRouter

from ..schemas.models import (
    MortgagePaymentInput,
    MortgagePaymentResult,
    AffordabilityInput,
    AffordabilityResult,
)
from ..services.tools import mortgage_payment, affordability


router = APIRouter()


@router.post("/mortgage_payment", response_model=MortgagePaymentResult)
def calc_mortgage_payment(data: MortgagePaymentInput):
    result = mortgage_payment(data.model_dump())
    return result


@router.post("/affordability", response_model=AffordabilityResult)
def calc_affordability(data: AffordabilityInput):
    result = affordability(data.model_dump())
    return result

