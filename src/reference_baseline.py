"""A fixed reference model on the table the agents actually see, evaluated three ways.

Why: the release's published reference numbers (GBM AUPRC 0.756 random / 0.649 group / 0.550 study) come from a
peptide-feature model. Agents see the full metadata table, and metadata (source organism, protein, study, assay) is itself
predictive, so "AUPRC above 0.649" would mix leakage with richer features. This baseline uses the agent-facing columns, so
its S4 / S1 / S5 numbers say what a typical agent pipeline scores with a random, leakage-group and study-held-out split.

Features: amino-acid composition + length + ordinal codes of the categorical columns + first_year. Model: histogram gradient
boosting. The random split is repeated over seeds; group and study splits use GroupKFold (deterministic).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold

AA = "ACDEFGHIKLMNPQRSTVWY"
CATS = ["allele", "category", "taxon_group", "species", "parent_name", "reference_ids", "methods", "responses",
        "effector_cells", "exposure_context", "mhc_evidence_class"]


def features(d: pd.DataFrame) -> np.ndarray:
    comp = np.array([[p.count(a) / len(p) for a in AA] for p in d["peptide"]])
    cat = np.column_stack([pd.factorize(d[c].fillna("NA"))[0] for c in CATS if c in d.columns])
    num = d[["length", "first_year"]].fillna(0).to_numpy(float)
    return np.hstack([comp, cat, num])


def oof_scores(X, y, folds: list[tuple[np.ndarray, np.ndarray]], seed: int = 0) -> np.ndarray:
    s = np.full(len(y), np.nan)
    for tr, te in folds:
        m = HistGradientBoostingClassifier(max_iter=60, learning_rate=0.1, random_state=seed)
        m.fit(X[tr], y[tr])
        s[te] = m.predict_proba(X[te])[:, 1]
    return s


def evaluate(agent_table: pd.DataFrame, truth: pd.DataFrame, seeds=(0, 1, 2)) -> pd.DataFrame:
    """agent_table = the dataset.csv.gz agents get; truth = scorer ground truth (group_id, study). Returns one row per split."""
    d = agent_table.merge(truth[["row_id", "group_id", "study"]], on="row_id", how="left")
    X, y = features(d), d["label"].to_numpy()
    rows = []
    rand = []
    for sd in seeds:
        folds = list(KFold(5, shuffle=True, random_state=sd).split(X))
        sc = oof_scores(X, y, folds, sd)
        rand.append((average_precision_score(y, sc), roc_auc_score(y, sc)))
    rows.append({"split": "random", "auprc": float(np.mean([r[0] for r in rand])), "auroc": float(np.mean([r[1] for r in rand])),
                 "n_seeds": len(seeds)})
    for name, key in (("group", "group_id"), ("study", "study")):
        folds = list(GroupKFold(5).split(X, groups=d[key].to_numpy()))
        sc = oof_scores(X, y, folds)
        rows.append({"split": name, "auprc": float(average_precision_score(y, sc)), "auroc": float(roc_auc_score(y, sc)), "n_seeds": 1})
    out = pd.DataFrame(rows)
    out["prevalence"] = float(y.mean())
    return out
