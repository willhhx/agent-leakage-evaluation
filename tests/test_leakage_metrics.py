import os
import random
import unittest

import pandas as pd

from src.leakage_metrics import classify_split, exposure, max_similarity, naive_similarity


class SimilarityTests(unittest.TestCase):
    def test_matches_naive_on_random_peptides(self):
        rnd = random.Random(1)
        aa = "ACDEFGHIKLMNPQRSTVWY"
        q = ["".join(rnd.choice(aa) for _ in range(rnd.randint(8, 11))) for _ in range(40)]
        t = ["".join(rnd.choice(aa) for _ in range(rnd.randint(8, 11))) for _ in range(60)]
        t += [q[0], q[1][1:], q[2][:-1] + "A"]  # identical, nested, near-duplicate
        fast = max_similarity(q, t)
        slow = [max(naive_similarity(a, b) for b in t) for a in q]
        for f, s in zip(fast, slow):
            self.assertAlmostEqual(f, s, places=6)

    def test_known_values(self):
        self.assertAlmostEqual(max_similarity(["AAAAAAAAA"], ["AAAAAAAAAA"])[0], 0.9)       # 9-mer nested in 10-mer
        self.assertAlmostEqual(max_similarity(["AAAAAAAAA"], ["AAAAAAAAC"])[0], 8 / 9)      # single substitution
        self.assertAlmostEqual(max_similarity(["ACDEFGHIK"], ["ACDEFGHIK"])[0], 1.0)
        self.assertEqual(max_similarity(["ACDEFGHIK"], [])[0], 0.0)


def toy_truth():
    return pd.DataFrame({
        "row_id": [f"r{i}" for i in range(8)],
        "peptide": ["AAAAAAAAA", "AAAAAAAAC", "CCCCCCCCC", "DDDDDDDDD", "EEEEEEEEE", "FFFFFFFFF", "GGGGGGGGG", "HHHHHHHHH"],
        "allele": ["a1", "a1", "a2", "a2", "a1", "a1", "a2", "a2"],
        "label": [1, 0, 1, 0, 1, 0, 1, 0],
        "taxon_group": ["x", "x", "y", "y", "unspecified", "z", "z", "y"],
        "group_id": [0, 0, 1, 2, 3, 4, 5, 6],
        "study": ["s1", "s1", "s2", "s2", "", "s3", "s3", "s4"],
    })


class ExposureTests(unittest.TestCase):
    def test_hand_computed(self):
        t = toy_truth()
        # hold out r1 (AAAAAAAAC): near-duplicate of r0 (train), same group, same study, same allele
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["train", "test"] + ["train"] * 6})
        e = exposure(t, split.iloc[[0, 1, 2, 3]])  # only r0..r3 used
        self.assertEqual(e["n_heldout"], 1)
        self.assertEqual(e["near_duplicate"], 1.0)
        self.assertEqual(e["identical_peptide"], 0.0)
        self.assertEqual(e["same_leakage_group"], 1.0)
        self.assertEqual(e["same_study"], 1.0)
        self.assertEqual(classify_split(e), "peptide_dedup_only")  # near-duplicate present, identical peptide absent

    def test_random_like_needs_identical_peptide(self):
        t = toy_truth()
        t.loc[1, "peptide"] = "AAAAAAAAA"  # same string as r0 (different allele row)
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["train", "test", "train", "train"] + ["train"] * 4})
        e = exposure(t, split)
        self.assertEqual(e["identical_peptide"], 1.0)
        self.assertEqual(classify_split(e), "random_like")

    def test_similarity_aware(self):
        t = toy_truth()
        t.loc[1, "group_id"] = 0
        t.loc[1, "peptide"] = "WWWWWWWWW"  # no near-duplicate in train, but still shares group 0 with r0
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["train", "test"] + ["train"] * 6})
        e = exposure(t, split)
        self.assertEqual((e["near_duplicate"], e["same_leakage_group"]), (0.0, 1.0))
        self.assertEqual(classify_split(e), "similarity_aware")

    def test_group_held_out_and_study_held_out(self):
        t = toy_truth()
        # hold out the whole group {r0, r1}: nothing shared by group; study s1 also absent from train
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["test", "test"] + ["train"] * 6})
        e = exposure(t, split)
        self.assertEqual(e["same_leakage_group"], 0.0)
        self.assertEqual(e["same_study"], 0.0)
        self.assertEqual(classify_split(e), "group_and_study_held_out")
        # hold out r2 only: study s2 still present in r3 -> group controlled but study exposed
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["train", "train", "test"] + ["train"] * 5})
        e = exposure(t, split)
        self.assertEqual(e["same_leakage_group"], 0.0)
        self.assertEqual(e["same_study"], 1.0)
        self.assertEqual(classify_split(e), "group_held_out")

    def test_study_only_and_any_reference(self):
        t = toy_truth()
        t["study"] = ["s1", "s1", "s2", "s2", "", "s3", "s3", "s4"]
        t.loc[2, "reference_ids"] = "s2;s9"   # r2 also cites s9
        t["reference_ids"] = t["study"].where(t.index != 2, "s2;s9")
        t.loc[6, "reference_ids"] = "s3;s9"   # r6 (train) also cites s9
        # r2's group is shared with a training row (r4), so leakage groups stay exposed when r2 is held out
        t.loc[2, "group_id"] = 1
        t.loc[4, "group_id"] = 1
        t.loc[3, "group_id"] = 1
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["train", "train", "test", "train", "train", "train", "train", "train"]})
        e = exposure(t, split)
        self.assertEqual(e["same_leakage_group"], 1.0)
        self.assertEqual(e["same_study"], 1.0)        # first reference s2 is shared with r3
        self.assertEqual(e["same_study_any"], 1.0)
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["train", "train", "test", "test", "train", "train", "train", "train"]})
        e = exposure(t, split)
        self.assertEqual(e["same_study"], 0.0)        # s2 fully held out by first reference
        self.assertEqual(e["same_study_any"], 0.5)    # but r2 also cites s9, which r6 (train) cites
        self.assertEqual(classify_split(e), "study_held_out")

    def test_cv_uses_other_folds_as_training(self):
        t = toy_truth()
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["0", "1", "0", "1", "0", "1", "0", "1"]})
        e = exposure(t, split)
        self.assertEqual(e["n_folds"], 2)
        self.assertEqual(e["n_heldout"], 8)
        self.assertEqual(e["same_taxon_group"], e["same_taxon_group"])  # not nan

    def test_invalid_without_train(self):
        t = toy_truth()
        split = pd.DataFrame({"row_id": t["row_id"], "fold": ["test"] * 8})
        self.assertEqual(classify_split(exposure(t, split)), "invalid")


@unittest.skipUnless(os.environ.get("LCI_IEDB_RELEASE") or __import__("pathlib").Path(__file__).resolve().parents[2].joinpath("lci-iedb").exists(),
                     "LCI-IEDB release not available")
class ReleaseReproductionTests(unittest.TestCase):
    def test_reproduces_release_numbers(self):
        from src.common import RES_EXPOSURE, SPLITS_FILE, load_truth, release_dir
        from src.leakage_metrics import RELEASE_VECTORS as VECTORS
        rel = release_dir()
        truth = load_truth(rel)
        sp = pd.read_csv(rel / SPLITS_FILE, usecols=["row_id", "S1_cv", "S4_cv"])
        ref = pd.read_csv(rel / RES_EXPOSURE)
        for name in ("S1", "S4"):
            s = sp[["row_id", f"{name}_cv"]].rename(columns={f"{name}_cv": "fold"})
            e = exposure(truth, s[s["fold"] >= 0])
            for k in VECTORS:
                want = float(ref[(ref["split"] == name) & (ref["vector"] == k)]["fraction_exposed"].iloc[0])
                self.assertAlmostEqual(e[k], want, places=3, msg=f"{name} {k}")
        self.assertEqual(classify_split(exposure(truth, sp[["row_id", "S4_cv"]].rename(columns={"S4_cv": "fold"}))), "random_like")


if __name__ == "__main__":
    unittest.main()
