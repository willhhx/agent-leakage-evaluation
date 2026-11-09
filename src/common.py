"""Shared constants and helpers for the agent-leakage evaluation study.

Everything that defines the experiment (conditions, thresholds, sanitised columns, reference values) lives here so the
runner, scorer and analysis cannot drift apart.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ENV = "LCI_IEDB_RELEASE"
# Default: the LCI-IEDB repo cloned as a sibling folder "lci-iedb" (override with LCI_IEDB_RELEASE).
DEFAULT_RELEASE = PROJECT_ROOT.parent / "lci-iedb" / "data" / "release" / "LCI-IEDB_v1.0"

PRIMARY_FILE = "LCI-IEDB_v1.0_primary_P_vs_N2.csv.gz"
GROUPS_FILE = "LCI-IEDB_v1.0_leakage_groups.csv.gz"
S5_FILE = "LCI-IEDB_v1.0_split_S5_study_heldout.csv.gz"
SPLITS_FILE = "LCI-IEDB_v1.0_splits_all_tiers.csv.gz"
RES_EXPOSURE = "metadata/results/leakage_exposure_all.csv"
RES_METRICS = "metadata/results/metrics_overall_all.csv"
RES_STUDY = "metadata/results/study_heldout_N2.csv"
RELEASE_FILES_USED = [PRIMARY_FILE, GROUPS_FILE, S5_FILE, SPLITS_FILE, RES_EXPOSURE, RES_METRICS, RES_STUDY]

# ---- experiment definition ---------------------------------------------------------------------------------------
CONDITIONS = ("C0", "C1", "C2")
CONDITION_LABELS = {"C0": "C0 minimal", "C1": "C1 generic warning", "C2": "C2 tool-assisted"}
# Columns removed from the table the agents see. They are label-derived (only defined for one class, or computed from the
# labels), so keeping them would add a second, unrelated kind of leakage. Everything else, including reference_ids and
# parent protein columns, is left in exactly as released: the question is whether the agent notices the structure.
DROP_COLUMNS = [
    "tier", "n2_confidence", "negative_replicated", "mixed_within_study", "max_positive_strength",
    "peptide_label_ambiguous", "matched_pair_id", "match_level", "n3_evidence", "binding_log10nM", "binding_source",
    "delta_binding", "delta_start",
]

# Split classification from measured exposure of held-out rows to the training rows of their fold.
EXPOSURE_TOL = 0.05  # a vector counts as "controlled" when at most 5% of held-out rows are exposed to it
# Study exposure uses the release's own definition (same first IEDB reference). Rows can cite several references, so an agent
# that groups by every PubMed id can still show a few percent of first-reference overlap; hence the wider tolerance.
STUDY_TOL = 0.10
SPLIT_TYPES = ("group_and_study_held_out", "group_held_out", "study_held_out", "similarity_aware", "peptide_dedup_only",
               "random_like", "invalid")
SPLIT_TYPE_LABELS = {
    "group_and_study_held_out": "Leakage groups and studies held out", "group_held_out": "Leakage groups held out (studies shared)",
    "study_held_out": "Studies held out (groups shared)", "similarity_aware": "Near-duplicates controlled only",
    "peptide_dedup_only": "Identical peptides removed only", "random_like": "Random-like",
    "invalid": "Invalid / not scorable",
}
# "Group-leaky" (primary outcome): more than EXPOSURE_TOL of held-out rows share a leakage group with training rows.
# Equivalent to the split type being any of these.
LEAKY_TYPES = ("study_held_out", "similarity_aware", "peptide_dedup_only", "random_like")

# Reference AUPRC values come from the release itself (GBM, primary P vs N2). See reference_values().
REFERENCE_MODEL = "GBM"

# ---- file helpers ------------------------------------------------------------------------------------------------

def release_dir() -> Path:
    p = Path(os.environ.get(RELEASE_ENV, DEFAULT_RELEASE)).expanduser()
    if not (p / PRIMARY_FILE).exists():
        raise FileNotFoundError(f"LCI-IEDB release not found at {p}. Set {RELEASE_ENV} to the LCI-IEDB_v1.0 folder.")
    return p


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_sha256sums(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+\*?(.+)$", line.strip())
        if m:
            out[m.group(2)] = m.group(1)
    return out


def verify_release(rel: Path | None = None, files=RELEASE_FILES_USED) -> dict[str, str]:
    """Check the files this study uses against the release's SHA256SUMS.txt; return {file: sha256}. Raises on mismatch."""
    rel = rel or release_dir()
    sums = parse_sha256sums(rel / "SHA256SUMS.txt")
    got = {}
    for f in files:
        if f not in sums:
            raise ValueError(f"{f} is not listed in SHA256SUMS.txt")
        digest = sha256_file(rel / f)
        if digest != sums[f]:
            raise ValueError(f"checksum mismatch for {f}: release says {sums[f][:12]}..., file is {digest[:12]}...")
        got[f] = digest
    return got


def load_primary(rel: Path | None = None) -> pd.DataFrame:
    rel = rel or release_dir()
    return pd.read_csv(rel / PRIMARY_FILE, low_memory=False)


def load_truth(rel: Path | None = None) -> pd.DataFrame:
    """Ground-truth table used only by the scorer: labels plus leakage group, study unit, allele, taxon group."""
    rel = rel or release_dir()
    d = load_primary(rel)
    g = pd.read_csv(rel / GROUPS_FILE, usecols=["row_id", "group_id"])
    s5 = pd.read_csv(rel / S5_FILE, usecols=["row_id", "S5_unit", "S5_cv"])
    t = d[["row_id", "peptide", "allele", "label", "taxon_group", "reference_ids"]].merge(g, on="row_id", how="left")
    t = t.merge(s5, on="row_id", how="left")
    t["study"] = t["reference_ids"].fillna("").str.split(";").str[0]
    if t["group_id"].isna().any():
        raise ValueError("some primary rows have no leakage group")
    return t.reset_index(drop=True)


def reference_values(rel: Path | None = None) -> dict[str, float]:
    """Leakage-free and leaky reference AUPRC for the reference model (GBM), read from the release's own results."""
    rel = rel or release_dir()
    m = pd.read_csv(rel / RES_METRICS)
    m = m[(m["track"] == "all") & (m["tier"] == "N2") & (m["model"] == REFERENCE_MODEL)]
    get = lambda s: float(m.loc[m["split"] == s, "auprc"].iloc[0])
    st = pd.read_csv(rel / RES_STUDY)
    s5 = float(st.loc[(st["split"] == "S5") & (st["model"] == REFERENCE_MODEL), "auprc"].iloc[0])
    prev = float(m["prevalence"].iloc[0])
    refs = {"S4_random": get("S4"), "S1_group": get("S1"), "S5_study": s5, "chance": prev}
    base = PROJECT_ROOT / "results" / "reference_baseline.csv"  # made by 07_reference_baseline.py (agent-facing features)
    if base.exists():
        b = pd.read_csv(base).set_index("split")["auprc"]
        refs.update({"base_S4": float(b["random"]), "base_S1": float(b["group"]), "base_S5": float(b["study"])})
    return refs


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str))


def read_json(path: Path):
    return json.loads(Path(path).read_text())


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def python_dir_first_env() -> dict[str, str]:
    """Environment for agent subprocesses: this interpreter's bin dir first on PATH so `python3` is the one tested here."""
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env
