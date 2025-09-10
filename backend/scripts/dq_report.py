from __future__ import annotations

import argparse
import glob
import os

from backend.app.services import parser as prs


def main():
    ap = argparse.ArgumentParser(description="Compute data quality for PDFs in a folder")
    ap.add_argument("path", help="Folder or glob (e.g., data/*.pdf)")
    args = ap.parse_args()

    files = []
    if os.path.isdir(args.path):
        files = [os.path.join(args.path, f) for f in os.listdir(args.path) if f.lower().endswith(".pdf")]
    else:
        files = glob.glob(args.path)

    print("file,rows,dq_score,recon_score,recon_diff,issues")
    for fp in files:
        try:
            with open(fp, "rb") as f:
                data = f.read()
            tx, stats = prs.parse_pdf_bytes_with_stats(data, os.path.basename(fp))
            dq = stats.get("dq", {})
            rows = len(tx)
            dq_score = dq.get("score", "")
            metrics = dq.get("metrics", {})
            rs = metrics.get("recon_score", "")
            rd = metrics.get("recon_diff", "")
            issues = ";".join(dq.get("issues", []))
            print(f"{os.path.basename(fp)},{rows},{dq_score},{rs},{rd},{issues}")
        except Exception as e:
            print(f"{os.path.basename(fp)},0,,,'error:{e}',parse_failed")


if __name__ == "__main__":
    main()

