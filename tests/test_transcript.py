import json
import tempfile
import unittest
from pathlib import Path

from src.transcript import parse_transcript
from tests.mock_agents import write_fake_transcript


class TranscriptTests(unittest.TestCase):
    def test_flags_and_tolerance(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jsonl"
            write_fake_transcript(p, "from sklearn.model_selection import train_test_split\nGroupKFold(5)\n"
                                     "# check near-duplicate peptides shared between train and test", "Possible data leakage here.")
            r = parse_transcript(p)
            self.assertEqual(r["bad_lines"], 1)
            self.assertEqual(r["tool_calls"], 1)
            self.assertEqual(r["model"], "mock-model")
            self.assertEqual(r["session_id"], "sess-1")
            f = r["flags"]
            self.assertTrue(f["code_random_split"] and f["code_grouped_split"] and f["audit_similarity"])
            self.assertTrue(f["mentions_leakage"])
            self.assertFalse(f["escape_release_files"])

    def test_escape_detection_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jsonl"
            write_fake_transcript(p, "pd.read_csv('../lci-iedb/data/release/LCI-IEDB_v1.0/x.csv.gz')")
            f = parse_transcript(p)["flags"]
            self.assertTrue(f["escape_release_files"] and f["explored_parent_dirs"])
            self.assertTrue(parse_transcript(Path(d) / "nope.jsonl")["missing"])

    def test_plain_text_mention_not_in_code(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jsonl"
            write_fake_transcript(p, "model.fit(X, y)", "I will use a random split.")
            f = parse_transcript(p)["flags"]
            self.assertFalse(f["mentions_leakage"] or f["code_random_split"])


if __name__ == "__main__":
    unittest.main()
