"""Measure how exposed held-out rows are to their training rows, and classify a split from that measurement.

The exposure vectors and the similarity definition mirror the LCI-IEDB v1.0 release (src/evaluation/13_leakage_exposure.py
and src/utilities/peptide_sim.py), re-implemented here so this study does not import release code. Tests check that the
numbers reproduce the release's own S1 and S4 values.

Similarity of two peptides = best ungapped identity over shifts -3..3, divided by the longer length (a 9-mer nested in a
10-mer scores 0.9). Near-duplicate means similarity >= 0.8.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from .common import EXPOSURE_TOL, STUDY_TOL

AA20 = "ACDEFGHIKLMNPQRSTVWY"
AA_INDEX = {c: i for i, c in enumerate(AA20)}
MAX_LEN = 11
OFFSETS = (-3, -2, -1, 0, 1, 2, 3)
RELEASE_VECTORS = ("identical_peptide", "near_duplicate", "same_leakage_group", "same_allele", "same_taxon_group", "same_study")
# same_study_any: the held-out row cites any reference that also supports a training row (stricter than the release's
# first-reference definition; reported for transparency, not used to classify).
VECTORS = RELEASE_VECTORS + ("same_study_any",)


def _encode(peps: Sequence[str]) -> np.ndarray:
    out = np.full((len(peps), MAX_LEN), -1, dtype=np.int8)
    for r, p in enumerate(peps):
        if len(p) > MAX_LEN:
            raise ValueError(f"peptide longer than {MAX_LEN}: {p}")
        out[r, : len(p)] = [AA_INDEX[c] for c in p]
    return out


def _onehot(codes: np.ndarray, shift: int = 0) -> np.ndarray:
    n = codes.shape[0]
    oh = np.zeros((n, MAX_LEN, len(AA20)), dtype=np.float32)
    for i in range(MAX_LEN):
        j = i + shift
        if 0 <= j < MAX_LEN:
            col = codes[:, j]
            ok = col >= 0
            oh[np.nonzero(ok)[0], i, col[ok]] = 1.0
    return oh.reshape(n, MAX_LEN * len(AA20))


def max_similarity(queries: Sequence[str], targets: Sequence[str], block: int = 500) -> np.ndarray:
    """Max similarity of each query peptide to any target peptide (0 if there are no targets)."""
    queries, targets = list(queries), list(targets)
    best = np.zeros(len(queries))
    if not targets or not queries:
        return best
    tc = _encode(targets)
    tlen = (tc >= 0).sum(axis=1)
    shifted = {d: _onehot(tc, d).T.copy() for d in OFFSETS}
    qc = _encode(queries)
    qlen = (qc >= 0).sum(axis=1)
    for s in range(0, len(queries), block):
        e = min(s + block, len(queries))
        q = _onehot(qc[s:e])
        counts = None
        for d in OFFSETS:
            c = q @ shifted[d]
            counts = c if counts is None else np.maximum(counts, c, out=counts)
        maxlen = np.maximum(qlen[s:e, None], tlen[None, :]).astype(np.float64)
        best[s:e] = (counts / maxlen).max(axis=1)
    return best


def naive_similarity(a: str, b: str) -> float:
    """Slow reference implementation used by the tests."""
    best = 0
    for d in OFFSETS:
        m = sum(1 for i in range(len(a)) if 0 <= i + d < len(b) and a[i] == b[i + d])
        best = max(best, m)
    return best / max(len(a), len(b))


def exposure(truth: pd.DataFrame, split: pd.DataFrame, return_rows: bool = False):
    """Exposure of held-out rows to the training rows of their own fold.

    ``split`` has columns row_id and fold. fold == "train" rows are never held out; every other fold value is a held-out
    set, and the training rows for that fold are all listed rows whose fold differs (so K-fold CV and a single hold-out
    both work). Rows missing from ``split`` are unused. Returns pooled fractions over held-out rows, plus counts.
    With ``return_rows=True`` returns (summary, per-row DataFrame with boolean columns row_exposed_group / _near_dup /
    _identical for every held-out row).
    """
    s = split[["row_id", "fold"]].copy()
    s["fold"] = s["fold"].astype(str)
    t = truth.merge(s, on="row_id", how="inner")
    ref_src = t["reference_ids"] if "reference_ids" in t.columns else t["study"]
    t["refs"] = ref_src.fillna("").str.split(";").map(lambda l: frozenset(x for x in l if x))
    held = t[t["fold"] != "train"]
    folds = sorted(held["fold"].unique())
    acc = {k: [] for k in VECTORS}  # list of (n_eligible, n_exposed)
    n_train = []
    row_parts = []
    for f in folds:
        te = t[t["fold"] == f]
        tr = t[t["fold"] != f]
        n_train.append(len(tr))
        if len(tr) == 0 or len(te) == 0:
            continue
        ms = max_similarity(te["peptide"].tolist(), sorted(set(tr["peptide"])))
        acc["identical_peptide"].append((len(te), int((ms >= 1 - 1e-9).sum())))
        acc["near_duplicate"].append((len(te), int((ms >= 0.8 - 1e-9).sum())))
        in_group = te["group_id"].isin(set(tr["group_id"])).to_numpy()
        acc["same_leakage_group"].append((len(te), int(in_group.sum())))
        row_parts.append(pd.DataFrame({"row_id": te["row_id"].to_numpy(), "row_exposed_group": in_group,
                                       "row_exposed_near_dup": ms >= 0.8 - 1e-9, "row_exposed_identical": ms >= 1 - 1e-9}))
        acc["same_allele"].append((len(te), int(te["allele"].isin(set(tr["allele"])).sum())))
        ok_t = te["taxon_group"] != "unspecified"
        acc["same_taxon_group"].append((int(ok_t.sum()), int((te.loc[ok_t, "taxon_group"].isin(set(tr["taxon_group"]))).sum())))
        ok_s = te["study"] != ""
        studies = set(tr["study"]) - {""}
        acc["same_study"].append((int(ok_s.sum()), int(te.loc[ok_s, "study"].isin(studies).sum())))
        tr_refs = set().union(*tr["refs"]) if len(tr) else set()
        ok_a = te["refs"].map(len) > 0
        acc["same_study_any"].append((int(ok_a.sum()), int(te.loc[ok_a, "refs"].map(lambda r: bool(r & tr_refs)).sum())))
    out = {"n_heldout": int(len(held)), "n_folds": len(folds), "n_train_mean": float(np.mean(n_train)) if n_train else 0.0}
    for k, pairs in acc.items():
        n = sum(p[0] for p in pairs)
        out[k] = (sum(p[1] for p in pairs) / n) if n else float("nan")
    if return_rows:
        rows = pd.concat(row_parts, ignore_index=True) if row_parts else pd.DataFrame(
            columns=["row_id", "row_exposed_group", "row_exposed_near_dup", "row_exposed_identical"])
        return out, rows
    return out


def classify_split(exp: dict, tol: float = EXPOSURE_TOL, study_tol: float = STUDY_TOL) -> str:
    """Name the split by which leakage vectors it controls (at most tol of held-out rows exposed).

    group_and_study_held_out  no shared leakage group and (first-reference) study shared with training
    group_held_out            no shared leakage group, studies still shared (S1-like)
    study_held_out            studies not shared, leakage groups still shared (S5-like)
    similarity_aware          near-duplicates controlled, leakage groups still shared (S2-like)
    peptide_dedup_only        identical peptides controlled, near-duplicates remain
    random_like               none of the above (S4-like)
    """
    if exp.get("n_heldout", 0) == 0 or exp.get("n_train_mean", 0) == 0:
        return "invalid"
    g = exp["same_leakage_group"] <= tol
    s = exp["same_study"] <= study_tol
    if g and s:
        return "group_and_study_held_out"
    if g:
        return "group_held_out"
    if s:
        return "study_held_out"
    if exp["near_duplicate"] <= tol:
        return "similarity_aware"
    if exp["identical_peptide"] <= tol:
        return "peptide_dedup_only"
    return "random_like"
