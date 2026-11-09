import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.stats_utils import bootstrap_ci, cliffs_delta, cohen_kappa, holm, mcnemar_exact, perm_chi2, pairwise_mwu


def synthetic_scores(n=10, seed=0):
    """C0 mostly leaky, C1 half, C2 mostly clean; phase 2 fixes some leaky trials."""
    rng = np.random.default_rng(seed)
    rows = []
    p_leaky = {"C0": 0.9, "C1": 0.5, "C2": 0.1}
    for c in ("C0", "C1", "C2"):
        for r in range(1, n + 1):
            leaky = rng.random() < p_leaky[c]
            fixed = leaky and rng.random() < (0.5 if c != "C0" else 0.3)
            for phase in (1, 2):
                lk = leaky if phase == 1 else (leaky and not fixed)
                typ = "random_like" if lk else ("group_held_out" if rng.random() < 0.8 else "study_held_out")
                auprc = (0.96 if lk else (0.85 if typ == "group_held_out" else 0.74)) + rng.normal(0, 0.01)
                rows.append({"run_id": f"{c}_r{r:02d}", "condition": c, "rep": r, "phase": phase, "contract_ok": True,
                             "split_type": typ, "leaky": lk, "study_exposed": typ != "study_held_out", "auprc": auprc,
                             "delta_vs_S1": auprc - 0.649, "delta_vs_base_S1": auprc - 0.85, "reported_gap": rng.normal(0, 0.005),
                             "reported_mismatch": False, "auprc_group_exposed": auprc if lk else np.nan,
                             "auprc_group_unexposed": 0.8 if lk else np.nan, "auprc_gap_group": (auprc - 0.8) if lk else np.nan,
                             "tx_mentions_leakage": rng.random() < 0.3, "tx_audit_similarity": rng.random() < 0.2,
                             "tx_audit_overlap": False, "tx_cost_usd": 1.0, "tx_num_turns": 10})
    return pd.DataFrame(rows)


class StatsTests(unittest.TestCase):
    def test_holm_monotone_and_bounded(self):
        adj = holm([0.01, 0.04, 0.03])
        self.assertEqual([round(x, 3) for x in adj], [0.03, 0.06, 0.06])

    def test_perm_chi2_detects_difference(self):
        _, p = perm_chi2(np.array([[9, 1], [5, 5], [1, 9]]), B=3000)
        self.assertLess(p, 0.01)
        _, p = perm_chi2(np.array([[5, 5], [5, 5], [5, 5]]), B=500)
        self.assertGreater(p, 0.9)

    def test_small_helpers(self):
        self.assertAlmostEqual(cliffs_delta([3, 4, 5], [0, 1, 2]), 1.0)
        self.assertAlmostEqual(cohen_kappa(np.array([1, 0, 1, 0]), np.array([1, 0, 1, 0])), 1.0)
        self.assertAlmostEqual(cohen_kappa(np.array([1, 1, 0, 0]), np.array([1, 0, 1, 0])), 0.0)
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertLess(mcnemar_exact(8, 0), 0.01)
        lo, hi = bootstrap_ci(np.arange(100.0), B=2000)
        self.assertTrue(40 < lo < 50 < hi < 60)
        rows = pairwise_mwu({"a": np.array([1.0, 1, 1]), "b": np.array([1.0, 1, 1]), "c": np.array([5.0, 6, 7])})
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["p"], 1.0)  # identical constant groups do not crash


class AnalyzeTests(unittest.TestCase):
    def test_end_to_end(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("analyze", Path(__file__).resolve().parents[1] / "src" / "05_analyze.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as d:
            scores = Path(d) / "toy_run_scores.csv"
            synthetic_scores(12).to_csv(scores, index=False)
            self.assertEqual(mod.main(["--scores", str(scores), "--perm", "2000"]), 0)
            out = Path(d) / "analysis_toy"
            for f in ("summary.md", "fig1_split_types.png", "fig2_auprc.png", "fig3_paired_change.png", "t1_split_types.csv",
                      "t2_leaky_share_phase1.csv", "t2_leaky_pairwise_phase1.csv", "t3_auprc_excess_phase1.csv", "t6_self_correction.csv"):
                self.assertTrue((out / f).exists(), f)
            share = pd.read_csv(out / "t2_leaky_share_phase1.csv").set_index("condition")["share"]
            self.assertGreater(share["C0"], share["C2"])
            pw = pd.read_csv(out / "t2_leaky_pairwise_phase1.csv")
            row = pw[(pw.a == "C0") & (pw.b == "C2")].iloc[0]
            self.assertLess(row.p, 0.01)
            corr = pd.read_csv(out / "t6_self_correction.csv")
            self.assertIn("all", set(corr.condition))
            text = (out / "summary.md").read_text()
            self.assertIn("Primary outcome, phase 1", text)
            self.assertIn("Self-review prompt", text)

    def test_handles_missing_phase2_and_empty_condition(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("analyze", Path(__file__).resolve().parents[1] / "src" / "05_analyze.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        df = synthetic_scores(6)
        df = df[(df.phase == 1) & (df.condition != "C1")]
        with tempfile.TemporaryDirectory() as d:
            scores = Path(d) / "part_run_scores.csv"
            df.to_csv(scores, index=False)
            self.assertEqual(mod.main(["--scores", str(scores), "--perm", "200"]), 0)


if __name__ == "__main__":
    unittest.main()
