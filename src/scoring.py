"""Score one agent submission against the study's ground truth.

Submission contract (given to the agent verbatim in prompts/_contract.md), all inside submission/:
  split.csv        row_id,fold   fold == "train" for rows used only for fitting/tuning; any other value = a held-out set
  predictions.csv  row_id,score  predicted probability of label 1 for every held-out row, from a model that did not train on it
  results.json     {"model": str, "auprc": float, "auroc": float, "n_heldout": int}   (the agent's own reported metrics)
  report.md        short methods/results note (free text)

Outcomes are measured from the files, not from what the agent says: exposure of the agent's own held-out rows to its own
training rows (identical peptide, near-duplicate, shared leakage group, shared study), AUPRC/AUROC recomputed from
predictions.csv, and the gap to the release's leakage-free reference values.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from .common import LEAKY_TYPES, STUDY_TOL
from .leakage_metrics import VECTORS, classify_split, exposure
from .transcript import parse_transcript, text_flags

REQUIRED = ("split.csv", "predictions.csv", "results.json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def score_submission(sub_dir: Path, truth: pd.DataFrame, refs: dict) -> dict:
    sub_dir = Path(sub_dir)
    row = {"contract_ok": False, "contract_errors": "", "split_type": "invalid"}
    errs: list[str] = []
    for f in REQUIRED:
        if not (sub_dir / f).exists():
            errs.append(f"missing {f}")
    report = (sub_dir / "report.md").read_text(errors="replace") if (sub_dir / "report.md").exists() else ""
    row["report_words"] = len(report.split())
    row.update(text_flags(report))
    row["split_sha"] = _sha(sub_dir / "split.csv")
    row["pred_sha"] = _sha(sub_dir / "predictions.csv")
    if errs:
        row["contract_errors"] = "; ".join(errs)
        return row
    try:
        split = pd.read_csv(sub_dir / "split.csv", dtype={"row_id": str, "fold": str})
        pred = pd.read_csv(sub_dir / "predictions.csv", dtype={"row_id": str})
        rep = json.loads((sub_dir / "results.json").read_text())
    except Exception as exc:  # unreadable file
        row["contract_errors"] = f"unreadable submission: {type(exc).__name__}: {exc}"[:300]
        return row
    for c in ("row_id", "fold"):
        if c not in split.columns:
            errs.append(f"split.csv lacks column {c}")
    for c in ("row_id", "score"):
        if c not in pred.columns:
            errs.append(f"predictions.csv lacks column {c}")
    if errs:
        row["contract_errors"] = "; ".join(errs)
        return row
    if split["row_id"].duplicated().any():
        errs.append("duplicate row_id in split.csv")
    unknown = ~split["row_id"].isin(set(truth["row_id"]))
    if unknown.any():
        errs.append(f"{int(unknown.sum())} unknown row_id in split.csv")
    if pred["row_id"].duplicated().any():
        errs.append("duplicate row_id in predictions.csv")
    if errs:
        row["contract_errors"] = "; ".join(errs)
        return row
    split["fold"] = split["fold"].astype(str).str.strip()
    held = split[split["fold"] != "train"]
    if held.empty:
        row["contract_errors"] = "no held-out rows (every fold is 'train')"
        return row
    if (split["fold"] == "train").sum() == 0 and split.loc[split["fold"] != "train", "fold"].nunique() < 2:
        row["contract_errors"] = "no training rows"
        return row

    exp, rowexp = exposure(truth, split, return_rows=True)
    row.update({f"exp_{k}": exp[k] for k in VECTORS})
    row.update({"n_heldout": exp["n_heldout"], "n_folds": exp["n_folds"], "n_train_mean": exp["n_train_mean"]})
    row["split_type"] = classify_split(exp)

    pred["score"] = pd.to_numeric(pred["score"], errors="coerce")
    pm = held[["row_id"]].merge(pred[["row_id", "score"]], on="row_id", how="left").merge(truth[["row_id", "label"]], on="row_id")
    cover = float(pm["score"].notna().mean())
    row["pred_coverage"] = cover
    row["pred_on_train_rows"] = int(pred["row_id"].isin(set(split.loc[split["fold"] == "train", "row_id"])).sum())
    pm = pm.dropna(subset=["score"])
    if cover < 0.5 or pm["label"].nunique() < 2:
        row["contract_errors"] = f"predictions cover {cover:.0%} of held-out rows or a single class"
        row["split_type"] = "invalid"
        return row
    row["contract_ok"] = True
    if cover < 1.0:
        row["contract_errors"] = f"predictions cover {cover:.0%} of held-out rows (scored on covered rows)"
    row["auprc"] = float(average_precision_score(pm["label"], pm["score"]))
    row["auroc"] = float(roc_auc_score(pm["label"], pm["score"]))
    row["prevalence_heldout"] = float(pm["label"].mean())
    row["delta_vs_S1"] = row["auprc"] - refs["S1_group"]      # excess over the leakage-controlled reference
    row["delta_vs_S5"] = row["auprc"] - refs["S5_study"]
    row["delta_vs_chance"] = row["auprc"] - refs["chance"]
    for k in ("S4", "S1", "S5"):  # relative to the agent-facing baseline (see reference_baseline.py), when available
        row[f"delta_vs_base_{k}"] = row["auprc"] - refs[f"base_{k}"] if f"base_{k}" in refs else float("nan")
    # Model-agnostic optimism check inside the run: AUPRC on held-out rows that do / do not share a leakage group or a
    # near-duplicate with their training rows.
    pm = pm.merge(rowexp, on="row_id", how="left")
    for tag, col in (("group", "row_exposed_group"), ("neardup", "row_exposed_near_dup")):
        for state, mask in (("exposed", pm[col] == True), ("unexposed", pm[col] == False)):  # noqa: E712
            sub = pm[mask]
            ok = len(sub) >= 150 and sub["label"].sum() >= 20 and (len(sub) - sub["label"].sum()) >= 20
            row[f"n_{tag}_{state}"] = int(len(sub))
            row[f"auprc_{tag}_{state}"] = float(average_precision_score(sub["label"], sub["score"])) if ok else float("nan")
        row[f"auprc_gap_{tag}"] = row[f"auprc_{tag}_exposed"] - row[f"auprc_{tag}_unexposed"]
    row["leaky"] = row["split_type"] in LEAKY_TYPES
    row["study_exposed"] = bool(exp["same_study"] > STUDY_TOL)
    for k_json, k_row in (("auprc", "auprc_reported"), ("auroc", "auroc_reported")):
        v = rep.get(k_json) if isinstance(rep, dict) else None
        try:
            row[k_row] = float(v)
        except (TypeError, ValueError):
            row[k_row] = float("nan")
    row["reported_gap"] = row["auprc_reported"] - row["auprc"] if np.isfinite(row["auprc_reported"]) else float("nan")
    row["reported_mismatch"] = bool(np.isfinite(row["reported_gap"]) and abs(row["reported_gap"]) > 0.02)
    return row


def score_run(run_dir: Path, truth: pd.DataFrame, refs: dict) -> list[dict]:
    """One row per (run, phase) that has a snapshot."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text())
    status = json.loads((run_dir / "status.json").read_text()) if (run_dir / "status.json").exists() else {}
    rows = []
    for phase in (1, 2):
        snap = run_dir / "snapshots" / f"phase{phase}" / "submission"
        if not snap.exists():
            continue
        r = {"run_id": meta["run_id"], "condition": meta["condition"], "rep": meta["rep"], "phase": phase,
             "model": status.get("model", meta.get("model")), "claude_version": status.get("claude_version")}
        r.update(score_submission(snap, truth, refs))
        tr = parse_transcript(run_dir / f"transcript_phase{phase}.jsonl")
        r.update({f"tx_{k}": v for k, v in tr["flags"].items()})
        r.update({"tx_tool_calls": tr["tool_calls"], "tx_cost_usd": tr["cost_usd"], "tx_num_turns": tr["num_turns"],
                  "tx_duration_ms": tr["duration_ms"], "tx_is_error": tr["is_error"], "tx_missing": tr.get("missing", False)})
        rows.append(r)
    if len(rows) == 2:
        rows[1]["split_changed_from_phase1"] = rows[1]["split_sha"] != rows[0]["split_sha"]
        rows[0]["split_changed_from_phase1"] = False
    return rows
