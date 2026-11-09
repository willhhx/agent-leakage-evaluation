"""Build the sandbox an agent works in, and assemble the prompts for each condition.

runs/<run_id>/
  meta.json                     condition, replicate, release checksums, dropped columns, prompt hashes
  prompt_phase1.md / prompt_phase2.md
  work/                         the agent's working directory (data/ + submission/ + whatever code it writes)
  transcript_phase{1,2}.jsonl   raw stream-json from the agent
  snapshots/phase{1,2}/         copy of submission/ and the agent's code after each phase
  status.json                   written by the runner
The ground truth (leakage groups, study ids, splits) is never copied into work/ except, for condition C2 only, the
curators' leakage_groups.csv.gz and a README explaining it.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pandas as pd

from .common import (CONDITIONS, DROP_COLUMNS, GROUPS_FILE, PRIMARY_FILE, PROJECT_ROOT, SPLITS_FILE, release_dir,
                     sha256_file, verify_release, write_json)

PROMPT_DIR = PROJECT_ROOT / "prompts"


def _read(name: str) -> str:
    return (PROMPT_DIR / name).read_text().strip()


def build_prompt(condition: str, n_rows: int) -> str:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition}")
    parts = [_read("base_task.md").replace("<<N_ROWS>>", f"{n_rows:,}")]
    f = PROMPT_DIR / f"{condition.lower()}_addendum.md"  # C0 has none: it is the task alone
    add = f.read_text().strip() if f.exists() else ""
    if add:
        parts.append(add)
    parts.append(_read("contract.md"))
    return "\n\n".join(parts) + "\n"


def followup_prompt() -> str:
    return _read("followup_review.md") + "\n"


def group_readme(n_rows: int, n_groups: int, largest_share: float) -> str:
    return f"""# Leakage groups

`leakage_groups.csv.gz` assigns every row of `dataset.csv.gz` a `group_id` ({n_rows:,} rows, {n_groups:,} groups; the largest group holds {largest_share:.1%} of the rows).

Rows are joined into one group when any of these holds:
* their peptides are near-identical in sequence (similarity >= 0.8, defined below);
* they come from the same parent protein (`parent_iri`);
* they belong to the same antigen family (`antigen_name_key`).
Groups are the connected components of these links, so two rows in different groups share none of the three.

Sequence similarity of two peptides is the best ungapped identity over relative shifts of -3..+3 residues, divided by the length of the longer peptide. A 9-mer nested inside a 10-mer scores 0.9, and a single-residue variant of a 9-mer scores 8/9 = 0.889. The similarity threshold was fixed at 0.8 by the curators.
"""


def prepare_workspace(run_id: str, condition: str, rep: int, runs_dir: Path, *, seed: int | None = None,
                      model: str | None = None, overwrite: bool = False, rel: Path | None = None) -> Path:
    rel = rel or release_dir()
    run_dir = Path(runs_dir) / run_id
    if run_dir.exists():
        if not overwrite:
            return run_dir
        shutil.rmtree(run_dir)
    checksums = verify_release(rel)
    work = run_dir / "work"
    (work / "data").mkdir(parents=True)
    (work / "submission").mkdir()

    d = pd.read_csv(rel / PRIMARY_FILE, low_memory=False)
    keep = [c for c in d.columns if c not in DROP_COLUMNS and d[c].notna().any()]
    d[keep].to_csv(work / "data" / "dataset.csv.gz", index=False)

    dd = pd.read_csv(rel / "data_dictionary.csv")
    dd = dd[(dd["table"] == "dataset_all_tiers") & dd["column"].isin(keep)].copy()
    # The released dictionary calls taxon_group a "Leakage-control" group; that wording would cue C0 and C1 agents.
    dd["description"] = dd["description"].str.replace("Leakage-control taxon group", "Source taxon group", regex=False)
    text = " ".join(dd["description"].astype(str)).lower() + " " + " ".join(keep).lower()
    if "leak" in text or "split" in text:
        raise ValueError("sanitised dictionary or column names still mention leakage/splits; fix before running agents")
    dd.drop(columns=["table"]).to_csv(work / "data" / "data_dictionary.csv", index=False)

    if condition == "C2":
        g = pd.read_csv(rel / GROUPS_FILE, usecols=["row_id", "group_id"])
        g = g[g["row_id"].isin(set(d["row_id"]))]
        g.to_csv(work / "data" / "leakage_groups.csv.gz", index=False)
        share = g["group_id"].value_counts(normalize=True).iloc[0]
        (work / "data" / "README_groups.md").write_text(group_readme(len(g), g["group_id"].nunique(), float(share)))

    p1 = build_prompt(condition, len(d))
    p2 = followup_prompt()
    (run_dir / "prompt_phase1.md").write_text(p1)
    (run_dir / "prompt_phase2.md").write_text(p2)
    write_json(run_dir / "meta.json", {
        "run_id": run_id, "condition": condition, "rep": rep, "schedule_seed": seed, "model": model,
        "n_rows": len(d), "columns_kept": keep, "columns_dropped": DROP_COLUMNS,
        "release_dir": str(rel), "release_sha256": checksums,
        "dataset_sha256": sha256_file(work / "data" / "dataset.csv.gz"),
        "prompt_phase1_sha256": hashlib.sha256(p1.encode()).hexdigest(),
        "prompt_phase2_sha256": hashlib.sha256(p2.encode()).hexdigest(),
    })
    return run_dir
