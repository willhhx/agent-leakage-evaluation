#!/usr/bin/env python3
"""Compute the agent-facing reference baseline once: results/reference_baseline.csv

  python3 src/07_reference_baseline.py

Run before 04_score_runs.py so the scorer can report each trial's AUPRC relative to what a typical pipeline scores on the
same table with a random, leakage-group and study-held-out split. Takes about a minute on a laptop CPU.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd  # noqa: E402

from src.common import PROJECT_ROOT, load_truth, verify_release  # noqa: E402
from src.reference_baseline import evaluate  # noqa: E402
from src.workspace import prepare_workspace  # noqa: E402


def main(argv=None) -> int:
    verify_release()
    with tempfile.TemporaryDirectory() as tmp:
        d = prepare_workspace("baseline", "C0", 0, Path(tmp))
        table = pd.read_csv(d / "work" / "data" / "dataset.csv.gz", low_memory=False)
    res = evaluate(table, load_truth())
    out = PROJECT_ROOT / "results" / "reference_baseline.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)
    print(res.to_string(index=False))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
