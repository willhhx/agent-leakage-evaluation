#!/usr/bin/env python3
"""Exact power of a two-sided Fisher exact test (alpha = 0.05) for comparing leaky-split shares between two conditions.

  python3 src/06_power.py            # table for C0 share 0.8 vs C1/C2 shares 0.6, 0.4, 0.2 at n = 5, 8, 10, 15, 20 per arm
  python3 src/06_power.py --p0 0.9 --n 10 --p1 0.5

Use it to decide how many trials per condition you can afford before the main run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def fisher_power(p0: float, p1: float, n0: int, n1: int, alpha: float = 0.05) -> float:
    pv = np.ones((n0 + 1, n1 + 1))
    for a in range(n0 + 1):
        for b in range(n1 + 1):
            pv[a, b] = stats.fisher_exact([[a, n0 - a], [b, n1 - b]])[1]
    w0 = stats.binom.pmf(np.arange(n0 + 1), n0, p0)
    w1 = stats.binom.pmf(np.arange(n1 + 1), n1, p1)
    return float((np.outer(w0, w1) * (pv <= alpha)).sum())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--p0", type=float, default=0.8)
    ap.add_argument("--p1", type=float, nargs="*", default=[0.6, 0.4, 0.2])
    ap.add_argument("--n", type=int, nargs="*", default=[5, 8, 10, 15, 20])
    args = ap.parse_args(argv)
    print(f"Share of leaky final splits: control (C0) = {args.p0}; power at alpha = 0.05, two-sided Fisher exact")
    print("n per arm " + "".join(f"  p1={p:.2f}" for p in args.p1))
    for n in args.n:
        print(f"{n:9d} " + "".join(f"  {fisher_power(args.p0, p, n, n):6.2f}" for p in args.p1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
