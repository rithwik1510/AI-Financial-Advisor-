from __future__ import annotations

import io
import os
from typing import List, Dict, Any, Optional

import yaml
import pdfplumber

from ..schemas.models import Transaction


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _load_yaml_templates() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not os.path.isdir(TEMPLATES_DIR):
        return items
    for name in os.listdir(TEMPLATES_DIR):
        if not name.endswith(".yaml") and not name.endswith(".yml"):
            continue
        path = os.path.join(TEMPLATES_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = yaml.safe_load(f) or {}
                if isinstance(obj, dict):
                    items.append(obj)
        except Exception:
            continue
    return items


def _page_text_sample(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = pdf.pages[:2]
            text = "\n".join([(p.extract_text(x_tolerance=2, y_tolerance=2) or "") for p in pages])
            return text
    except Exception:
        return ""


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


def try_parse_with_templates(data: bytes, source: str) -> List[Transaction]:
    """Attempt a template-driven parse if anchors match.

    Minimal template schema:
    - name: string
    - anchors: ["HEADER TOKEN", ...]  # all must be present in first two pages
    - columns: { date: [x0, x1], description: [x0, x1], amount: [x0, x1] }  # page-space x ranges
    - date_format: optional strftime-like (best-effort)
    """
    templates = _load_yaml_templates()
    if not templates:
        return []

    sample = _page_text_sample(data)
    selected = None
    for tpl in templates:
        anchors = tpl.get("anchors") or []
        if anchors and all(a.lower() in sample.lower() for a in anchors):
            selected = tpl
            break
    if not selected:
        return []

    cols = selected.get("columns") or {}
    rx = cols.get("date") or [0, 120]
    rdesc = cols.get("description") or [120, 380]
    ramt = cols.get("amount") or [380, 9999]

    out: List[Transaction] = []
    try:
        from datetime import datetime
        import re
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                words = page.extract_words(x_tolerance=2, y_tolerance=2) or []
                for line in _group_words_to_lines(words, y_tolerance=3.5):
                    xs = [(w.get("x0", 0.0), w.get("text", "")) for w in line]
                    if not xs:
                        continue
                    d_tokens = [t for x, t in xs if rx[0] <= float(x) <= rx[1]]
                    a_tokens = [t for x, t in xs if ramt[0] <= float(x) <= ramt[1]]
                    desc_tokens = [t for x, t in xs if rdesc[0] <= float(x) <= rdesc[1]]
                    # Parse date (first date-like token)
                    date_val = None
                    for t in d_tokens[:4]:
                        m = re.search(r"\b(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})\b", t)
                        if m:
                            txt = m.group(1)
                            for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%y", "%d/%m/%y"):
                                try:
                                    date_val = datetime.strptime(txt, fmt)
                                    break
                                except Exception:
                                    continue
                            if date_val:
                                break
                    # Parse amount (rightmost number)
                    amount_val = None
                    for t in reversed(a_tokens):
                        try:
                            s = t.replace(",", "").replace("$", "").strip()
                            neg = s.startswith("(") or s.startswith("-")
                            s = s.strip("() ")
                            if s.count(".") > 1:
                                continue
                            val = float(s)
                            amount_val = -abs(val) if neg else val
                            break
                        except Exception:
                            continue
                    if amount_val is None:
                        continue
                    desc = " ".join(desc_tokens).strip(" -:\t")
                    if not desc:
                        continue
                    out.append(Transaction(date=date_val, description=desc, amount=float(amount_val), source=source))
    except Exception:
        return []
    # Deduplicate
    seen = set()
    deduped: List[Transaction] = []
    for t in out:
        key = (
            t.date.isoformat() if t.date else None,
            (t.description or "").strip().lower(),
            round(float(t.amount), 2),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped

