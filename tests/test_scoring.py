import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.common import load_truth, reference_values
from src.reference_baseline import evaluate
from src.runner import snapshot
from src.scoring import score_run, score_submission
from src.workspace import prepare_workspace
from tests import mock_agents as m


class ScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runs = Path(cls.tmp.name)
        cls.truth, cls.refs = load_truth(), reference_values()
        specs = {
            "random": ("C0", lambda w: m.random_kfold(w)),
            "holdout": ("C0", lambda w: m.random_holdout(w)),
            "peptide": ("C0", lambda w: m.grouped_kfold(w, "peptide")),
            "group": ("C2", lambda w: m.grouped_kfold(w, "group_id")),
            "study": ("C0", lambda w: m.grouped_kfold(w, "study")),
        }
        cls.sub, cls.res = {}, {}
        tmp0 = prepare_workspace("baseline", "C0", 0, cls.runs)
        b = evaluate(pd.read_csv(tmp0 / "work" / "data" / "dataset.csv.gz", low_memory=False), cls.truth).set_index("split")["auprc"]
        cls.refs.update({"base_S4": float(b["random"]), "base_S1": float(b["group"]), "base_S5": float(b["study"])})
        for name, (cond, fn) in specs.items():
            d = prepare_workspace(f"{name}", cond, 1, cls.runs)
            fn(d / "work")
            snapshot(d, 1)
            cls.sub[name] = d / "snapshots" / "phase1" / "submission"
            cls.res[name] = score_submission(cls.sub[name], cls.truth, cls.refs)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_split_types(self):
        got = {k: v["split_type"] for k, v in self.res.items()}
        self.assertEqual(got["random"], "random_like", got)
        self.assertEqual(got["holdout"], "random_like", got)
        self.assertEqual(got["peptide"], "peptide_dedup_only", got)
        self.assertEqual(got["group"], "group_held_out", got)
        self.assertEqual(got["study"], "study_held_out", got)

    def test_exposure_values(self):
        r = self.res
        self.assertGreater(r["random"]["exp_same_leakage_group"], 0.6)
        self.assertEqual(r["group"]["exp_same_leakage_group"], 0.0)
        self.assertEqual(r["study"]["exp_same_study"], 0.0)
        self.assertEqual(r["peptide"]["exp_identical_peptide"], 0.0)
        self.assertGreater(r["peptide"]["exp_near_duplicate"], 0.2)
        self.assertEqual(r["holdout"]["n_folds"], 1)
        self.assertTrue(r["random"]["leaky"] and not r["group"]["leaky"])
        self.assertTrue(r["study"]["leaky"])  # study-held-out still shares leakage groups with training: group-leaky
        self.assertTrue(r["group"]["study_exposed"] and not r["study"]["study_exposed"])

    def test_performance_ordering_and_recompute(self):
        r = self.res
        self.assertGreater(r["random"]["auprc"], r["group"]["auprc"])
        self.assertGreater(r["group"]["auprc"], r["study"]["auprc"])
        # the mock agents use the baseline's own pipeline, so against the matching baseline split the excess is ~0
        self.assertLess(abs(r["group"]["delta_vs_base_S1"]), 0.005)
        self.assertLess(abs(r["study"]["delta_vs_base_S5"]), 0.005)
        self.assertLess(abs(r["random"]["delta_vs_base_S4"]), 0.02)
        # and a leaky split reads as inflated against the leakage-controlled baselines
        self.assertGreater(r["random"]["delta_vs_base_S1"], 0.05)
        self.assertGreater(r["random"]["delta_vs_base_S5"], 0.15)
        for v in r.values():
            self.assertTrue(v["contract_ok"], v["contract_errors"])
            self.assertAlmostEqual(v["auprc"], v["auprc_reported"], places=9)
            self.assertFalse(v["reported_mismatch"])

    def test_exposed_vs_unexposed_auprc(self):
        r = self.res
        self.assertEqual(r["group"]["n_group_exposed"], 0)  # nothing exposed under a group split
        self.assertTrue(pd.isna(r["group"]["auprc_group_exposed"]))
        self.assertGreater(r["random"]["n_group_exposed"], r["random"]["n_group_unexposed"])
        self.assertGreater(r["random"]["n_group_unexposed"], 1000)
        self.assertFalse(pd.isna(r["random"]["auprc_gap_group"]))

    def test_reported_mismatch_flagged(self):
        d = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(self.sub["random"], d / "s")
            p = d / "s" / "results.json"
            j = json.loads(p.read_text()); j["auprc"] = 0.5; p.write_text(json.dumps(j))
            v = score_submission(d / "s", self.truth, self.refs)
            self.assertTrue(v["reported_mismatch"])
            self.assertLess(v["reported_gap"], -0.1)
        finally:
            shutil.rmtree(d)

    def test_contract_failures(self):
        d = Path(tempfile.mkdtemp())
        try:
            for fname, mutate, expect in [
                ("predictions.csv", lambda p: p.unlink(), "missing predictions.csv"),
                ("split.csv", lambda p: p.write_text("row_id,fold\nNOPE,0\n"), "unknown row_id"),
                ("split.csv", lambda p: p.write_text(p.read_text() + "LCI000001,3\n"), "duplicate row_id"),
                ("predictions.csv", lambda p: p.write_text("row_id,score\nLCI000001,0.5\n"), "predictions cover"),
                ("results.json", lambda p: p.write_text("{not json"), "unreadable"),
                ("split.csv", lambda p: p.write_text("a,b\n1,2\n"), "lacks column"),
            ]:
                if (d / "s").exists():
                    shutil.rmtree(d / "s")
                shutil.copytree(self.sub["random"], d / "s")
                mutate(d / "s" / fname)
                v = score_submission(d / "s", self.truth, self.refs)
                self.assertFalse(v["contract_ok"], expect)
                self.assertIn(expect, v["contract_errors"])
                self.assertEqual(v["split_type"], "invalid")
        finally:
            shutil.rmtree(d)

    def test_score_run_two_phases(self):
        d = self.runs / "random"
        snapshot(d, 2)  # identical phase 2
        (d / "transcript_phase1.jsonl").write_text("")
        rows = score_run(d, self.truth, self.refs)
        self.assertEqual([r["phase"] for r in rows], [1, 2])
        self.assertFalse(rows[1]["split_changed_from_phase1"])
        self.assertEqual(rows[0]["condition"], "C0")


if __name__ == "__main__":
    unittest.main()
