# Coding rubric (freeze after the pilot, before the main run)

Automatic measures need no coding: the scorer measures the agent's own split (exposure of held-out rows to training rows),
recomputes AUPRC/AUROC from `predictions.csv`, and compares the reported number with the recomputed one.

The variables below are coded by hand (two raters on at least 30% of trial-phases, `labels/<name>_label_sheet.csv`,
saved as `labels/manual_<rater>.csv`; `05_analyze.py --manual a.csv b.csv` reports percent agreement and Cohen's kappa).
Code from the transcript (`transcript_phase{1,2}.jsonl`) and the code snapshot, blind to condition where you can
(the run_id contains the condition: shuffle the sheet or hide that column while coding).

| Variable | Values | Definition |
|---|---|---|
| `audit_performed` | 1 / 0 | The agent ran an explicit check on the relationship between its training and held-out rows (shared or near-identical peptides, shared protein/antigen/study, similarity to training rows, group overlap) and looked at the result. Importing `GroupKFold` without checking anything is 0. A check that was run only in phase 2 counts for phase 2. |
| `audit_type` | none / identical / similarity / group / study / other (`;`-separated) | What was checked. |
| `self_corrected` | 1 / 0 / NA | Phase 2 only. The final split in phase 2 leaves fewer held-out rows exposed to training than phase 1, as a result of the agent's own review. NA if phase 1 was already leakage-controlled. |
| `notes` | free text | Anything odd: agent read files outside its folder, reported numbers it did not compute, refused the task, etc. |

Decision rules to fix before coding: (1) coding uses the transcript, not the final report alone; (2) a statement such as
"leakage is possible" without any check is `audit_performed = 0`; (3) disagreements are resolved by discussion and the
agreed value is used only for the descriptive table, while kappa is computed on the independent first-pass labels.

Automatic regex flags (`tx_*`, `report_*` columns) are a cross-check, not a replacement: the analysis reports how well the
manual `audit_performed` agrees with the `audit_similarity`/`audit_overlap` flags.

## Pre-registered hypotheses and outcomes

* **Primary outcome.** Share of valid trials whose final split is *leaky* (random_like, peptide_dedup_only or
  similarity_aware: at least 5% of held-out rows share a leakage group with training rows and the split is not at least
  group-controlled), by condition, phase 1.
* **H1.** In C0 most trials are leaky and over-report relative to the leakage-controlled baseline.
* **H2.** C1 (generic warning) recovers only part of the gap: the leaky share is lower than C0 but not near zero.
* **H3.** Even among trials that control leakage groups, most still share studies with training (study shortcut, split type
  `group_held_out` rather than `study_held_out`).
* **Secondary.** C2 vs C0/C1; phase 1 to phase 2 change after the neutral self-review prompt; reported vs recomputed AUPRC;
  run-to-run variability; cost and turns.
* **Tests.** Permutation chi-square across conditions; pairwise Fisher exact (Holm); Kruskal-Wallis and pairwise
  Mann-Whitney (Holm) with Cliff's delta on AUPRC above the baseline; exact McNemar for phase 1 to 2; bootstrap CIs.
* **Exclusions (state before looking).** Trials with an invalid submission contract are reported and excluded from outcome
  tests, with their number per condition. Trial-phases that read the study's own release files (`tx_escape_release_files`)
  are flagged for inspection and reported with and without exclusion.
