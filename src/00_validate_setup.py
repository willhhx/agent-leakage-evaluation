#!/usr/bin/env python3
"""Pre-flight check. Run this first: python3 src/00_validate_setup.py

Checks (1) the Python packages, (2) that the LCI-IEDB v1.0 release is present and matches its SHA256SUMS, (3) that this
study's leakage-exposure code reproduces the release's own S1/S4 numbers and classifies S1, S4 and S5 correctly, and
(4) whether the Claude Code CLI is available. Exit code 0 only if everything needed for scoring passes.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd  # noqa: E402

from src.common import (RES_EXPOSURE, SPLITS_FILE, load_truth, python_dir_first_env, reference_values, release_dir,  # noqa: E402
                        verify_release)
from src.leakage_metrics import RELEASE_VECTORS, classify_split, exposure  # noqa: E402
from src.runner import claude_version  # noqa: E402

TOL = 0.002


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claude-bin", default="claude")
    args = ap.parse_args(argv)
    ok = True

    def report(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed)
        print(f"[{'PASS' if passed else 'FAIL'}] {name}{(': ' + detail) if detail else ''}")

    import numpy, scipy, sklearn, matplotlib  # noqa: F401
    report("packages", True, f"numpy {numpy.__version__}, pandas {pd.__version__}, scipy {scipy.__version__}, "
                             f"scikit-learn {sklearn.__version__}, matplotlib {matplotlib.__version__}")
    try:
        rel = release_dir()
        sums = verify_release(rel)
        report("release checksums", True, f"{len(sums)} files verified in {rel}")
    except (OSError, ValueError) as exc:
        report("release checksums", False, str(exc))
        return 1

    refs = reference_values(rel)
    report("reference values", True, ", ".join(f"{k}={v:.3f}" for k, v in refs.items()))
    truth = load_truth(rel)
    sp = pd.read_csv(rel / SPLITS_FILE, usecols=["row_id", "S1_cv", "S4_cv"])
    ref = pd.read_csv(rel / RES_EXPOSURE)
    expect = {"S1": "group_held_out", "S4": "random_like"}
    for name, col in (("S1", "S1_cv"), ("S4", "S4_cv")):
        s = sp[["row_id", col]].rename(columns={col: "fold"})
        s = s[s["fold"] >= 0]
        e = exposure(truth, s)
        worst = max(abs(e[k] - float(ref[(ref["split"] == name) & (ref["vector"] == k)]["fraction_exposed"].iloc[0])) for k in RELEASE_VECTORS)
        report(f"exposure reproduces release ({name})", worst <= TOL, f"max abs diff {worst:.5f}")
        report(f"classification of {name}", classify_split(e) == expect[name], classify_split(e))
    s5 = truth[["row_id", "S5_cv"]].rename(columns={"S5_cv": "fold"})
    e5 = exposure(truth, s5[s5["fold"] >= 0])
    report("classification of S5", classify_split(e5) == "study_held_out", f"{classify_split(e5)}, same_study={e5['same_study']:.3f}")

    cb = shutil.which(args.claude_bin)
    if cb:
        print(f"[info] Claude Code CLI: {cb} ({claude_version(args.claude_bin)})")
    else:
        print("[warn] Claude Code CLI not found; use manual mode (01_prepare_workspace.py + 02_run_agent.py --snapshot) "
              "or pass --claude-bin")
    print(f"[info] agent subprocesses will use python3 from: {shutil.which('python3', path=python_dir_first_env()['PATH'])}")
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
