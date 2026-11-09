# agent-leakage-evaluation

Code for the study *Do Autonomous AI Analysis Agents Detect and Avoid Data Leakage? A Controlled Evaluation of
Split-Selection Behavior on a Leakage-Audited Immunology Benchmark* (target: BioData Mining, collection "Uses of Agentic AI
in Biodata Mining").

An autonomous coding agent (Claude Code, headless) is given the LCI-IEDB v1.0 table and an under-specified task. We measure,
from the files it produces, how leaky its own evaluation is, how much it over-reports, and whether it repairs the problem.

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
| `runs/`, `results/`, `labels/` | Created as you go (`runs/` is git-ignored) |

Put the LCI-IEDB v1.0 release next to this folder (default `../lci-iedb/data/release/LCI-IEDB_v1.0`), or set `LCI_IEDB_RELEASE=/path/to/LCI-IEDB_v1.0`. Only numpy,
pandas, scipy, scikit-learn and matplotlib are needed (same as the release). No API key: agents run through your Claude Code
login.

## Quick start

```bash
cd agent-leakage-evaluation
python3 src/00_validate_setup.py          # must say ALL CHECKS PASSED
python3 src/07_reference_baseline.py      # agent-facing baseline, ~1 min
python3 src/06_power.py                   # how many trials per condition you need
python3 src/03_run_batch.py --pilot --dry-run      # see the schedule
python3 src/03_run_batch.py --pilot                # 15 trials into runs/pilot (resumable; --limit N to spread usage)
python3 src/04_score_runs.py --runs-dir runs/pilot --label-sheet
python3 src/05_analyze.py --scores results/pilot_run_scores.csv
```
Then freeze `docs/rubric.md`, run the main experiment (`03_run_batch.py --reps N`, `04`, `05` on `runs/main`) and discard the
pilot from the final analysis. `bash run_pipeline.sh` chains everything. Tests: `python3 -m unittest discover -s tests -t .`.

Manual mode (any other agent, or a person): `01_prepare_workspace.py --condition C0 --rep 1`, work in
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
* **Isolation.** The CLI runs with `--setting-sources ""`, `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`, no MCP servers, no slash commands
  and only Bash/Read/Write/Edit/Glob/Grep. Transcripts are scanned for reads of the study's own release files
  (`tx_escape_release_files`).

## Verified

* Exposure code reproduces the release's own S1 and S4 exposure numbers (max difference 0.00000) and classifies S1, S4 and S5
  correctly (`00_validate_setup.py`).
* 32 tests pass: similarity vs a slow reference, hand-computed exposure cases, workspace sanitising, five mock agent strategies
  scored end to end, invalid-submission handling, a stand-in `claude` that checks the flags the runner sends, resumability,
  and the statistics on synthetic data with known effects.
* One real trial through the real CLI (Claude Code 2.1.319, sonnet alias = claude-sonnet-5-5) completed both phases and scored.

## Caveats you should state in the paper

* The study design is not a hypothesis-free guess: a smoke trial showed a current model can pick a grouped split on its own
  in C0. Condition differences are only detectable if some conditions leak; run the pilot and look before committing.
* Heuristic transcript flags are not ground truth; use the manual labels for the audit/self-correction variables.
* The agent runs shell commands as you inside `runs/<run_id>/work/` and nothing stops a command from touching other files.
* One dataset, one model family (add `--model` runs as a factor if you can), 5% exposure tolerance is a choice
  (`EXPOSURE_TOL`, `STUDY_TOL`), and the release's own S5 only holds out each row's first reference.
