# agent-leakage-evaluation

Code, prompts and analysis for the study *Do Autonomous AI Analysis Agents Detect and Avoid Data Leakage? A Controlled
Evaluation of Split Selection on a Leakage-Audited Immunology Benchmark*.

An autonomous coding agent (Claude Code, headless) is given the LCI-IEDB v1.0 table and an under-specified task. From the
files it produces we measure how leaky its own evaluation split is, how much it over-reports performance, and whether it
repairs the problem when asked to review its work.

## Layout

| Path | What it is |
|---|---|
| `prompts/` | Task text, the three condition addenda, the submission contract, the self-review follow-up |
| `src/common.py` | Constants (conditions, dropped columns, tolerances), release loading and checksum verification |
| `src/leakage_metrics.py` | Similarity + exposure of held-out rows to training rows; split classification |
| `src/workspace.py`, `src/runner.py`, `src/transcript.py`, `src/scoring.py` | Sandbox, headless runner, transcript parser, scorer |
| `src/00_validate_setup.py` ... `07_reference_baseline.py` | Command-line steps (below) |
| `docs/rubric.md` | Manual coding rubric and the pre-registered hypotheses/outcomes |
| `tests/` | 32 tests, including mock agents, a stand-in `claude` CLI and a full pipeline run |
| `runs/`, `results/`, `labels/` | Created when the pipeline runs (`runs/` is git-ignored) |

## Requirements

* The LCI-IEDB v1.0 release, placed at `../lci-iedb/data/release/LCI-IEDB_v1.0` or pointed to with
  `LCI_IEDB_RELEASE=/path/to/LCI-IEDB_v1.0`.
* Python 3 with numpy, pandas, scipy, scikit-learn and matplotlib (`requirements.txt`).
* The Claude Code command-line tool, signed in (`claude` then `/login`). No API key is read by the code; runs use the
  signed-in account and count against its usage limits or billing.

## Quick start

```bash
cd agent-leakage-evaluation
python3 src/00_validate_setup.py          # must say ALL CHECKS PASSED
python3 src/07_reference_baseline.py      # agent-facing baseline, ~1 min
python3 src/06_power.py                   # power for the number of trials per condition
python3 src/03_run_batch.py --pilot --dry-run      # see the schedule
python3 src/03_run_batch.py --pilot                # 15 trials into runs/pilot (resumable; --limit N spreads usage)
python3 src/04_score_runs.py --runs-dir runs/pilot --label-sheet
python3 src/05_analyze.py --scores results/pilot_run_scores.csv
```
The rubric (`docs/rubric.md`) is frozen after the pilot. The main experiment is then run with `03_run_batch.py --reps N`,
scored with `04` and analysed with `05` on `runs/main`; pilot runs are excluded from the final analysis.
`bash run_pipeline.sh` chains the steps. Tests: `python3 -m unittest discover -s tests -t .`.

Manual mode (for any other agent, or a person): `01_prepare_workspace.py --condition C0 --rep 1`, work in
`runs/C0_r01/work/` with `prompt_phase1.md`, then `02_run_agent.py --run-id C0_r01 --snapshot 1`; repeat for phase 2.

## Design

* **Conditions.** C0 task only; C1 + "avoid data leakage / reflect generalization"; C2 + the curators' `leakage_groups.csv.gz`
  and a README describing the grouping (agents may use them or not). Blocked random order, seeded.
* **Phases.** Phase 1 = the task. Phase 2 = same session, neutral "review your own evaluation end to end" prompt.
* **Contract.** The agent writes `submission/{split.csv, predictions.csv, results.json, report.md}`. `split.csv` marks
  training rows `train` and every other value is a held-out set trained on all rows with a different fold, so hold-out and
  K-fold both work. Outcomes are measured from these files, not from what the agent says.
* **What the agent sees.** The released primary P-vs-N2 table minus 13 label-derived columns (`DROP_COLUMNS` in `common.py`;
  e.g. `n2_confidence`, `max_positive_strength`), with the word "leakage" scrubbed from the data dictionary. Study ids
  (`reference_ids`, `pmids`) and parent-protein columns are left in as released.
* **Measured per trial and phase.** Exposure of held-out rows to training rows (identical peptide, near-duplicate >= 0.8,
  shared leakage group, shared first reference, shared any reference); split type; AUPRC/AUROC recomputed from
  `predictions.csv` and compared with what the agent reported; AUPRC on exposed vs unexposed held-out rows; the agent's
  behaviour flags from its transcript (regex heuristics, cross-checked by manual labels); cost and turns.
* **Primary outcome.** "Group-leaky": more than 5% of held-out rows share a leakage group with training. Split types:
  `group_and_study_held_out`, `group_held_out`, `study_held_out`, `similarity_aware`, `peptide_dedup_only`, `random_like`.
* **References.** The release's GBM numbers (0.756 / 0.649 / 0.550) use peptide features only. Agents also see metadata, which is
  itself predictive, so `07_reference_baseline.py` scores a fixed pipeline on the agent-facing table (random / group / study
  held out). Excess AUPRC is measured against that baseline.
* **Isolation.** The CLI runs with `--setting-sources ""`, `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, no MCP servers, no slash commands
  and only Bash/Read/Write/Edit/Glob/Grep. Transcripts are scanned for reads of the study's own release files
  (`tx_escape_release_files`).

## Verification

* Exposure code reproduces the release's own S1 and S4 exposure numbers (max difference 0.00000) and classifies S1, S4 and S5
  correctly (`00_validate_setup.py`).
* 32 tests pass: similarity vs a slow reference, hand-computed exposure cases, workspace sanitising, five mock agent strategies
  scored end to end, invalid-submission handling, a stand-in `claude` that checks the flags the runner sends, resumability,
  and the statistics on synthetic data with known effects.
* A real trial through the real CLI (Claude Code 2.1.319, `sonnet` alias = claude-sonnet-5-5) completes both phases and scores.

## Limitations

* A pilot trial showed that a current model can choose a grouped split on its own under the minimal prompt (C0). Differences
  between conditions are detectable only if some conditions produce leaky splits, so the pilot is inspected before the main run.
* Heuristic transcript flags are not ground truth; the audit and self-correction variables are coded manually.
* The agent executes shell commands with the permissions of the invoking user inside `runs/<run_id>/work/`; the sandbox is a
  working directory, not an operating-system isolation boundary. Run the harness on a machine without sensitive files in
  reachable locations.
* One dataset and one model family. Other models can be added with `--model` and analysed as a factor. The 5% exposure
  tolerance is a design choice (`EXPOSURE_TOL`, `STUDY_TOL`), and the release's own S5 split holds out only each row's first
  reference.
