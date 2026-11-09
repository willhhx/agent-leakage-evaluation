#!/usr/bin/env python3
"""Create the sandbox and prompts for one trial without running an agent (manual mode).

  python3 src/01_prepare_workspace.py --condition C0 --rep 1 [--runs-dir runs/main]

Then open runs/<run_id>/work/ in any agent (Claude Code app, another model, a person), paste runs/<run_id>/prompt_phase1.md,
let it finish, and run   python3 src/02_run_agent.py --run-id <run_id> --snapshot 1
Repeat with prompt_phase2.md in the same session and --snapshot 2.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import CONDITIONS, PROJECT_ROOT  # noqa: E402
from src.workspace import prepare_workspace  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    ap.add_argument("--rep", type=int, required=True)
    ap.add_argument("--runs-dir", type=Path, default=PROJECT_ROOT / "runs" / "main")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    run_id = f"{args.condition}_r{args.rep:02d}"
    d = prepare_workspace(run_id, args.condition, args.rep, args.runs_dir, overwrite=args.overwrite)
    print(f"prepared {d}\n  agent working directory: {d / 'work'}\n  phase 1 prompt: {d / 'prompt_phase1.md'}"
          f"\n  phase 2 prompt: {d / 'prompt_phase2.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
