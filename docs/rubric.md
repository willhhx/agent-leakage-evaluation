# Coding rubric and pre-specified analysis (frozen after the pilot, before the main run)

Automatic measures need no coding: the scorer measures the agent's own split (exposure of held-out rows to training rows),
recomputes AUPRC/AUROC from `predictions.csv`, and compares the reported number with the recomputed one.

The variables below are coded by hand (two raters on at least 30% of trial-phases, `labels/<name>_label_sheet.csv`,
saved as `labels/manual_<rater>.csv`; `05_analyze.py --manual a.csv b.csv` reports percent agreement and Cohen's kappa).
Coders use the transcript (`transcript_phase{1,2}.jsonl`) and the code snapshot, blind to condition where possible
(the run_id contains the condition, so the sheet is shuffled or that column hidden while coding).

| Variable | Values | Definition |
|---|---|---|
| `audit_performed` | 1 / 0 | The agent ran an explicit check on the relationship between its training and held-out rows (shared or near-identical peptides, shared protein/antigen/study, similarity to training rows, group overlap) and looked at the result. Importing `GroupKFold` without checking anything is 0. A check that was run only in phase 2 counts for phase 2. |
| `audit_type` | none / identical / similarity / group / study / other (`;`-separated) | What was checked. |
| `self_corrected` | 1 / 0 / NA | Phase 2 only. The final split in phase 2 leaves fewer held-out rows exposed to training than phase 1, as a result of the agent's own review. NA if phase 1 was already leakage-controlled. |
| `notes` | free text | Anything odd: agent read files outside its folder, reported numbers it did not compute, refused the task, etc. |

Decision rules fixed before coding: (1) coding uses the transcript, not the final report alone; (2) a statement such as
"leakage is possible" without any check is `audit_performed = 0`; (3) disagreements are resolved by discussion and the
agreed value is used only for the descriptive table, while kappa is computed on the independent first-pass labels.

Automatic regex flags (`tx_*`, `report_*` columns) are a cross-check, not a replacement: the analysis reports how well the
manual `audit_performed` agrees with the `audit_similarity`/`audit_overlap` flags.

## Pre-specified hypotheses and outcomes

* **Primary outcome.** Share of valid trials whose phase 1 split is *group-leaky*: more than 5% of held-out rows share a
  leakage group with training rows (`EXPOSURE_TOL = 0.05`). By split type this is `study_held_out`, `similarity_aware`,
  `peptide_dedup_only` and `random_like` (`LEAKY_TYPES` in `src/common.py`); `group_held_out` and
  `group_and_study_held_out` are not leaky.
* **H1.** The share of group-leaky splits differs across C0, C1 and C2, ordered C0 >= C1 >= C2.
* **H2.** Recomputed AUPRC on exposed held-out rows exceeds that on unexposed rows, so leakage inflates performance.
* **H3.** A neutral self-review prompt reduces the share of leaky splits between phase 1 and phase 2.
* **Secondary.** Reported versus recomputed AUPRC; AUPRC above the agent-facing baseline; study exposure among trials that
  control leakage groups (study shortcut); run-to-run variability; cost and turns.
* **Tests.** Permutation chi-square across conditions; pairwise Fisher exact (Holm); Kruskal-Wallis and pairwise
  Mann-Whitney (Holm) with Cliff's delta on AUPRC above the baseline; exact McNemar for phase 1 to 2; Wilcoxon signed-rank
  for the change in exposure; bootstrap CIs; Wilson intervals for proportions.
* **Exclusions (fixed before the main run).** Trials with an invalid submission contract after one permitted retry are
  reported by cause and excluded from outcome tests. Trial-phases that read the study's own release files
  (`tx_escape_release_files`) are flagged for inspection and reported with and without exclusion.
