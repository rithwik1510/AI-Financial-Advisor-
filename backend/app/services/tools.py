from __future__ import annotations

from typing import Optional, Dict, Any

import math


def _monthly_pi(principal: float, annual_rate: float, term_years: int) -> float:
    n = max(int(term_years * 12), 1)
    r = max(annual_rate, 0.0) / 12.0
    if r <= 0:
        return principal / n
    a = math.pow(1 + r, n)
    return principal * (r * a) / (a - 1)


def _normalize_down_payment(house_price: Optional[float], down_payment: Optional[float], down_payment_percent: Optional[float]) -> (Optional[float], Optional[float]):
    if house_price is None:
        return down_payment, down_payment_percent
    # Prefer absolute if provided, else derive from percent
    if down_payment is not None:
        dpp = down_payment / house_price if house_price > 0 else None
        return down_payment, dpp
    if down_payment_percent is not None:
        return house_price * down_payment_percent, down_payment_percent
    return None, None


def mortgage_payment(params: Dict[str, Any]) -> Dict[str, Any]:
    house_price = params.get("house_price")
    principal = params.get("principal")
    annual_rate = float(params["annual_rate"])  # required
    term_years = int(params.get("term_years", 30))

    dp_abs, dp_pct = _normalize_down_payment(house_price, params.get("down_payment"), params.get("down_payment_percent"))

    if principal is None:
        if house_price is None:
            raise ValueError("Provide either principal or house_price with a down payment")
        # assume 20% DP if neither is provided
        if dp_abs is None and dp_pct is None:
            dp_pct = 0.20
            dp_abs = house_price * dp_pct
        principal = max(house_price - (dp_abs or 0.0), 0.0)

    # Taxes
    monthly_taxes = params.get("monthly_taxes")
    if monthly_taxes is None and house_price is not None:
        tax_rate_raw = params.get("property_tax_rate_annual")
        tax_rate = 0.0125 if tax_rate_raw is None else float(tax_rate_raw)
        monthly_taxes = tax_rate * float(house_price) / 12.0
    monthly_taxes = float(monthly_taxes or 0.0)

    # Insurance
    monthly_insurance = params.get("monthly_insurance")
    if monthly_insurance is None and house_price is not None:
        ins_rate_raw = params.get("insurance_rate_annual")
        ins_rate = 0.003 if ins_rate_raw is None else float(ins_rate_raw)
        monthly_insurance = ins_rate * float(house_price) / 12.0
    monthly_insurance = float(monthly_insurance or 0.0)

    # HOA
    monthly_hoa = float(params.get("monthly_hoa", 0.0) or 0.0)

    # PMI
    monthly_pmi = params.get("monthly_pmi")
    if monthly_pmi is None:
        pmi_rate_raw = params.get("pmi_rate_annual")
        pmi_rate = 0.006 if pmi_rate_raw is None else float(pmi_rate_raw)  # 0.6% default if needed
        ltv_thr_raw = params.get("ltv_pmi_threshold")
        ltv_threshold = 0.80 if ltv_thr_raw is None else float(ltv_thr_raw)
        if house_price and principal and house_price > 0:
            ltv = principal / house_price
            if ltv > ltv_threshold:
                monthly_pmi = float(pmi_rate) * principal / 12.0
            else:
                monthly_pmi = 0.0
        else:
            monthly_pmi = 0.0
    monthly_pmi = float(monthly_pmi or 0.0)

    monthly_pi = _monthly_pi(float(principal), annual_rate, term_years)
    piti = monthly_pi + monthly_taxes + monthly_insurance + monthly_hoa + monthly_pmi

    return {
        "house_price": house_price,
        "down_payment": dp_abs,
        "principal": float(principal),
        "annual_rate": annual_rate,
        "term_months": int(term_years * 12),
        "monthly_pi": round(monthly_pi, 2),
        "monthly_taxes": round(monthly_taxes, 2),
        "monthly_insurance": round(monthly_insurance, 2),
        "monthly_hoa": round(monthly_hoa, 2),
        "monthly_pmi": round(monthly_pmi, 2),
        "monthly_piti": round(piti, 2),
    }


def affordability(params: Dict[str, Any]) -> Dict[str, Any]:
    income = float(params["monthly_income"])  # required
    debts = float(params["monthly_debt_payments"])  # required
    rate = float(params["annual_rate"])  # required
    term = int(params.get("term_years", 30))

    # Defaults
    dti_front = float(params.get("dti_front", 0.28))
    dti_back = float(params.get("dti_back", 0.36))
    default_dp_pct = 0.20 if params.get("down_payment_percent") is None and params.get("down_payment") is None else None

    tax_rate = float(0.0125 if params.get("property_tax_rate_annual") is None else params.get("property_tax_rate_annual"))
    ins_rate = float(0.003 if params.get("insurance_rate_annual") is None else params.get("insurance_rate_annual"))
    hoa = float(params.get("monthly_hoa", 0.0) or 0.0)
    pmi_rate = float(0.006 if params.get("pmi_rate_annual") is None else params.get("pmi_rate_annual"))
    ltv_threshold = float(0.80 if params.get("ltv_pmi_threshold") is None else params.get("ltv_pmi_threshold"))

    # PITI caps from DTI
    front_cap = dti_front * income
    back_cap = dti_back * income - debts
    piti_cap = min(front_cap, back_cap)
    binding = "front" if front_cap <= back_cap else "back"
    if piti_cap <= 0:
        return {
            "max_price": 0.0,
            "binding_constraint": binding,
            "piti_at_max": 0.0,
            "breakdown": {"pi": 0.0, "taxes": 0.0, "insurance": 0.0, "hoa": hoa, "pmi": 0.0},
            "assumptions": {
                "annual_rate": rate,
                "term_years": term,
                "dti_front": dti_front,
                "dti_back": dti_back,
                "property_tax_rate_annual": tax_rate,
                "insurance_rate_annual": ins_rate,
                "monthly_hoa": hoa,
                "pmi_rate_annual": pmi_rate,
                "ltv_pmi_threshold": ltv_threshold,
            },
        }

    # Binary search for price X such that PITI(X) ~ piti_cap
    def piti_for_price(x: float) -> (float, Dict[str, float]):
        # Determine down payment
        dp_abs = params.get("down_payment")
        dp_pct = params.get("down_payment_percent", default_dp_pct)
        if dp_abs is None and dp_pct is not None:
            dp_abs = x * float(dp_pct)
        if dp_abs is not None and dp_abs > x:
            dp_abs = x
        principal = x - (dp_abs or 0.0)
        pi = _monthly_pi(principal, rate, term)
        taxes = tax_rate * x / 12.0
        ins = ins_rate * x / 12.0
        ltv = principal / x if x > 0 else 0.0
        pmi = (pmi_rate * principal / 12.0) if ltv > ltv_threshold else 0.0
        piti_val = pi + taxes + ins + hoa + pmi
        return piti_val, {"pi": pi, "taxes": taxes, "insurance": ins, "hoa": hoa, "pmi": pmi}

    lo, hi = 0.0, 1000000.0
    # Grow hi until we exceed cap or reach a max
    for _ in range(24):
        val, _ = piti_for_price(hi)
        if val >= piti_cap:
            break
        hi *= 1.5
        if hi > 10000000.0:
            break

    # Binary search
    for _ in range(64):
        mid = (lo + hi) / 2.0
        val, _ = piti_for_price(mid)
        if val > piti_cap:
            hi = mid
        else:
            lo = mid
    max_price = lo
    piti_val, brk = piti_for_price(max_price)

    return {
        "max_price": round(max_price, 0),
        "binding_constraint": binding,
        "piti_at_max": round(piti_val, 2),
        "breakdown": {k: round(v, 2) for k, v in brk.items()},
        "assumptions": {
            "annual_rate": rate,
            "term_years": term,
            "dti_front": dti_front,
            "dti_back": dti_back,
            "property_tax_rate_annual": tax_rate,
            "insurance_rate_annual": ins_rate,
            "monthly_hoa": hoa,
            "pmi_rate_annual": pmi_rate,
            "ltv_pmi_threshold": ltv_threshold,
            "down_payment": params.get("down_payment"),
            "down_payment_percent": params.get("down_payment_percent", default_dp_pct),
        },
    }
