#!/usr/bin/env python3
"""Run one trial headlessly with the Claude Code CLI, or snapshot a trial you ran by hand.

  python3 src/02_run_agent.py --condition C1 --rep 3 [--model sonnet] [--max-turns 60] [--timeout-min 30]
  python3 src/02_run_agent.py --run-id C1_r03 --snapshot 1      # manual mode: copy submission/ + code after phase 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import CONDITIONS, PROJECT_ROOT  # noqa: E402
from src.runner import run_trial, snapshot  # noqa: E402
from src.workspace import prepare_workspace  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--condition", choices=CONDITIONS)
    ap.add_argument("--rep", type=int)
    ap.add_argument("--run-id")
    ap.add_argument("--runs-dir", type=Path, default=PROJECT_ROOT / "runs" / "main")
    ap.add_argument("--snapshot", type=int, choices=(1, 2), help="manual mode: snapshot this phase and exit")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-turns", type=int, default=60)
    ap.add_argument("--max-budget-usd", type=float, default=None)
    ap.add_argument("--timeout-min", type=float, default=30)
    ap.add_argument("--phases", type=int, choices=(1, 2), default=2)
    ap.add_argument("--claude-bin", default="claude")
    args = ap.parse_args(argv)

    run_id = args.run_id or (f"{args.condition}_r{args.rep:02d}" if args.condition and args.rep else None)
    if not run_id:
        ap.error("give --run-id or both --condition and --rep")
    run_dir = args.runs_dir / run_id
    if args.snapshot:
        if not run_dir.exists():
            ap.error(f"{run_dir} does not exist; run 01_prepare_workspace.py first")
        print(f"snapshot saved: {snapshot(run_dir, args.snapshot)}")
        return 0
    if not run_dir.exists():
        if not (args.condition and args.rep):
            ap.error("run directory missing; pass --condition and --rep to create it")
        prepare_workspace(run_id, args.condition, args.rep, args.runs_dir, model=args.model)
    st = run_trial(run_dir, claude_bin=args.claude_bin, model=args.model, max_turns=args.max_turns,
                   max_budget_usd=args.max_budget_usd, timeout_min=args.timeout_min, phases=args.phases)
    print({k: st.get(k) for k in ("run_id", "model", "phase1_done", "phase2_done")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
