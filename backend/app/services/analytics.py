from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Tuple

import pandas as pd

from .categorizer import auto_categorize, is_essential
from pandas.tseries.offsets import DateOffset


def _to_df(transactions: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(transactions)
    if "date" in df:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"]).copy()
    if "description" not in df:
        df["description"] = None
    if "category" not in df:
        df["category"] = None
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Fill categories
    df["category"] = [
        (c if pd.notna(c) and str(c).strip() else auto_categorize(d, a))
        for c, d, a in zip(df.get("category", [None] * len(df)), df.get("description", [None] * len(df)), df["amount"])
    ]
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["abs_amount"] = df["amount"].abs()
    return df


def _apply_category_rules(df: pd.DataFrame, rules: List[Dict[str, Any]]) -> pd.DataFrame:
    dfr = df.copy()
    if not rules:
        return dfr
    desc = dfr.get("description", pd.Series([None] * len(dfr))).astype(str).str.lower()
    import re as _re
    for rule in rules:
        try:
            mt = str(rule.get("match_type") or "contains").lower()
            pat = str(rule.get("pattern") or "").strip()
            cat = str(rule.get("category") or "").strip()
            if not pat or not cat:
                continue
            if mt == "regex":
                rx = _re.compile(pat, flags=_re.IGNORECASE)
                mask = desc.apply(lambda s: bool(rx.search(s)))
            else:
                low = pat.lower()
                mask = desc.str.contains(_re.escape(low), case=False, regex=True)
            dfr.loc[mask, "category"] = cat
        except Exception:
            continue
    return dfr


def compute_analytics(
    transactions: List[Dict[str, Any]],
    liquid_savings: float | None,
    monthly_debt_payments: float | None,
    budgets: Dict[str, float] | None = None,
    category_rules: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    df = enrich(_to_df(transactions))
    if category_rules:
        df = _apply_category_rules(df, category_rules)
    if len(df) == 0:
        return {
            "summary": {"transactions": 0, "total_inflow": 0.0, "total_outflow": 0.0, "net": 0.0},
            "monthly": [],
            "by_category": [],
            "by_merchant": [],
            "savings_rate": 0.0,
            "dti": None,
            "emergency_fund_months": None,
            "discretionary_share": None,
            "health_score": None,
            "insights": [],
            "anomalies": [],
            "recurring": [],
        }

    # Totals
    total_inflow = float(df.loc[df["amount"] > 0, "amount"].sum() or 0.0)
    total_outflow = float(df.loc[df["amount"] < 0, "amount"].sum() or 0.0)
    tx_count = int(len(df))
    net = total_inflow + total_outflow

    # Monthly
    monthly = (
        df.groupby("month")["amount"].agg(["sum", "count"]).rename(columns={"sum": "net", "count": "tx_count"})
        .reset_index()
    )
    # income/expenses per month
    income_by_month = df[df["amount"] > 0].groupby("month")["amount"].sum()
    expense_by_month = df[df["amount"] < 0].groupby("month")["amount"].sum()
    monthly = monthly.merge(income_by_month.rename("income"), on="month", how="left")
    monthly = monthly.merge(expense_by_month.rename("expenses"), on="month", how="left")
    monthly = monthly.fillna({"income": 0.0, "expenses": 0.0})
    monthly = monthly[["month", "income", "expenses", "net", "tx_count"]]

    # Category breakdown (expenses negative)
    by_cat = df.groupby("category")["amount"].sum().reset_index()

    # Merchants
    by_merchant = (
        df.groupby("description").agg(
            total_spend=("amount", lambda s: float(s[s < 0].sum() or 0.0)),
            total_inflow=("amount", lambda s: float(s[s > 0].sum() or 0.0)),
            tx_count=("amount", "count"),
        )
        .reset_index()
        .sort_values(["total_spend", "tx_count"], ascending=[True, False])
    )

    # Savings rate (overall)
    expenses_abs = abs(total_outflow)
    savings = max(total_inflow - expenses_abs, 0.0)
    savings_rate = (savings / total_inflow) if total_inflow > 0 else 0.0

    # Discretionary vs essentials
    df["is_essential"] = df["category"].map(is_essential).fillna(False)
    essentials_spend = float(df.loc[(df["amount"] < 0) & (df["is_essential"] == True), "amount"].sum() or 0.0)
    discretionary_spend = float(df.loc[(df["amount"] < 0) & (df["is_essential"] == False), "amount"].sum() or 0.0)
    total_expenses_abs = abs(essentials_spend + discretionary_spend)
    discretionary_share = (abs(discretionary_spend) / total_expenses_abs) if total_expenses_abs > 0 else None

    # DTI (monthly)
    # If monthly_debt_payments not provided, approximate from Debt category outflows
    monthly_debt = monthly_debt_payments
    if monthly_debt is None:
        debt_outflows = df.loc[(df["amount"] < 0) & (df["category"] == "Debt"), ["month", "amount"]]
        monthly_debt = float(abs(debt_outflows["amount"].sum())) / max(len(monthly), 1)
    avg_monthly_income = float(max(monthly["income"].mean(), 0.0)) if len(monthly) else 0.0
    dti = (monthly_debt / avg_monthly_income) if avg_monthly_income > 0 else None

    # Emergency fund adequacy (months)
    avg_monthly_expenses_abs = float(abs(monthly["expenses"].mean())) if len(monthly) else 0.0
    emergency_fund_months = (liquid_savings / avg_monthly_expenses_abs) if (liquid_savings is not None and avg_monthly_expenses_abs > 0) else None

    # Anomalies (z-score on absolute amount)
    anomalies = []
    if len(df) >= 5 and df["abs_amount"].std(ddof=0) > 0:
        z = (df["abs_amount"] - df["abs_amount"].mean()) / df["abs_amount"].std(ddof=0)
        outliers = df.loc[z > 2.5].sort_values("abs_amount", ascending=False)
        anomalies = outliers[["date", "description", "amount", "category", "account", "source"]].to_dict(orient="records")

    # Health score (0-100)
    # Weights: savings 40%, DTI 25%, emergency 20%, discretionary 15%
    def clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    savings_score = clamp((savings_rate / 0.2) * 100.0, 0.0, 100.0)  # 20%+ => 100
    if dti is None:
        dti_score = None
    else:
        # 10% or less => 100, 43%+ => 0
        if dti <= 0.10:
            dti_score = 100.0
        elif dti >= 0.43:
            dti_score = 0.0
        else:
            # linear decay between 10% and 43%
            dti_score = clamp(100.0 * (1 - ((dti - 0.10) / (0.43 - 0.10))), 0.0, 100.0)

    if emergency_fund_months is None:
        emergency_score = None
    else:
        # 0 => 0, 3 mo => 70, 6 mo+ => 100
        if emergency_fund_months >= 6:
            emergency_score = 100.0
        elif emergency_fund_months >= 3:
            # map 3..6 => 70..100
            emergency_score = 70.0 + (emergency_fund_months - 3) * (30.0 / 3.0)
        else:
            emergency_score = clamp((emergency_fund_months / 3.0) * 70.0, 0.0, 70.0)

    if discretionary_share is None:
        discretionary_score = None
    else:
        # 15% => 100, 30% => 70, 70%+ => 0 (linear bands)
        if discretionary_share <= 0.15:
            discretionary_score = 100.0
        elif discretionary_share <= 0.30:
            # map 15..30 => 100..70
            discretionary_score = 100.0 - ((discretionary_share - 0.15) / 0.15) * 30.0
        elif discretionary_share <= 0.70:
            # map 30..70 => 70..0
            discretionary_score = 70.0 - ((discretionary_share - 0.30) / 0.40) * 70.0
        else:
            discretionary_score = 0.0

    weighted_parts: List[Tuple[float, float]] = []
    if savings_score is not None:
        weighted_parts.append((savings_score, 0.40))
    if dti_score is not None:
        weighted_parts.append((dti_score, 0.25))
    if emergency_score is not None:
        weighted_parts.append((emergency_score, 0.20))
    if discretionary_score is not None:
        weighted_parts.append((discretionary_score, 0.15))
    total_weight = sum(w for _, w in weighted_parts) or 1.0
    health_score = sum(score * w for score, w in weighted_parts) / total_weight

    summary = {
        "transactions": tx_count,
        "total_inflow": round(total_inflow, 2),
        "total_outflow": round(total_outflow, 2),
        "net": round(net, 2),
    }

    insights: List[str] = []
    if savings_rate < 0.10:
        insights.append("Savings rate is below 10%; consider cutting discretionary spend or increasing income.")
    if dti is not None and dti > 0.36:
        insights.append("Debt-to-income ratio is above 36%; consider reducing debt payments or refinancing.")
    if emergency_fund_months is not None and emergency_fund_months < 3:
        insights.append("Emergency fund covers less than 3 months of expenses; aim for 3-6 months.")
    if discretionary_share is not None and discretionary_share > 0.5:
        insights.append("Over half of expenses are discretionary; consider tightening optional categories.")

    # Recurring detection
    def detect_recurring(df_in: pd.DataFrame) -> List[Dict[str, Any]]:
        rec: List[Dict[str, Any]] = []
        dfr = df_in.copy()
        dfr = dfr.dropna(subset=["date"])  # need dates
        if len(dfr) == 0:
            return rec

        # Work per description and polarity (expense vs income)
        for direction, sub in [("expense", dfr[dfr["amount"] < 0]), ("income", dfr[dfr["amount"] > 0])]:
            if len(sub) == 0:
                continue
            for desc, g in sub.groupby("description"):
                if g.empty:
                    continue
                # Use absolute amounts for clustering
                amounts = g["amount"].abs().sort_values()
                median_amt = float(amounts.median())
                # Dynamic tolerance: $5 or 5%
                tol = max(5.0, 0.05 * median_amt)
                sel = g.loc[(g["amount"].abs() >= median_amt - tol) & (g["amount"].abs() <= median_amt + tol)].copy()
                if len(sel) < 2:
                    continue

                # Check month coverage and intervals
                sel = sel.sort_values("date")
                months = sel["date"].dt.to_period("M").nunique()
                if months < 2:
                    # at least across two different months for recurring
                    continue

                diffs = sel["date"].sort_values().diff().dropna().dt.days.astype(float)
                if len(diffs) == 0:
                    continue
                med = float(diffs.median())
                avg = float(diffs.mean())

                # Infer frequency
                if 26 <= med <= 35:
                    freq = "monthly"
                    next_date = (sel["date"].iloc[-1] + DateOffset(months=1)).to_pydatetime()
                    conf = "high"
                elif 13 <= med <= 16:
                    freq = "biweekly"
                    next_date = (sel["date"].iloc[-1] + pd.Timedelta(days=14)).to_pydatetime()
                    conf = "high"
                elif 6 <= med <= 8:
                    freq = "weekly"
                    next_date = (sel["date"].iloc[-1] + pd.Timedelta(days=7)).to_pydatetime()
                    conf = "medium"
                else:
                    # Irregular but still likely repeating given month coverage
                    freq = "irregular"
                    # heuristic next date ~ median interval
                    next_date = (sel["date"].iloc[-1] + pd.Timedelta(days=int(round(med))))
                    conf = "low"

                item = {
                    "description": desc,
                    "typical_amount": round(median_amt, 2),
                    "type": direction,
                    "occurrences": int(len(sel)),
                    "first_date": sel["date"].iloc[0].to_pydatetime(),
                    "last_date": sel["date"].iloc[-1].to_pydatetime(),
                    "avg_interval_days": round(avg, 1),
                    "median_interval_days": round(med, 1),
                    "frequency": freq,
                    "confidence": conf,
                    "next_estimated_date": pd.to_datetime(next_date).to_pydatetime(),
                }
                rec.append(item)

        # Sort: expenses first by amount desc, then income
        rec = sorted(rec, key=lambda r: (0 if r["type"] == "expense" else 1, -r["typical_amount"], r["description"] or ""))
        # Limit to a reasonable number
        return rec[:50]

    recurring = detect_recurring(df)

    # Budgets variance (optional): compare average monthly spend per category vs target
    budget_variance = None
    if budgets and len(monthly) > 0:
        try:
            # Compute average monthly expenses per category (absolute values)
            df_exp = df[df["amount"] < 0].copy()
            if not df_exp.empty:
                per_month_cat = (
                    df_exp.groupby(["month", "category"]) ["amount"].sum().reset_index()
                )
                avg_cat = per_month_cat.groupby("category")["amount"].mean().reset_index()
                avg_cat["actual"] = avg_cat["amount"].abs()
                avg_cat = avg_cat.drop(columns=["amount"])  # keep actual
                rows: List[Dict[str, Any]] = []
                for k, target in budgets.items():
                    try:
                        t = float(target)
                    except Exception:
                        continue
                    actual = float(avg_cat.loc[avg_cat["category"] == k, "actual"].values[0]) if (avg_cat["category"] == k).any() else 0.0
                    rows.append({
                        "category": k,
                        "actual": round(actual, 2),
                        "target": round(t, 2),
                        "variance": round(actual - t, 2),  # positive means over target
                    })
                budget_variance = sorted(rows, key=lambda r: (-r["variance"], r["category"]))
        except Exception:
            budget_variance = None

    result = {
        "summary": summary,
        "monthly": monthly.sort_values("month").to_dict(orient="records"),
        "by_category": by_cat.sort_values("amount").to_dict(orient="records"),
        "by_merchant": by_merchant.head(50).to_dict(orient="records"),
        "savings_rate": round(savings_rate, 4),
        "dti": round(dti, 4) if dti is not None else None,
        "emergency_fund_months": round(emergency_fund_months, 2) if emergency_fund_months is not None else None,
        "discretionary_share": round(discretionary_share, 4) if discretionary_share is not None else None,
        "health_score": round(health_score, 1) if health_score is not None else None,
        "insights": insights,
        "anomalies": anomalies,
        "recurring": recurring,
        "budget_variance": budget_variance,
    }
    return result
