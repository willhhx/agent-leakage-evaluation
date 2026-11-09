#!/usr/bin/env python3
"""Run a whole experiment: reps x 3 conditions, in blocked random order, resumable.

  python3 src/03_run_batch.py --pilot                 # 3 x 5 pilot in runs/pilot (use it to freeze the rubric, then discard)
  python3 src/03_run_batch.py --reps 10               # main experiment in runs/main
  python3 src/03_run_batch.py --reps 10 --limit 6     # do at most 6 pending trials now (spread usage over days)
  python3 src/03_run_batch.py --reps 10 --dry-run     # just show the schedule

Order: within each replicate block the three conditions are shuffled (seeded), so any drift in the model or in your usage
limits is spread across conditions instead of loading onto one. Completed trials are skipped on re-run.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import CONDITIONS, PROJECT_ROOT, read_json  # noqa: E402
from src.runner import run_trial  # noqa: E402
from src.workspace import prepare_workspace  # noqa: E402


def make_schedule(reps: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(1, reps + 1):
        for c in rng.permutation(CONDITIONS):
            rows.append({"order": len(rows) + 1, "condition": str(c), "rep": r, "run_id": f"{c}_r{r:02d}"})
    return pd.DataFrame(rows)


def is_done(run_dir: Path, phases: int) -> bool:
    p = run_dir / "status.json"
    if not p.exists():
        return False
    st = read_json(p)
    return bool(st.get("phase1_done") and (phases < 2 or st.get("phase2_done")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--pilot", action="store_true", help="5 reps into runs/pilot")
    ap.add_argument("--runs-dir", type=Path)
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--limit", type=int, default=None, help="max pending trials to run now")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-turns", type=int, default=60)
    ap.add_argument("--max-budget-usd", type=float, default=None)
    ap.add_argument("--timeout-min", type=float, default=30)
    ap.add_argument("--phases", type=int, choices=(1, 2), default=2)
    ap.add_argument("--claude-bin", default="claude")
    args = ap.parse_args(argv)

    reps = 5 if args.pilot else args.reps
    runs_dir = args.runs_dir or PROJECT_ROOT / "runs" / ("pilot" if args.pilot else "main")
    sched = make_schedule(reps, args.seed)
    runs_dir.mkdir(parents=True, exist_ok=True)
    sched.to_csv(runs_dir / "schedule.csv", index=False)
    pending = [r for r in sched.itertuples() if not is_done(runs_dir / r.run_id, args.phases)]
    print(f"{len(sched)} trials scheduled in {runs_dir}; {len(sched) - len(pending)} done, {len(pending)} pending")
    if args.dry_run:
        print(sched.to_string(index=False))
        return 0
    n = 0
    for r in pending:
        if args.limit is not None and n >= args.limit:
            break
        n += 1
        print(f"[{n}] {r.run_id} (order {r.order}) ...", flush=True)
        try:
            prepare_workspace(r.run_id, r.condition, r.rep, runs_dir, seed=args.seed, model=args.model)
            st = run_trial(runs_dir / r.run_id, claude_bin=args.claude_bin, model=args.model, max_turns=args.max_turns,
                           max_budget_usd=args.max_budget_usd, timeout_min=args.timeout_min, phases=args.phases)
            p1, p2 = st.get("phase1", {}), st.get("phase2", {})
            print(f"    phase1 {p1.get('seconds')}s turns={p1.get('num_turns')} err={p1.get('is_error')} | "
                  f"phase2 {p2.get('seconds')}s turns={p2.get('num_turns')} err={p2.get('is_error')}", flush=True)
        except KeyboardInterrupt:
            print("interrupted; re-run the same command to resume")
            return 130
        except Exception:  # keep going: one failed trial must not stop the batch
            traceback.print_exc()
    print("batch finished; next: python3 src/04_score_runs.py --runs-dir", runs_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
