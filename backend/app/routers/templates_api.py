from __future__ import annotations

import os
import time
from typing import List, Optional, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel
import yaml

from ..services import templates as tpl


router = APIRouter()


class TemplatePayload(BaseModel):
    name: str
    anchors: List[str]
    columns: Dict[str, List[float]]  # keys: date, description, amount -> [x0,x1]
    date_format: Optional[str] = None


@router.post("/templates")
def save_template(payload: TemplatePayload):
    os.makedirs(tpl.TEMPLATES_DIR, exist_ok=True)
    ts = int(time.time())
    safe_name = "".join(c for c in payload.name if c.isalnum() or c in ("-", "_", ".", " ")).strip().replace(" ", "_")
    if not safe_name:
        safe_name = f"user_{ts}"
    path = os.path.join(tpl.TEMPLATES_DIR, f"{safe_name}_{ts}.yaml")
    data = {
        "name": payload.name,
        "anchors": payload.anchors,
        "columns": payload.columns,
    }
    if payload.date_format:
        data["date_format"] = payload.date_format
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    return {"status": "ok", "path": path}

