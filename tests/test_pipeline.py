"""End-to-end: batch runner -> fake claude CLI -> snapshots -> scoring -> analysis."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace(".py", "").replace("-", "_"), ROOT / "src" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runs = Path(cls.tmp.name) / "runs"
        import os
        cls.fake = str(ROOT / "tests" / "fake_claude.py")
        os.chmod(cls.fake, 0o755)  # permissions can be lost when the folder is copied
        cls.batch = load("03_run_batch.py")
        cls.rc = cls.batch.main(["--reps", "1", "--runs-dir", str(cls.runs), "--claude-bin", cls.fake, "--model", "sonnet",
                                 "--seed", "7"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_batch_ran_and_wrote_artifacts(self):
        self.assertEqual(self.rc, 0)
        sched = pd.read_csv(self.runs / "schedule.csv")
        self.assertEqual(sorted(sched["condition"]), ["C0", "C1", "C2"])
        for rid in sched["run_id"]:
            d = self.runs / rid
            for f in ("meta.json", "status.json", "prompt_phase1.md", "prompt_phase2.md", "transcript_phase1.jsonl",
                      "transcript_phase2.jsonl", "fake_args_1.json", "fake_args_2.json"):
                self.assertTrue((d / f).exists(), f"{rid}/{f}")
            for ph in (1, 2):
                self.assertTrue((d / "snapshots" / f"phase{ph}" / "submission" / "predictions.csv").exists())
            st = json.loads((d / "status.json").read_text())
            self.assertTrue(st["phase1_done"] and st["phase2_done"])
            self.assertEqual(st["claude_version"], "0.0.0-fake (Claude Code)")
            a2 = json.loads((d / "fake_args_2.json").read_text())
            self.assertEqual(a2[a2.index("--resume") + 1], st["session_id"])
            self.assertNotIn("--session-id", a2)
            self.assertEqual((d / "snapshots" / "phase1" / "code" / "agent_code.py").exists(), True)

    def test_resume_is_idempotent(self):
        before = {p: p.stat().st_mtime_ns for p in self.runs.glob("*/status.json")}
        self.assertEqual(self.batch.main(["--reps", "1", "--runs-dir", str(self.runs), "--claude-bin", "/nonexistent", "--seed", "7"]), 0)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.runs.glob("*/status.json")})
        sched = self.batch.make_schedule(3, 7)
        self.assertTrue(all(sorted(g["condition"]) == ["C0", "C1", "C2"] for _, g in sched.groupby("rep")))  # blocked
        self.assertEqual(sched.to_dict(), self.batch.make_schedule(3, 7).to_dict())  # seeded

    def test_scoring_and_analysis(self):
        score = load("04_score_runs.py")
        out = Path(self.tmp.name) / "scores.csv"
        self.assertEqual(score.main(["--runs-dir", str(self.runs), "--out", str(out), "--label-sheet"]), 0)
        df = pd.read_csv(out)
        self.assertEqual(len(df), 6)
        p1 = df[df.phase == 1].set_index("condition")
        p2 = df[df.phase == 2].set_index("condition")
        for c in ("C0", "C1", "C2"):
            self.assertEqual(p1.loc[c, "split_type"], "random_like")
            self.assertTrue(p1.loc[c, "tx_code_random_split"])
        self.assertEqual(p2.loc["C2", "split_type"], "group_held_out")   # C2 agent fixed its split after review
        self.assertEqual(p2.loc["C0", "split_type"], "random_like")      # C0 agent had no groups and changed nothing
        self.assertTrue(p2.loc["C2", "split_changed_from_phase1"])
        self.assertFalse(p2.loc["C0", "split_changed_from_phase1"])
        self.assertTrue(p2.loc["C2", "tx_mentions_leakage"])
        self.assertTrue(p2.loc["C2", "tx_used_provided_groups"] or p2.loc["C2", "tx_code_grouped_split"])
        self.assertFalse(df["tx_escape_release_files"].any())
        self.assertTrue((ROOT / "labels" / f"{self.runs.name}_label_sheet.csv").exists())
        (ROOT / "labels" / f"{self.runs.name}_label_sheet.csv").unlink()
        an = load("05_analyze.py")
        self.assertEqual(an.main(["--scores", str(out), "--perm", "300"]), 0)
        self.assertTrue((Path(self.tmp.name) / "analysis_scores".replace("scores", "scores") / "summary.md").exists()
                        or any(Path(self.tmp.name).glob("analysis_*/summary.md")))


if __name__ == "__main__":
    unittest.main()
