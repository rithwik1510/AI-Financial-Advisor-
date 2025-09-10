from __future__ import annotations

from typing import List, Dict, Any, Optional

try:
    import pulp  # type: ignore
    HAS_PULP = True
except Exception:
    HAS_PULP = False

from ..schemas.models import Transaction


NEG_HINTS = (
    "payment",
    "debit",
    "withdrawal",
    "charge",
    "purchase",
    "fee",
)
POS_HINTS = (
    "deposit",
    "credit",
    "refund",
    "rebate",
    "interest",
)


def _hint_sign(desc: Optional[str], original: float) -> int:
    d = (desc or "").lower()
    if any(w in d for w in NEG_HINTS):
        return -1
    if any(w in d for w in POS_HINTS):
        return 1
    # default to original sign if present, else negative for outflow bias
    if original != 0:
        return -1 if original < 0 else 1
    return -1


def reconcile_signs_ilp(transactions: List[Transaction], meta: Dict[str, Any]) -> Dict[str, Any]:
    """Choose signs for amounts to best match expected delta using ILP.

    Returns dict with keys: corrected (List[Transaction]), diff, expected, sum, solver, status.
    If ILP unavailable, returns heuristic correction.
    """
    opening = meta.get("opening_balance")
    closing = meta.get("closing_balance")
    t_dep = meta.get("total_deposits")
    t_wdr = meta.get("total_withdrawals")

    expected: Optional[float] = None
    if opening is not None and closing is not None:
        try:
            expected = float(closing) - float(opening)
        except Exception:
            expected = None
    if expected is None and (t_dep is not None or t_wdr is not None):
        try:
            expected = float(t_dep or 0.0) + float(t_wdr or 0.0)
        except Exception:
            expected = None

    if expected is None:
        return {
            "corrected": transactions,
            "expected": None,
            "sum": sum(float(t.amount) for t in transactions),
            "diff": None,
            "solver": None,
            "status": "no_expected",
        }

    abs_vals = [abs(float(t.amount)) for t in transactions]
    hints = [_hint_sign(t.description, float(t.amount)) for t in transactions]

    # If pulp is not available, heuristic: keep original signs, but if far off, flip smallest set with weakest hints
    if not HAS_PULP or len(transactions) == 0:
        signed = [hints[i] * abs_vals[i] for i in range(len(abs_vals))]
        total = sum(signed)
        return {
            "corrected": [Transaction(**{**t.model_dump(), "amount": signed[i]}) for i, t in enumerate(transactions)],
            "expected": expected,
            "sum": total,
            "diff": abs(total - expected),
            "solver": "heuristic",
            "status": "ok",
        }

    # ILP model
    prob = pulp.LpProblem("sign_reconcile", pulp.LpMinimize)
    # z_i in {0,1}; x_i = 2*z_i - 1 => -1 or +1
    z_vars = [pulp.LpVariable(f"z_{i}", lowBound=0, upBound=1, cat=pulp.LpBinary) for i in range(len(abs_vals))]
    # absolute deviation via positive slack variables
    d_pos = pulp.LpVariable("d_pos", lowBound=0)
    d_neg = pulp.LpVariable("d_neg", lowBound=0)

    # Sum expression S = sum_i (2*z_i - 1) * a_i
    S = pulp.lpSum([(2 * z_vars[i] - 1) * abs_vals[i] for i in range(len(abs_vals))])
    prob += S - expected == d_pos - d_neg

    # Flip penalty: prefer matching hint
    # If hint is -1: cost when z_i = 1 (x_i=+1), so cost term is z_i
    # If hint is +1: cost when z_i = 0 (x_i=-1), so cost term is (1 - z_i)
    LAMBDA = 0.01  # small weight compared to currency units
    flip_cost_terms = []
    for i, h in enumerate(hints):
        if h < 0:
            flip_cost_terms.append(z_vars[i])
        else:
            flip_cost_terms.append(1 - z_vars[i])

    prob += d_pos + d_neg + LAMBDA * pulp.lpSum(flip_cost_terms)

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))

    z_vals = [int(pulp.value(z)) for z in z_vars]
    signed = [((2 * z_vals[i]) - 1) * abs_vals[i] for i in range(len(abs_vals))]
    total = sum(signed)

    corrected = [Transaction(**{**t.model_dump(), "amount": signed[i]}) for i, t in enumerate(transactions)]

    return {
        "corrected": corrected,
        "expected": expected,
        "sum": total,
        "diff": abs(total - expected),
        "solver": "pulp",
        "status": str(pulp.LpStatus[status]) if hasattr(pulp, "LpStatus") else str(status),
    }

