"""Mock agents that behave like the strategies the study measures. They read only what a real agent would see
(work/data/dataset.csv.gz, plus data/leakage_groups.csv.gz in C2) and write a real submission/ with a real model, so the
scoring pipeline is tested end to end on genuine predictions."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold, KFold

from src.reference_baseline import features  # noqa: E402  (mock agents use the baseline's feature set)


def _fit_predict(X, y, tr, te):
    m = HistGradientBoostingClassifier(max_iter=60, learning_rate=0.1, random_state=0,
                                       categorical_features=None)
    m.fit(X[tr], y[tr])
    return m.predict_proba(X[te])[:, 1]


def write_submission(work: Path, d: pd.DataFrame, folds: np.ndarray, *, report="Mock agent report.", model="mock"):
    """folds: array of str per row ('train' or a held-out label)."""
    from sklearn.metrics import average_precision_score, roc_auc_score
    X, y = features(d), d["label"].to_numpy()
    score = np.full(len(d), np.nan)
    for f in sorted(set(folds) - {"train"}):
        te = folds == f
        tr = ~te
        score[te] = _fit_predict(X, y, tr, te)
    held = folds != "train"
    sub = work / "submission"
    sub.mkdir(exist_ok=True, parents=True)
    pd.DataFrame({"row_id": d["row_id"], "fold": folds}).to_csv(sub / "split.csv", index=False)
    pd.DataFrame({"row_id": d.loc[held, "row_id"], "score": score[held]}).to_csv(sub / "predictions.csv", index=False)
    (sub / "results.json").write_text(json.dumps({
        "model": model, "auprc": float(average_precision_score(y[held], score[held])),
        "auroc": float(roc_auc_score(y[held], score[held])), "n_heldout": int(held.sum())}))
    (sub / "report.md").write_text(report)


def random_kfold(work: Path, k: int = 5):
    d = pd.read_csv(work / "data" / "dataset.csv.gz", low_memory=False)
    folds = np.empty(len(d), dtype=object)
    for i, (_, te) in enumerate(KFold(k, shuffle=True, random_state=0).split(d)):
        folds[te] = str(i)
    write_submission(work, d, folds, model="HistGB, random 5-fold CV")


def random_holdout(work: Path):
    d = pd.read_csv(work / "data" / "dataset.csv.gz", low_memory=False)
    rng = np.random.default_rng(0)
    folds = np.where(rng.random(len(d)) < 0.2, "test", "train").astype(object)
    write_submission(work, d, folds, model="HistGB, 80/20 holdout")


def grouped_kfold(work: Path, by: str, k: int = 5, report="Grouped CV used to avoid leakage."):
    d = pd.read_csv(work / "data" / "dataset.csv.gz", low_memory=False)
    if by == "group_id":
        g = pd.read_csv(work / "data" / "leakage_groups.csv.gz")
        groups = d[["row_id"]].merge(g, on="row_id")["group_id"].to_numpy()
    elif by == "peptide":
        groups = d["peptide"].to_numpy()
    elif by == "study":
        groups = d["reference_ids"].fillna("").str.split(";").str[0].to_numpy()
    else:
        raise ValueError(by)
    folds = np.empty(len(d), dtype=object)
    for i, (_, te) in enumerate(GroupKFold(k).split(d, groups=groups)):
        folds[te] = str(i)
    write_submission(work, d, folds, model=f"HistGB, GroupKFold by {by}", report=report)


def write_fake_transcript(path: Path, code: str, text: str = "", cost: float = 0.5):
    lines = [
        {"type": "system", "subtype": "init", "session_id": "sess-1", "model": "mock-model"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": text or "Working on it."},
                                                      {"type": "tool_use", "name": "Write", "input": {"file_path": "run.py", "content": code}}]}},
        {"type": "result", "subtype": "success", "session_id": "sess-1", "total_cost_usd": cost, "num_turns": 3,
         "duration_ms": 1000, "is_error": False, "result": text},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json at all\n")
