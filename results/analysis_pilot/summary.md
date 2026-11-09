# Analysis of `pilot_run_scores.csv`

Release reference AUPRC (peptide-feature GBM, primary P vs N2): random split S4 0.756; leakage-group split S1 0.649; study-held-out S5 0.550; chance 0.539.

Agent-facing baseline (same table the agents saw): random 0.960; leakage-group 0.861; study-held-out 0.748.

## Completeness

| phase | condition | trials | valid | valid_share |
|---|---|---|---|---|
| 1 | C0 | 5 | 5 | 1.000 |
| 1 | C1 | 5 | 5 | 1.000 |
| 1 | C2 | 5 | 5 | 1.000 |
| 2 | C0 | 5 | 5 | 1.000 |
| 2 | C1 | 5 | 5 | 1.000 |
| 2 | C2 | 5 | 5 | 1.000 |

## Final split type by condition (counts)

| phase | condition | group_and_study_held_out | group_held_out | study_held_out | similarity_aware | peptide_dedup_only | random_like | invalid |
|---|---|---|---|---|---|---|---|---|
| 1 | C0 | 0 | 0 | 1 | 0 | 4 | 0 | 0 |
| 1 | C1 | 0 | 0 | 0 | 0 | 5 | 0 | 0 |
| 1 | C2 | 0 | 5 | 0 | 0 | 0 | 0 | 0 |
| 2 | C0 | 0 | 0 | 2 | 3 | 0 | 0 | 0 |
| 2 | C1 | 0 | 0 | 1 | 3 | 1 | 0 | 0 |
| 2 | C2 | 0 | 5 | 0 | 0 | 0 | 0 | 0 |

## Primary outcome, phase 1: share of trials with a group-leaky final split (valid submissions only)

| condition | k | n | share | ci_lo | ci_hi |
|---|---|---|---|---|---|
| C0 | 5 | 5 | 1.000 | 0.566 | 1.000 |
| C1 | 5 | 5 | 1.000 | 0.566 | 1.000 |
| C2 | 0 | 5 | 0.000 | -0.000 | 0.434 |

Permutation chi-square across the three conditions: chi2 = 15.00, p = 0.0013 (20000 permutations).

Pairwise Fisher exact tests (Holm-adjusted):

| a | b | share_a | share_b | diff | odds_ratio | p | p_holm |
|---|---|---|---|---|---|---|---|
| C0 | C1 | 1.0000 | 1.0000 | 0.0000 |  | 1.0000 | 1.0000 |
| C0 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0079 | 0.0238 |
| C1 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0079 | 0.0238 |

## AUPRC above the leakage-controlled reference (recomputed AUPRC minus 0.861, agent-facing baseline on a leakage-group split), phase 1

| condition | n | mean | ci_lo | ci_hi | median | sd | min | max |
|---|---|---|---|---|---|---|---|---|
| C0 | 5 | -0.134 | -0.173 | -0.110 | -0.116 | 0.043 | -0.210 | -0.108 |
| C1 | 5 | -0.079 | -0.139 | -0.018 | -0.082 | 0.075 | -0.184 | 0.024 |
| C2 | 5 | -0.031 | -0.054 | 0.011 | -0.051 | 0.047 | -0.057 | 0.053 |

Kruskal-Wallis: H = 8.82, p = 0.0122.

Pairwise Mann-Whitney (Holm), Cliff's delta:

| a | b | n_a | n_b | p | cliffs_delta_a_vs_b | p_holm |
|---|---|---|---|---|---|---|
| C0 | C1 | 5 | 5 | 0.0952 | -0.6800 | 0.1905 |
| C0 | C2 | 5 | 5 | 0.0079 | -1.0000 | 0.0238 |
| C1 | C2 | 5 | 5 | 0.0952 | -0.6800 | 0.1905 |

## Within-run optimism check, phase 1: AUPRC on held-out rows that share a leakage group with training vs rows that do not (model-agnostic; empty when a split already removes all shared groups)

| condition | n | median_auprc_exposed | median_auprc_unexposed | median_gap | n_with_gap |
|---|---|---|---|---|---|
| C0 | 5 | 0.728 | 0.780 | -0.049 | 5 |
| C1 | 5 | 0.761 | 0.692 | 0.114 | 5 |
| C2 | 5 |  | 0.809 |  | 0 |

## Study shortcut among trials that controlled leakage groups, phase 1

| condition | group_controlled | still_study_exposed | share_study_exposed |
|---|---|---|---|
| C2 | 5 | 5 | 1.000 |

## Reported vs recomputed AUPRC, phase 1

| condition | n | mean_reported_minus_recomputed | mismatch_share |
|---|---|---|---|
| C0 | 5 | 0.000 | 0.000 |
| C1 | 5 | 0.000 | 0.000 |
| C2 | 5 | 0.000 | 0.000 |

## Primary outcome, phase 2: share of trials with a group-leaky final split (valid submissions only)

| condition | k | n | share | ci_lo | ci_hi |
|---|---|---|---|---|---|
| C0 | 5 | 5 | 1.000 | 0.566 | 1.000 |
| C1 | 5 | 5 | 1.000 | 0.566 | 1.000 |
| C2 | 0 | 5 | 0.000 | -0.000 | 0.434 |

Permutation chi-square across the three conditions: chi2 = 15.00, p = 0.0013 (20000 permutations).

Pairwise Fisher exact tests (Holm-adjusted):

| a | b | share_a | share_b | diff | odds_ratio | p | p_holm |
|---|---|---|---|---|---|---|---|
| C0 | C1 | 1.0000 | 1.0000 | 0.0000 |  | 1.0000 | 1.0000 |
| C0 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0079 | 0.0238 |
| C1 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0079 | 0.0238 |

## AUPRC above the leakage-controlled reference (recomputed AUPRC minus 0.861, agent-facing baseline on a leakage-group split), phase 2

| condition | n | mean | ci_lo | ci_hi | median | sd | min | max |
|---|---|---|---|---|---|---|---|---|
| C0 | 5 | -0.138 | -0.207 | -0.069 | -0.190 | 0.091 | -0.214 | -0.038 |
| C1 | 5 | -0.082 | -0.151 | -0.013 | -0.046 | 0.090 | -0.186 | 0.017 |
| C2 | 5 | -0.046 | -0.054 | -0.035 | -0.051 | 0.013 | -0.057 | -0.024 |

Kruskal-Wallis: H = 1.86, p = 0.3946.

Pairwise Mann-Whitney (Holm), Cliff's delta:

| a | b | n_a | n_b | p | cliffs_delta_a_vs_b | p_holm |
|---|---|---|---|---|---|---|
| C0 | C1 | 5 | 5 | 0.2222 | -0.5200 | 0.6667 |
| C0 | C2 | 5 | 5 | 0.4206 | -0.3600 | 0.8413 |
| C1 | C2 | 5 | 5 | 1.0000 | 0.0400 | 1.0000 |

## Within-run optimism check, phase 2: AUPRC on held-out rows that share a leakage group with training vs rows that do not (model-agnostic; empty when a split already removes all shared groups)

| condition | n | median_auprc_exposed | median_auprc_unexposed | median_gap | n_with_gap |
|---|---|---|---|---|---|
| C0 | 5 | 0.763 | 0.590 | 0.173 | 5 |
| C1 | 5 | 0.854 | 0.661 | 0.171 | 5 |
| C2 | 5 |  | 0.809 |  | 0 |

## Study shortcut among trials that controlled leakage groups, phase 2

| condition | group_controlled | still_study_exposed | share_study_exposed |
|---|---|---|---|
| C2 | 5 | 5 | 1.000 |

## Reported vs recomputed AUPRC, phase 2

| condition | n | mean_reported_minus_recomputed | mismatch_share |
|---|---|---|---|
| C0 | 5 | 0.000 | 0.000 |
| C1 | 5 | 0.000 | 0.000 |
| C2 | 5 | 0.000 | 0.000 |

## Self-review prompt (phase 1 -> phase 2), trials valid in both phases

| condition | n_pairs | leaky_before | fixed_after_review | newly_leaky | share_of_leaky_fixed | mcnemar_exact_p | median_change_auprc | wilcoxon_p |
|---|---|---|---|---|---|---|---|---|
| C0 | 5 | 5 | 0 | 0 | 0.0000 | 1.0000 | 0.0000 | 1.0000 |
| C1 | 5 | 5 | 0 | 0 | 0.0000 | 1.0000 | -0.0014 | 1.0000 |
| C2 | 5 | 0 | 0 | 0 |  | 1.0000 | 0.0000 | 1.0000 |
| all | 15 | 10 | 0 | 0 | 0.0000 | 1.0000 | 0.0000 | 0.4446 |

## Heuristic behaviour flags (share of trials; regex-based, check against manual labels)

| phase | condition | tx_mentions_leakage | tx_audit_similarity | tx_audit_overlap | tx_used_provided_groups | tx_code_grouped_split | tx_code_random_split | tx_escape_release_files | report_mentions_leakage |
|---|---|---|---|---|---|---|---|---|---|
| 1 | C0 | 0.200 | 0.000 | 0.600 | 0.000 | 1.000 | 0.000 | 0.000 | 0.600 |
| 1 | C1 | 0.600 | 0.000 | 0.800 | 0.000 | 1.000 | 0.000 | 0.000 | 0.600 |
| 1 | C2 | 0.600 | 0.000 | 0.400 | 1.000 | 1.000 | 0.000 | 0.000 | 0.400 |
| 2 | C0 | 0.200 | 0.200 | 0.400 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 |
| 2 | C1 | 0.200 | 0.200 | 1.000 | 0.000 | 0.600 | 0.000 | 0.000 | 0.600 |
| 2 | C2 | 1.000 | 0.200 | 0.000 | 0.800 | 0.600 | 0.000 | 0.000 | 0.600 |

## Cost and effort (as reported by the CLI)

| phase | condition | trials | total_cost_usd | mean_turns |
|---|---|---|---|---|
| 1 | C0 | 5 | 0.383 | 6.000 |
| 1 | C1 | 5 | 0.355 | 6.400 |
| 1 | C2 | 5 | 0.364 | 5.400 |
| 2 | C0 | 5 | 0.694 | 6.400 |
| 2 | C1 | 5 | 0.627 | 5.600 |
| 2 | C2 | 5 | 0.684 | 6.200 |
