from __future__ import annotations

from typing import List, Dict, Any, Optional
from math import isfinite

from ..schemas.models import Transaction


def _safe_float(x: Any) -> Optional[float]:
    try:
        f = float(x)
        return f if isfinite(f) else None
    except Exception:
        return None


def compute_data_quality(
    transactions: List[Transaction],
    meta: Optional[Dict[str, Any]] = None,
    provenance_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Compute a 0..100 DQ score and diagnostics.

    Components:
    - Volume: some rows present.
    - Dates: fraction of rows with valid dates.
    - Reconciliation: delta vs opening/closing or totals if available.
    - Duplicates: share of exact dup triplets.
    - Consensus: share supported by multiple strategies (if counts provided).
    """
    n = len(transactions)
    issues: List[str] = []
    if n == 0:
        return {"score": 0.0, "issues": ["No transactions parsed"], "metrics": {}}

    # Dates
    with_dates = sum(1 for t in transactions if getattr(t, "date", None) is not None)
    frac_dates = with_dates / max(1, n)

    # Duplicates (exact triplet duplicates)
    seen = set()
    dups = 0
    for t in transactions:
        key = (
            t.date.isoformat() if t.date else None,
            (t.description or "").strip().lower(),
            round(float(t.amount), 2),
        )
        if key in seen:
            dups += 1
        else:
            seen.add(key)
    dup_rate = dups / max(1, n)

    # Reconciliation
    recon_score = None
    recon_diff = None
    if meta:
        opening = _safe_float(meta.get("opening_balance"))
        closing = _safe_float(meta.get("closing_balance"))
        t_dep = _safe_float(meta.get("total_deposits"))
        t_wdr = _safe_float(meta.get("total_withdrawals"))
        s = sum(float(t.amount) for t in transactions)
        if opening is not None and closing is not None:
            expected = closing - opening
            recon_diff = abs(s - expected)
            denom = max(1.0, abs(expected))
            recon_score = max(0.0, 1.0 - (recon_diff / denom))  # 0..1
        elif t_dep is not None or t_wdr is not None:
            expected = (t_dep or 0.0) + (t_wdr or 0.0)
            recon_diff = abs(s - expected)
            denom = max(1.0, abs(expected))
            recon_score = max(0.0, 1.0 - (recon_diff / denom))

    # Consensus support (if available)
    consensus_frac = None
    if provenance_counts and n > 0:
        votes = 0
        for k, cnt in provenance_counts.items():
            # Give partial credit but cap by number of transactions
            votes += min(cnt, n)
        # Assume up to 3 effective strategies, normalize roughly
        consensus_frac = min(1.0, votes / (3 * max(1, n)))

    # Score weighting
    score = 0.0
    # Base presence
    score += 15.0 if n > 0 else 0.0
    # Dates
    score += 20.0 * frac_dates
    # Deduct for dups
    score += 10.0 * max(0.0, 1.0 - min(1.0, dup_rate * 5))  # heavy penalty if many dups
    # Reconciliation (if any)
    if recon_score is not None:
        score += 40.0 * recon_score
    else:
        issues.append("No balances/totals found; reconciliation skipped")
        score += 15.0  # partial credit if other components are fine
    # Consensus
    if consensus_frac is not None:
        score += 15.0 * consensus_frac

    score = max(0.0, min(100.0, score))

    # Issues
    if frac_dates < 0.6:
        issues.append("Low date coverage")
    if dup_rate > 0.05:
        issues.append("Possible duplicate rows detected")
    if recon_score is not None and recon_score < 0.8:
        issues.append("Transactions do not reconcile with balances/totals")

    metrics = {
        "rows": n,
        "with_dates": with_dates,
        "date_fraction": round(frac_dates, 3),
        "dup_rate": round(dup_rate, 3),
        "recon_score": round(recon_score, 3) if recon_score is not None else None,
        "recon_diff": round(recon_diff, 2) if recon_diff is not None else None,
        "consensus_frac": round(consensus_frac, 3) if consensus_frac is not None else None,
    }

    return {"score": round(score, 1), "issues": issues, "metrics": metrics}

