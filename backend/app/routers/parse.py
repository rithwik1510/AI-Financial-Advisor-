from __future__ import annotations

from typing import List

from fastapi import APIRouter, UploadFile, File

from ..schemas.models import ParseResponse, Transaction
from ..services import parser


router = APIRouter()


@router.post("/parse", response_model=ParseResponse)
async def parse_files(files: List[UploadFile] = File(...)):
    transactions: List[Transaction] = []
    filenames: List[str] = []
    notes_parts: List[str] = []
    all_warnings: List[str] = []
    dq_scores: List[float] = []
    dq_details = {"files": []}

    for f in files:
        try:
            filenames.append(f.filename)
            content = await f.read()
            name = f.filename.lower()
            if name.endswith(".csv"):
                tx = parser.parse_csv_bytes(content, f.filename)
                transactions.extend(tx)
                notes_parts.append(f"{f.filename}: parsed {len(tx)} from CSV/XLSX.")
            elif name.endswith(".xlsx") or name.endswith(".xls"):
                tx = parser.parse_excel_bytes(content, f.filename)
                transactions.extend(tx)
                notes_parts.append(f"{f.filename}: parsed {len(tx)} from CSV/XLSX.")
            elif name.endswith(".pdf"):
                # PDF parsing disabled in this build; attach CSV/XLSX or paste text excerpts
                all_warnings.append(f"{f.filename}: PDF parsing disabled; attach CSV/XLSX exports instead.")
                notes_parts.append(f"{f.filename}: skipped local PDF parsing (doc Q&A not available)")
            else:
                # ignore unsupported
                continue
        except Exception as e:
            all_warnings.append(f"{getattr(f,'filename','<unknown>')}: file handling failed: {e}")
            notes_parts.append(f"{getattr(f,'filename','<unknown>')}: failed to read or process file")

    notes = "Processed locally; data never leaves your system." + (" " + " ".join(notes_parts) if notes_parts else "")
    agg_dq = sum(dq_scores) / len(dq_scores) if dq_scores else (100.0 if transactions else 0.0)
    return ParseResponse(transactions=transactions, files=filenames, notes=notes, dq_score=round(agg_dq,1), dq=dq_details, warnings=all_warnings)
