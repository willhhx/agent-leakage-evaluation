#!/usr/bin/env python3
"""Score every trial in a runs directory -> results/<name>_run_scores.csv (one row per trial and phase).

  python3 src/04_score_runs.py --runs-dir runs/main [--label-sheet]

--label-sheet also writes labels/<name>_label_sheet.csv with the automatic flags pre-filled and empty columns for manual
coding (see docs/rubric.md). Fill it in, save as labels/manual_<rater>.csv, and 05_analyze.py will report agreement.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import PROJECT_ROOT, load_truth, reference_values, verify_release  # noqa: E402
from src.scoring import score_run  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", type=Path, default=PROJECT_ROOT / "runs" / "main")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--label-sheet", action="store_true")
    args = ap.parse_args(argv)

    verify_release()
    truth, refs = load_truth(), reference_values()
    name = args.runs_dir.name
    rows = []
    for d in sorted(p for p in args.runs_dir.iterdir() if (p / "meta.json").exists()):
        rows.extend(score_run(d, truth, refs))
    if not rows:
        print(f"no scored runs found in {args.runs_dir}")
        return 1
    df = pd.DataFrame(rows).sort_values(["condition", "rep", "phase"])
    out = args.out or PROJECT_ROOT / "results" / f"{name}_run_scores.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    ok = df["contract_ok"].fillna(False)
    print(f"scored {df['run_id'].nunique()} trials / {len(df)} phase rows -> {out}")
    print(f"valid submissions: {int(ok.sum())}/{len(df)}")
    print(df.groupby(["phase", "condition"])["split_type"].value_counts().unstack(fill_value=0).to_string())
    if args.label_sheet:
        cols = ["run_id", "condition", "rep", "phase", "split_type", "tx_mentions_leakage", "tx_audit_similarity",
                "tx_audit_overlap", "tx_used_provided_groups", "tx_code_grouped_split"]
        sheet = df[[c for c in cols if c in df.columns]].copy()
        for c in ("audit_performed", "audit_type", "self_corrected", "notes"):
            sheet[c] = ""
        lp = PROJECT_ROOT / "labels" / f"{name}_label_sheet.csv"
        lp.parent.mkdir(parents=True, exist_ok=True)
        sheet.to_csv(lp, index=False)
        print(f"label sheet -> {lp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
