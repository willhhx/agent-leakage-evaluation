import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.common import DROP_COLUMNS
from src.workspace import build_prompt, prepare_workspace


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runs = Path(cls.tmp.name)
        cls.dirs = {c: prepare_workspace(f"{c}_r01", c, 1, cls.runs) for c in ("C0", "C1", "C2")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_prompts_differ_only_by_addendum(self):
        p0, p1, p2 = (build_prompt(c, 12380) for c in ("C0", "C1", "C2"))
        self.assertIn("12,380", p0)
        self.assertNotIn("leak", p0.lower())
        self.assertNotIn("group", p0.lower())
        self.assertIn("avoid data leakage", p1)
        self.assertIn("leakage_groups.csv.gz", p2)
        for p in (p0, p1, p2):
            self.assertIn("submission/split.csv", p)
        self.assertTrue(set(p0.split("\n")) <= set(p1.split("\n")))
        self.assertTrue(set(p0.split("\n")) <= set(p2.split("\n")))

    def test_sanitised_data(self):
        for c, d in self.dirs.items():
            data = pd.read_csv(d / "work" / "data" / "dataset.csv.gz", low_memory=False)
            self.assertEqual(len(data), 12380)
            self.assertEqual(data["label"].sum(), 6675)
            self.assertFalse(set(DROP_COLUMNS) & set(data.columns))
            self.assertIn("reference_ids", data.columns)  # the study structure stays visible, as released
            dd = (d / "work" / "data" / "data_dictionary.csv").read_text().lower()
            self.assertNotIn("leak", dd)
            self.assertNotIn("split", dd)
            self.assertTrue(set(pd.read_csv(d / "work" / "data" / "data_dictionary.csv")["column"]) <= set(data.columns))

    def test_only_c2_gets_groups(self):
        for c, d in self.dirs.items():
            has = (d / "work" / "data" / "leakage_groups.csv.gz").exists()
            self.assertEqual(has, c == "C2", c)
            self.assertEqual((d / "work" / "data" / "README_groups.md").exists(), c == "C2")
            self.assertEqual({p.name for p in (d / "work" / "data").iterdir()} >= {"dataset.csv.gz", "data_dictionary.csv"}, True)
        g = pd.read_csv(self.dirs["C2"] / "work" / "data" / "leakage_groups.csv.gz")
        self.assertEqual(len(g), 12380)
        self.assertEqual(list(g.columns), ["row_id", "group_id"])

    def test_no_truth_files_in_workdir(self):
        for d in self.dirs.values():
            names = {p.name for p in (d / "work").rglob("*") if p.is_file()}
            self.assertFalse({n for n in names if "split" in n.lower() and n != "split.csv"})
            self.assertFalse(any("S5" in n for n in names))


if __name__ == "__main__":
    unittest.main()
