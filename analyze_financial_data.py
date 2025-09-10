#!/usr/bin/env python3
"""
Local Financial Data Analyzer

CLI to analyze bank/credit statements from a local folder and produce a JSON
report. Designed to run fully offline with privacy-first defaults.

Supported inputs:
- CSV (.csv)
- Excel (.xlsx, .xls)

PDF support is intentionally omitted for reliability; CSV/XLSX exports are
preferred. You can request PDF support later if needed.

Usage example:
    python analyze_financial_data.py \
        --input "uploaded_statements" \
        --output "analysis_report.json" \
        --local --privacy-mode

Notes:
- The flags --local and --privacy-mode are accepted and enforced by design
  (no network access or telemetry); the script performs only local I/O.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import pandas as pd
except ImportError as e:  # pragma: no cover
    print(
        "Missing dependency: pandas. Install with `pip install pandas openpyxl`.",
        file=sys.stderr,
    )
    raise


# ------------------------
# Helpers and data classes
# ------------------------

SUPPORTED_EXTS = {".csv", ".xlsx", ".xls"}


@dataclass
class AnalysisConfig:
    input_dir: Path
    output_path: Path
    local: bool = True
    privacy_mode: bool = True
    verbose: bool = False


def vprint(cfg: AnalysisConfig, *args: object) -> None:
    if cfg.verbose:
        print(*args, file=sys.stderr)


def discover_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            files.append(p)
    return sorted(files)


def read_statement(path: Path, cfg: AnalysisConfig) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext in {".xlsx", ".xls"}:
        # engine auto-detection; requires openpyxl for .xlsx
        df = pd.read_excel(path)
    else:  # pragma: no cover - guarded by discover_files
        raise ValueError(f"Unsupported file type: {path}")

    # Normalize column names for easier matching
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _pick_first(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def normalize_transactions(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """
    Attempt to normalize a statement DataFrame to a common schema:
      date, description, amount, currency, category, account, source

    Heuristics handle common column variations across banks. Amounts are
    positive for inflows and negative for outflows. If separate Debit/Credit
    columns exist, they are merged into a single signed amount column.
    """
    df_work = df.copy()

    # Candidate columns by semantics
    date_cols = [
        "Date",
        "Transaction Date",
        "Posted Date",
        "Posting Date",
        "date",
    ]
    desc_cols = [
        "Description",
        "Details",
        "Memo",
        "Narrative",
        "Transaction Details",
        "description",
        "Payee",
        "Merchant",
    ]
    amount_cols = [
        "Amount",
        "Transaction Amount",
        "amount",
        "Value",
    ]
    debit_cols = ["Debit", "Withdrawal", "Money Out", "Outflow"]
    credit_cols = ["Credit", "Deposit", "Money In", "Inflow"]
    category_cols = ["Category", "Type", "Tags"]
    currency_cols = ["Currency", "CUR", "ISO Currency Code"]
    account_cols = ["Account", "Account Name", "Account Number", "Card Number"]

    # Resolve columns present in df
    date_col = _pick_first(df_work, date_cols)
    desc_col = _pick_first(df_work, desc_cols)
    amount_col = _pick_first(df_work, amount_cols)
    debit_col = _pick_first(df_work, debit_cols)
    credit_col = _pick_first(df_work, credit_cols)
    category_col = _pick_first(df_work, category_cols)
    currency_col = _pick_first(df_work, currency_cols)
    account_col = _pick_first(df_work, account_cols)

    # Build signed amount
    amt_series = None
    if amount_col is not None:
        amt_series = pd.to_numeric(df_work[amount_col], errors="coerce")
    elif debit_col or credit_col:
        debit = (
            pd.to_numeric(df_work[debit_col], errors="coerce")
            if debit_col in df_work
            else 0
        )
        credit = (
            pd.to_numeric(df_work[credit_col], errors="coerce")
            if credit_col in df_work
            else 0
        )
        # Debits negative, credits positive
        amt_series = credit.fillna(0) - debit.fillna(0)
    else:
        # If no recognizable amount columns, try last numeric column as fallback
        numeric_cols = df_work.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0:
            amt_series = pd.to_numeric(df_work[numeric_cols[-1]], errors="coerce")

    # Parse date
    if date_col is not None:
        date_series = pd.to_datetime(df_work[date_col], errors="coerce")
    else:
        # Fallback: attempt to parse any column that looks like a date
        date_series = None
        for c in df_work.columns:
            try:
                parsed = pd.to_datetime(df_work[c], errors="raise")
                date_series = parsed
                break
            except Exception:
                continue

    # Build normalized DataFrame
    norm = pd.DataFrame()
    norm["date"] = date_series
    norm["description"] = df_work[desc_col] if desc_col is not None else None
    norm["amount"] = amt_series
    norm["currency"] = (
        df_work[currency_col] if currency_col is not None else None
    )
    norm["category"] = (
        df_work[category_col] if category_col is not None else None
    )
    norm["account"] = df_work[account_col] if account_col is not None else None
    norm["source"] = source

    # Coerce data types
    norm["amount"] = pd.to_numeric(norm["amount"], errors="coerce")
    norm["date"] = pd.to_datetime(norm["date"], errors="coerce")

    # Drop rows missing critical fields
    norm = norm.dropna(subset=["amount"])  # allow missing date if truly absent

    # Strip descriptions
    if "description" in norm:
        norm["description"] = (
            norm["description"].astype(str).str.strip().replace({"nan": None})
        )

    return norm.reset_index(drop=True)


def auto_categorize(df: pd.DataFrame) -> pd.Series:
    """
    If category is missing, apply a lightweight keyword-based classifier on
    description. This is deterministic, local-only, and transparent.
    """
    if "category" in df and df["category"].notna().any():
        return df["category"]

    patterns: List[Tuple[str, str]] = [
        ("grocery|supermarket|whole foods|aldi|kroger|costco|walmart", "Groceries"),
        ("uber|lyft|taxi|metro|subway|bus|train|mta|bart|boltbus|amtrak", "Transport"),
        ("shell|exxon|bp|chevron|7-eleven|7 eleven|gas", "Fuel"),
        ("netflix|spotify|hulu|disney|prime video|youtube", "Subscriptions"),
        ("restaurant|cafe|coffee|starbucks|mcdonald|kfc|taco bell|dunkin", "Dining"),
        ("pharmacy|cvs|walgreens|rite aid|drug", "Pharmacy"),
        ("amazon|etsy|mercado|ebay|aliexpress", "Shopping"),
        ("rent|landlord|property management|mortgage", "Housing"),
        ("electric|water|utility|gas bill|internet|comcast|verizon|att", "Utilities"),
        ("salary|payroll|pay check|paycheck|direct deposit|wage", "Income"),
        ("transfer|zelle|venmo|cash app|paypal", "Transfers"),
        ("insurance|premium|geico|progressive|state farm", "Insurance"),
    ]

    desc = df.get("description", pd.Series([None] * len(df))).astype(str).str.lower()
    result = pd.Series([None] * len(df), index=df.index, dtype="object")
    for pattern, label in patterns:
        mask = desc.str.contains(pattern, na=False, regex=True)
        result.loc[mask] = label

    # Fallbacks by sign
    result = result.where(result.notna(), other=pd.Series(
        ["Income" if a and a > 0 else "General" for a in df["amount"]], index=df.index
    ))
    return result


def compute_metrics(df: pd.DataFrame) -> Dict[str, object]:
    df = df.copy()

    # Enrich
    df["category"] = auto_categorize(df)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["abs_amount"] = df["amount"].abs()

    total_inflow = float(df.loc[df["amount"] > 0, "amount"].sum() or 0.0)
    total_outflow = float(df.loc[df["amount"] < 0, "amount"].sum() or 0.0)
    net = total_inflow + total_outflow

    # Monthly summaries
    monthly = (
        df.groupby("month")["amount"].sum().rename("net").to_frame()
        .assign(
            inflow=df[df["amount"] > 0].groupby("month")["amount"].sum(),
            outflow=df[df["amount"] < 0].groupby("month")["amount"].sum(),
            tx_count=df.groupby("month")["amount"].count(),
        )
        .fillna(0)
        .reset_index()
        .sort_values("month")
    )

    # Category breakdown
    by_cat = (
        df.groupby("category")["amount"].sum().sort_values(ascending=True).reset_index()
    )

    # Top merchants by spend and frequency
    by_merchant = (
        df.groupby("description").agg(
            total_spend=("amount", lambda s: float(s[s < 0].sum() or 0.0)),
            total_inflow=("amount", lambda s: float(s[s > 0].sum() or 0.0)),
            tx_count=("amount", "count"),
        )
        .reset_index()
        .sort_values(["total_spend", "tx_count"], ascending=[True, False])
    )

    # Simple anomaly detection: Z-score by absolute amount
    if len(df) >= 5 and df["abs_amount"].std(ddof=0) > 0:
        z = (df["abs_amount"] - df["abs_amount"].mean()) / df["abs_amount"].std(ddof=0)
        anomalies = df.loc[z > 2.5].sort_values("abs_amount", ascending=False)
    else:
        anomalies = df.iloc[0:0]

    results = {
        "summary": {
            "transactions": int(len(df)),
            "total_inflow": round(total_inflow, 2),
            "total_outflow": round(total_outflow, 2),
            "net": round(net, 2),
        },
        "monthly": monthly.to_dict(orient="records"),
        "by_category": by_cat.to_dict(orient="records"),
        "by_merchant": by_merchant.head(50).to_dict(orient="records"),
        "anomalies": anomalies.head(50)[
            ["date", "description", "amount", "category", "account", "source"]
        ].to_dict(orient="records"),
    }
    return results


def analyze_folder(cfg: AnalysisConfig) -> Dict[str, object]:
    files = discover_files(cfg.input_dir)
    if not files:
        return {
            "error": f"No supported files found in '{cfg.input_dir}'. Supported: {sorted(SUPPORTED_EXTS)}",
            "input": str(cfg.input_dir),
        }

    frames: List[pd.DataFrame] = []
    for f in files:
        try:
            df_raw = read_statement(f, cfg)
            df_norm = normalize_transactions(df_raw, source=f.name)
            frames.append(df_norm)
            vprint(cfg, f"Parsed {f.name}: {len(df_norm)} rows")
        except Exception as e:  # robust to mixed bank exports
            vprint(cfg, f"Skipping {f.name}: {e}")

    if not frames:
        return {
            "error": "Unable to parse any files in input folder.",
            "input": str(cfg.input_dir),
        }

    all_tx = pd.concat(frames, ignore_index=True)
    results = compute_metrics(all_tx)
    results["files"] = [f.name for f in files]
    return results


def parse_args(argv: Optional[List[str]] = None) -> AnalysisConfig:
    p = argparse.ArgumentParser(description="Analyze local financial statements to JSON report.")
    p.add_argument("--input", required=True, help="Path to folder containing statements (CSV/XLSX)")
    p.add_argument("--output", required=True, help="Path to JSON report to write")
    p.add_argument("--local", action="store_true", help="Run in local-only mode (default)")
    p.add_argument("--privacy-mode", action="store_true", help="Enable strict privacy mode (default)")
    p.add_argument("--verbose", action="store_true", help="Print progress details")

    ns = p.parse_args(argv)
    input_dir = Path(ns.input).expanduser().resolve()
    output_path = Path(ns.output).expanduser().resolve()
    return AnalysisConfig(
        input_dir=input_dir,
        output_path=output_path,
        local=bool(ns.local or True),
        privacy_mode=bool(ns.privacy_mode or True),
        verbose=bool(ns.verbose),
    )


def main(argv: Optional[List[str]] = None) -> int:
    cfg = parse_args(argv)

    # Guardrails: local + privacy mode are accepted; the script is offline-only.
    if not cfg.input_dir.exists() or not cfg.input_dir.is_dir():
        print(f"Input folder not found: {cfg.input_dir}", file=sys.stderr)
        return 2

    results = analyze_folder(cfg)
    try:
        cfg.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg.output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        vprint(cfg, f"Wrote report: {cfg.output_path}")
    except Exception as e:
        print(f"Failed to write report: {e}", file=sys.stderr)
        return 3

    # Also print a short summary to stdout for convenience
    if "summary" in results:
        s = results["summary"]
        print(json.dumps({"summary": s, "output": str(cfg.output_path)}, indent=2))
    else:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

