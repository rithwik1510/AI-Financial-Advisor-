from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional, Literal, Any, Dict

from pydantic import BaseModel, field_validator


class Transaction(BaseModel):
    date: Optional[datetime]
    description: Optional[str]
    amount: float
    currency: Optional[str] = None
    category: Optional[str] = None
    account: Optional[str] = None
    source: Optional[str] = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, (datetime, date)):
            return datetime.fromtimestamp(v.timestamp()) if isinstance(v, datetime) else datetime.combine(v, datetime.min.time())
        if v is None:
            return None
        # Try common formats
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(v), fmt)
            except Exception:
                pass
        try:
            # last resort
            return datetime.fromisoformat(str(v))
        except Exception:
            return None


class ParseResponse(BaseModel):
    transactions: List[Transaction]
    files: List[str]
    notes: Optional[str] = None
    # Optional data quality surface for gating and UX
    dq_score: Optional[float] = None
    dq: Optional[dict] = None
    warnings: Optional[List[str]] = None


class AnalyzeInput(BaseModel):
    transactions: List[Transaction]
    liquid_savings: Optional[float] = None
    monthly_debt_payments: Optional[float] = None
    # Optional enhancements
    budgets: Optional[Dict[str, float]] = None  # monthly targets per category (USD, positive numbers)
    category_rules: Optional[List[Dict[str, str]]] = None  # [{match_type:'contains'|'regex', pattern:'', category:''}]


class MonthlyRow(BaseModel):
    month: str
    income: float
    expenses: float
    net: float
    tx_count: int


class CategoryRow(BaseModel):
    category: str
    amount: float


class MerchantRow(BaseModel):
    description: Optional[str]
    total_spend: float
    total_inflow: float
    tx_count: int


class AnalyzeResult(BaseModel):
    summary: Dict[str, Any]
    monthly: List[MonthlyRow]
    by_category: List[CategoryRow]
    by_merchant: List[MerchantRow]
    savings_rate: float
    dti: Optional[float] = None
    emergency_fund_months: Optional[float] = None
    discretionary_share: Optional[float] = None
    health_score: Optional[float] = None
    insights: List[str] = []
    anomalies: List[Dict[str, Any]] = []
    recurring: List[Dict[str, Any]] = []
    # Optional add-ons
    budget_variance: Optional[List[Dict[str, Any]]] = None


class AskInput(BaseModel):
    analytics: Optional[AnalyzeResult] = None
    question: str
    model: Optional[str] = None  # defaults in service


class AskResponse(BaseModel):
    answer: str
    model: str


# ---- Tools: Mortgage Payment / Affordability ----

class MortgagePaymentInput(BaseModel):
    # Either provide principal, or house_price with a down payment (absolute or percent)
    principal: Optional[float] = None
    house_price: Optional[float] = None
    down_payment: Optional[float] = None
    down_payment_percent: Optional[float] = None  # 0..1

    annual_rate: float  # e.g. 0.065 for 6.5%
    term_years: int = 30

    # Taxes/insurance: either monthly, or annual rate against price
    monthly_taxes: Optional[float] = None
    property_tax_rate_annual: Optional[float] = None  # e.g. 0.0125 (1.25%)
    monthly_insurance: Optional[float] = None
    insurance_rate_annual: Optional[float] = None  # e.g. 0.003 (0.3%)
    monthly_hoa: Optional[float] = 0.0

    # PMI: monthly or computed from annual rate if LTV above threshold
    monthly_pmi: Optional[float] = None
    pmi_rate_annual: Optional[float] = None  # e.g. 0.006 (0.6%)
    ltv_pmi_threshold: Optional[float] = 0.80


class MortgagePaymentResult(BaseModel):
    house_price: Optional[float] = None
    down_payment: Optional[float] = None
    principal: float
    annual_rate: float
    term_months: int
    monthly_pi: float
    monthly_taxes: float
    monthly_insurance: float
    monthly_hoa: float
    monthly_pmi: float
    monthly_piti: float


class AffordabilityInput(BaseModel):
    monthly_income: float
    monthly_debt_payments: float
    annual_rate: float
    term_years: int = 30

    # Assumptions (defaults used if not provided)
    down_payment: Optional[float] = None
    down_payment_percent: Optional[float] = None  # 0..1; default 0.20

    property_tax_rate_annual: Optional[float] = None  # default 0.0125
    insurance_rate_annual: Optional[float] = None  # default 0.003
    monthly_hoa: Optional[float] = 0.0
    pmi_rate_annual: Optional[float] = None  # default 0.006
    ltv_pmi_threshold: Optional[float] = 0.80

    # DTI thresholds
    dti_front: Optional[float] = 0.28
    dti_back: Optional[float] = 0.36


class AffordabilityResult(BaseModel):
    max_price: float
    binding_constraint: str  # 'front' or 'back'
    piti_at_max: float
    breakdown: dict
    assumptions: dict
