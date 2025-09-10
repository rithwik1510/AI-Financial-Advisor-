from __future__ import annotations

import io
import re
from datetime import datetime
from typing import List, Optional, Iterable, Tuple, Dict, Any
import os
import json
import requests
import subprocess
import tempfile
import shutil

import pandas as pd
import pdfplumber

from ..schemas.models import Transaction
from .templates import try_parse_with_templates
from .dq import compute_data_quality
from .reconcile import reconcile_signs_ilp

SUPPORTED_EXTS = {".csv", ".xlsx", ".xls", ".pdf"}


def _pick_first(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def _normalize_df(df: pd.DataFrame, source: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    date_col = _pick_first(df, ["date", "Date", "Transaction Date", "Posting Date"]) or _pick_first(
        df, ["posted", "post date"]
    )
    desc_col = _pick_first(
        df,
        [
            "description",
            "Description",
            "Details",
            "Memo",
            "Transaction Details",
            "Payee",
            "Merchant",
        ],
    )
    amount_col = _pick_first(df, ["amount", "Amount", "Transaction Amount", "Value"])
    debit_col = _pick_first(df, ["Debit", "Withdrawal", "Money Out", "Outflow"])
    credit_col = _pick_first(df, ["Credit", "Deposit", "Money In", "Inflow"])
    currency_col = _pick_first(df, ["Currency", "CUR", "ISO Currency Code"])
    account_col = _pick_first(df, ["Account", "Account Name", "Account Number", "Card Number"])

    # Build amount column
    if amount_col:
        amt = pd.to_numeric(df[amount_col], errors="coerce")
    else:
        debit = pd.to_numeric(df[debit_col], errors="coerce") if debit_col in df else 0
        credit = pd.to_numeric(df[credit_col], errors="coerce") if credit_col in df else 0
        amt = pd.Series(credit).fillna(0) - pd.Series(debit).fillna(0)

    # Build date
    if date_col:
        dt = pd.to_datetime(df[date_col], errors="coerce")
    else:
        dt = None
        for c in df.columns:
            try:
                dt = pd.to_datetime(df[c], errors="raise")
                break
            except Exception:
                continue

    norm = pd.DataFrame()
    norm["date"] = dt
    norm["description"] = df[desc_col] if desc_col in df else None
    norm["amount"] = pd.to_numeric(amt, errors="coerce")
    norm["currency"] = df[currency_col] if currency_col in df else None
    norm["category"] = None
    norm["account"] = df[account_col] if account_col in df else None
    norm["source"] = source

    norm = norm.dropna(subset=["amount"])  # allow missing dates
    return norm.reset_index(drop=True)


def parse_csv_bytes(data: bytes, source: str) -> List[Transaction]:
    df = pd.read_csv(io.BytesIO(data))
    norm = _normalize_df(df, source)
    return [Transaction(**row.to_dict()) for _, row in norm.iterrows()]


def parse_excel_bytes(data: bytes, source: str) -> List[Transaction]:
    df = pd.read_excel(io.BytesIO(data))
    norm = _normalize_df(df, source)
    return [Transaction(**row.to_dict()) for _, row in norm.iterrows()]


# -------- PDF parsing (tables + text fallback) --------

_DATE_RE = re.compile(
    r"\b((?:\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})|(?:\d{4}[\-/]\d{1,2}[\-/]\d{1,2}))\b"
)
_AMOUNT_RE = re.compile(
    r"(?P<sign>[-(])?\s*(?P<curr>[$€£₹])?\s*(?P<num>(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d{2})?)\s*(?P<crdr>(?:CR|DR))?\)??$",
    re.IGNORECASE,
)


def _parse_date_str(s: str) -> Optional[datetime]:
    s = s.strip()
    # Try explicit common formats first
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y", "%m/%d/%y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # If it looks like a date (matched by _DATE_RE), try pandas
    try:
        dt = pd.to_datetime(s, errors="coerce")
        if pd.notna(dt):
            return dt.to_pydatetime()
    except Exception:
        pass
    return None


def _parse_amount_str(raw: str) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = _AMOUNT_RE.search(s)
    if not m:
        return None
    num = m.group("num")
    sign = -1.0 if (m.group("sign") == "-" or (m.group("sign") == "(")) else 1.0
    # Handle thousand/decimal separators heuristically
    if "," in num and "." in num:
        # Assume US: 1,234.56
        num = num.replace(",", "")
    elif num.count(",") >= 1 and num.count(".") == 0:
        # Assume EU: 1.234,56 or 123,45 -> treat comma as decimal
        num = num.replace(".", "").replace(",", ".")
    # Else plain
    try:
        val = float(num)
    except Exception:
        return None
    # DR/CR tag
    crdr = (m.group("crdr") or "").upper()
    if crdr == "DR":
        sign = -1.0
    elif crdr == "CR":
        sign = 1.0
    # Parentheses parsing already implied negative via sign when '(' present; ensure closing ')' doesn’t flip
    return sign * val


def _dedupe_triplets(rows: List[Tuple[Optional[datetime], str, float]]) -> List[Tuple[Optional[datetime], str, float]]:
    seen = set()
    out = []
    for d, desc, amt in rows:
        key = (d.isoformat() if isinstance(d, datetime) else None, (desc or "").strip().lower(), round(amt, 2))
        if key in seen:
            continue
        seen.add(key)
        out.append((d, desc, amt))
    return out


def _parse_pdf_tables(data: bytes, source: str) -> List[Transaction]:
    results: List[Transaction] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for tbl in tables:
                if not tbl or len(tbl) < 2:
                    continue
                header = [str(x).strip() for x in tbl[0]]
                rows = tbl[1:]
                df = pd.DataFrame(rows, columns=header)
                try:
                    norm = _normalize_df(df, source)
                    for _, row in norm.iterrows():
                        results.append(Transaction(**row.to_dict()))
                except Exception:
                    # If header alignment is off, try without headers (positional guess)
                    try:
                        df2 = pd.DataFrame(rows)
                        df2.columns = [f"col{i+1}" for i in range(len(df2.columns))]
                        norm = _normalize_df(df2, source)
                        for _, row in norm.iterrows():
                            results.append(Transaction(**row.to_dict()))
                    except Exception:
                        continue
    return results


def _parse_pdf_text(data: bytes, source: str) -> List[Transaction]:
    # Heuristic text line parser: expects lines like 'MM/DD/YYYY <desc> <amount>'
    # Also attempts two-column page layouts via cropping left/right halves.
    def parse_lines(lines: List[str]) -> List[Tuple[Optional[datetime], str, float]]:
        items: List[Tuple[Optional[datetime], str, float]] = []
        pending: Optional[Tuple[Optional[datetime], str]] = None
        for line in lines:
            if not line:
                continue
            # Ignore common headers/footers
            if re.search(r"^\s*(page \d+|opening|closing|balance|total|statement|summary)\b", line, re.I):
                continue
            m_date = _DATE_RE.search(line)
            m_amt = _AMOUNT_RE.search(line)
            if m_date and m_amt and m_amt.start() > m_date.end():
                d = _parse_date_str(m_date.group(1))
                amount = _parse_amount_str(line[m_amt.start():])
                desc = line[m_date.end(): m_amt.start()].strip(" -:\t")
                if amount is not None and desc:
                    items.append((d, desc, float(amount)))
                    pending = None
                    continue
            if pending is not None and not m_amt and not m_date and line.strip():
                d0, desc0 = pending
                pending = (d0, (desc0 + " " + line.strip()).strip())
                continue
            if m_date and not m_amt:
                d = _parse_date_str(m_date.group(1))
                rest = line[m_date.end():].strip(" -:\t")
                pending = (d, rest)
                continue
            if pending is not None and m_amt and not m_date:
                amount = _parse_amount_str(line[m_amt.start():])
                if amount is not None:
                    d0, desc0 = pending
                    items.append((d0, desc0, float(amount)))
                    pending = None
        return items

    triplets: List[Tuple[Optional[datetime], str, float]] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            # Full page text first
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if text:
                lines = [ln for ln in text.splitlines() if ln and not ln.strip().startswith("Page ")]
                triplets.extend(parse_lines(lines))

            # Try two-column crop heuristics
            try:
                w, h = page.width, page.height
                left = page.crop((0, 0, w / 2, h))
                right = page.crop((w / 2, 0, w, h))
                left_text = left.extract_text(x_tolerance=2, y_tolerance=2) or ""
                right_text = right.extract_text(x_tolerance=2, y_tolerance=2) or ""
                if left_text:
                    triplets.extend(parse_lines([ln for ln in left_text.splitlines() if ln]))
                if right_text:
                    triplets.extend(parse_lines([ln for ln in right_text.splitlines() if ln]))
            except Exception:
                pass

    triplets = _dedupe_triplets(triplets)
    txs = [
        Transaction(
            date=d,
            description=desc,
            amount=amt,
            currency=None,
            category=None,
            account=None,
            source=source,
        )
        for d, desc, amt in triplets
    ]
    return txs


def parse_pdf_bytes(data: bytes, source: str) -> List[Transaction]:
    tx, _ = parse_pdf_bytes_with_stats(data, source)
    return tx


def parse_pdf_bytes_with_stats(data: bytes, source: str) -> Tuple[List[Transaction], dict]:
    """Consensus-based extraction with provenance counts and DQ."""
    candidates: List[Transaction] = []
    provenance: Dict[str, int] = {}

    # Try template-driven parse first (if templates match)
    try:
        tpl_tx = try_parse_with_templates(data, source)
        if tpl_tx:
            provenance["template"] = len(tpl_tx)
            candidates.extend(tpl_tx)
    except Exception:
        provenance["template"] = 0

    # Strategy 1: table extraction
    try:
        tbl = _parse_pdf_tables(data, source)
        provenance["tables"] = len(tbl)
        candidates.extend(tbl)
    except Exception:
        provenance["tables"] = 0

    # Strategy 2: layout-aware words grouping
    try:
        wrd = _parse_pdf_words(data, source)
        provenance["words"] = len(wrd)
        candidates.extend(wrd)
    except Exception:
        provenance["words"] = 0

    # Strategy 3: plain text line heuristic
    try:
        txt = _parse_pdf_text(data, source)
        provenance["text"] = len(txt)
        candidates.extend(txt)
    except Exception:
        provenance["text"] = 0

    # If nothing or scanned, try OCR (if enabled)
    try:
        enable_ocr = os.getenv("ENABLE_OCR", "0") == "1"
        if (not candidates or _likely_scanned_pdf(data)) and enable_ocr:
            ocr_bytes = _try_ocr_pdf(data)
            if ocr_bytes:
                try:
                    ot = _parse_pdf_tables(ocr_bytes, source)
                    provenance["ocr_tables"] = len(ot)
                    candidates.extend(ot)
                except Exception:
                    provenance["ocr_tables"] = 0
                try:
                    ow = _parse_pdf_words(ocr_bytes, source)
                    provenance["ocr_words"] = len(ow)
                    candidates.extend(ow)
                except Exception:
                    provenance["ocr_words"] = 0
                try:
                    ox = _parse_pdf_text(ocr_bytes, source)
                    provenance["ocr_text"] = len(ox)
                    candidates.extend(ox)
                except Exception:
                    provenance["ocr_text"] = 0
    except Exception:
        pass

    # Cluster by (date, desc, amount) and vote
    cluster: Dict[Tuple[Optional[str], str, float], Dict[str, Any]] = {}
    def key_of(t: Transaction):
        return (
            t.date.isoformat() if isinstance(t.date, datetime) else None,
            (t.description or "").strip().lower(),
            round(float(t.amount), 2),
        )

    for t in candidates:
        k = key_of(t)
        if k not in cluster:
            cluster[k] = {"t": t, "count": 0}
        cluster[k]["count"] += 1

    # Accept if seen by >=2 strategies or unique but we need volume
    accepted: List[Transaction] = []
    for k, v in cluster.items():
        c = v["count"]
        if c >= 2:
            accepted.append(v["t"])
        elif c == 1 and len(accepted) < 10:  # allow a few uniques to avoid empty parses
            accepted.append(v["t"])

    # Extract statement meta, attempt ILP-based sign reconciliation, then compute DQ
    meta = extract_pdf_statement_meta(data)
    if meta:
        try:
            rec = reconcile_signs_ilp(accepted, meta)
            accepted = rec.get("corrected", accepted)
            provenance["reconcile_solver"] = 1 if rec.get("solver") else 0
        except Exception:
            provenance["reconcile_solver"] = 0
    dq = compute_data_quality(accepted, meta=meta, provenance_counts=provenance)

    stats = {
        "provenance": provenance,
        "clusters": len(cluster),
        "accepted": len(accepted),
        "meta": meta,
        "dq": dq,
    }
    return accepted, stats


# (Removed legacy LLM-assisted PDF parsing fallback.)


def _likely_scanned_pdf(data: bytes) -> bool:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = list(pdf.pages)
            if not pages:
                return False
            text_chars = 0
            sample = pages[: min(3, len(pages))]
            for p in sample:
                txt = p.extract_text(x_tolerance=2, y_tolerance=2) or ""
                text_chars += len(txt)
            return text_chars < 30  # almost no text
    except Exception:
        return False


def _try_ocr_pdf(data: bytes) -> Optional[bytes]:
    # Prefer ocrmypdf CLI if available
    if shutil.which("ocrmypdf"):
        try:
            with tempfile.TemporaryDirectory() as td:
                inp = os.path.join(td, "in.pdf")
                outp = os.path.join(td, "out.pdf")
                with open(inp, "wb") as f:
                    f.write(data)
                cmd = [
                    "ocrmypdf",
                    "--force-ocr",
                    "--skip-text",
                    "--rotate-pages",
                    "--deskew",
                    "--optimize",
                    "1",
                    "--language",
                    "eng",
                    "--output-type",
                    "pdf",
                    inp,
                    outp,
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with open(outp, "rb") as f:
                    return f.read()
        except Exception:
            return None
    # If no ocrmypdf, try returning None (avoid heavy alternative deps)
    return None


def _group_words_to_lines(words: List[dict], y_tolerance: float = 3.0) -> List[List[dict]]:
    if not words:
        return []
    ws = sorted(words, key=lambda w: (w.get("top", 0.0), w.get("x0", 0.0)))
    lines: List[List[dict]] = []
    current: List[dict] = []
    current_top: Optional[float] = None
    for w in ws:
        top = float(w.get("top", 0.0))
        if current_top is None:
            current_top = top
            current = [w]
            continue
        if abs(top - current_top) <= y_tolerance:
            current.append(w)
        else:
            lines.append(sorted(current, key=lambda ww: ww.get("x0", 0.0)))
            current = [w]
            current_top = top
    if current:
        lines.append(sorted(current, key=lambda ww: ww.get("x0", 0.0)))
    return lines


def _parse_pdf_words(data: bytes, source: str) -> List[Transaction]:
    results: List[Transaction] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2, y_tolerance=2) or []
            if not words:
                continue
            lines = _group_words_to_lines(words, y_tolerance=3.5)
            for wline in lines:
                texts = [w.get("text", "") for w in wline if w.get("text")]
                if not texts:
                    continue
                raw = " ".join(texts)
                # Ignore totals/headers
                if re.search(r"\b(total|balance|statement|opening|closing|page \d+)\b", raw, re.I):
                    continue
                # Find date token
                date_idx: Optional[int] = None
                date_val: Optional[datetime] = None
                for i, t in enumerate(texts[:6]):  # date is usually near the start
                    m = _DATE_RE.search(t)
                    if m:
                        d = _parse_date_str(m.group(1))
                        if d:
                            date_idx = i
                            date_val = d
                            break
                # Find amount using last tokens from right
                amt_idx: Optional[int] = None
                amount_val: Optional[float] = None
                for j in range(len(texts) - 1, max(-1, (date_idx or 0) - 1), -1):
                    cand = texts[j]
                    amt = _parse_amount_str(cand)
                    if amt is None and j - 1 >= 0:
                        # Try combining with previous (e.g., '$' '123.45' or '(123.45)')
                        combo = texts[j - 1] + cand
                        amt = _parse_amount_str(combo)
                        if amt is not None:
                            j = j - 1
                    if amt is not None:
                        amt_idx = j
                        amount_val = float(amt)
                        break
                if amount_val is None:
                    continue
                # Build description between date and amount if possible
                desc_tokens = []
                start = (date_idx + 1) if date_idx is not None else 0
                end = amt_idx if amt_idx is not None else len(texts)
                if start < end:
                    desc_tokens = texts[start:end]
                desc = " ".join(desc_tokens).strip(" -:\t") or raw
                results.append(
                    Transaction(
                        date=date_val,
                        description=desc,
                        amount=amount_val,
                        currency=None,
                        category=None,
                        account=None,
                        source=source,
                    )
                )
    # Deduplicate
    seen = set()
    deduped: List[Transaction] = []
    for t in results:
        key = (
            t.date.isoformat() if isinstance(t.date, datetime) else None,
            (t.description or "").strip().lower(),
            round(float(t.amount), 2),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


# -------- Statement metadata extraction + reconciliation (generic) --------

_OPENING_RE = re.compile(r"\b(opening\s+balance|beginning\s+balance)\b[:\s]*", re.I)
_CLOSING_RE = re.compile(r"\b(closing\s+balance|ending\s+balance)\b[:\s]*", re.I)
_TOTAL_DEP_RE = re.compile(r"\b(total\s+(?:deposits|credits))\b[:\s]*", re.I)
_TOTAL_WDR_RE = re.compile(r"\b(total\s+(?:withdrawals|debits|charges))\b[:\s]*", re.I)


def extract_pdf_statement_meta(data: bytes) -> dict:
    meta: dict = {}
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join([(p.extract_text(x_tolerance=2, y_tolerance=2) or "") for p in pdf.pages])
    except Exception:
        text = ""
    if not text:
        return meta
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def find_amount_after(pattern: re.Pattern) -> Optional[float]:
        for ln in lines:
            if pattern.search(ln):
                # Try amount at end or after label
                m = _AMOUNT_RE.search(ln)
                if m:
                    amt = _parse_amount_str(ln[m.start() :])
                    if amt is not None:
                        return float(amt)
                # Try next tokens split by whitespace
                parts = re.split(r"\s{2,}|\t|\s-\s|:\s*", ln)
                for p in reversed(parts):
                    a = _parse_amount_str(p)
                    if a is not None:
                        return float(a)
        return None

    opening = find_amount_after(_OPENING_RE)
    closing = find_amount_after(_CLOSING_RE)
    total_deposits = find_amount_after(_TOTAL_DEP_RE)
    total_withdrawals = find_amount_after(_TOTAL_WDR_RE)
    # Normalize signs: totals commonly reported as positive
    if total_withdrawals is not None:
        total_withdrawals = -abs(total_withdrawals)
    meta.update(
        {
            "opening_balance": opening,
            "closing_balance": closing,
            "total_deposits": total_deposits,
            "total_withdrawals": total_withdrawals,
        }
    )
    return meta


def reconcile_transactions_with_meta(transactions: List[Transaction], meta: dict) -> dict:
    s = sum(float(t.amount) for t in transactions if isinstance(t.amount, (int, float)))
    opening = meta.get("opening_balance")
    closing = meta.get("closing_balance")
    t_dep = meta.get("total_deposits")
    t_wdr = meta.get("total_withdrawals")
    result = {
        "transactions_sum": round(s, 2),
        "opening_balance": opening,
        "closing_balance": closing,
        "expected_delta": (closing - opening) if (opening is not None and closing is not None) else None,
        "totals_section_sum": (t_dep or 0.0) + (t_wdr or 0.0) if (t_dep is not None or t_wdr is not None) else None,
        "reconciled": None,
        "mismatch": None,
    }
    # Reconcile by balances if both present
    if result["expected_delta"] is not None:
        diff = abs(result["transactions_sum"] - result["expected_delta"])
        result["reconciled"] = diff <= max(1.0, 0.005 * abs(result["expected_delta"]))  # $1 or 0.5%
        result["mismatch"] = round(diff, 2)
        return result
    # Else reconcile by totals section, if present
    if result["totals_section_sum"] is not None:
        diff = abs(result["transactions_sum"] - result["totals_section_sum"])
        result["reconciled"] = diff <= max(1.0, 0.005 * abs(result["totals_section_sum"]))
        result["mismatch"] = round(diff, 2)
        return result
    # No meta to reconcile with
    result["reconciled"] = None
    return result
