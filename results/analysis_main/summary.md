# Analysis of `main_run_scores.csv`

Release reference AUPRC (peptide-feature GBM, primary P vs N2): random split S4 0.756; leakage-group split S1 0.649; study-held-out S5 0.550; chance 0.539.

Agent-facing baseline (same table the agents saw): random 0.960; leakage-group 0.861; study-held-out 0.748.

## Completeness

| phase | condition | trials | valid | valid_share |
|---|---|---|---|---|
| 1 | C0 | 10 | 10 | 1.000 |
| 1 | C1 | 10 | 10 | 1.000 |
| 1 | C2 | 10 | 10 | 1.000 |
| 2 | C0 | 10 | 10 | 1.000 |
| 2 | C1 | 10 | 10 | 1.000 |
| 2 | C2 | 10 | 10 | 1.000 |

## Final split type by condition (counts)

| phase | condition | group_and_study_held_out | group_held_out | study_held_out | similarity_aware | peptide_dedup_only | random_like | invalid |
|---|---|---|---|---|---|---|---|---|
| 1 | C0 | 0 | 0 | 7 | 0 | 3 | 0 | 0 |
| 1 | C1 | 0 | 0 | 2 | 0 | 8 | 0 | 0 |
| 1 | C2 | 0 | 10 | 0 | 0 | 0 | 0 | 0 |
| 2 | C0 | 0 | 0 | 7 | 2 | 1 | 0 | 0 |
| 2 | C1 | 0 | 0 | 4 | 5 | 1 | 0 | 0 |
| 2 | C2 | 0 | 10 | 0 | 0 | 0 | 0 | 0 |

## Primary outcome, phase 1: share of trials with a group-leaky final split (valid submissions only)

| condition | k | n | share | ci_lo | ci_hi |
|---|---|---|---|---|---|
| C0 | 10 | 10 | 1.000 | 0.722 | 1.000 |
| C1 | 10 | 10 | 1.000 | 0.722 | 1.000 |
| C2 | 0 | 10 | 0.000 | 0.000 | 0.278 |

Permutation chi-square across the three conditions: chi2 = 30.00, p = 0.0000 (20000 permutations).

Pairwise Fisher exact tests (Holm-adjusted):

| a | b | share_a | share_b | diff | odds_ratio | p | p_holm |
|---|---|---|---|---|---|---|---|
| C0 | C1 | 1.0000 | 1.0000 | 0.0000 |  | 1.0000 | 1.0000 |
| C0 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0000 | 0.0000 |
| C1 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0000 | 0.0000 |

## AUPRC above the leakage-controlled reference (recomputed AUPRC minus 0.861, agent-facing baseline on a leakage-group split), phase 1

| condition | n | mean | ci_lo | ci_hi | median | sd | min | max |
|---|---|---|---|---|---|---|---|---|
| C0 | 10 | -0.163 | -0.189 | -0.137 | -0.162 | 0.044 | -0.221 | -0.091 |
| C1 | 10 | -0.122 | -0.157 | -0.090 | -0.102 | 0.057 | -0.210 | -0.062 |
| C2 | 10 | -0.046 | -0.061 | -0.027 | -0.050 | 0.028 | -0.086 | 0.028 |

Kruskal-Wallis: H = 20.02, p = 0.0000.

Pairwise Mann-Whitney (Holm), Cliff's delta:

| a | b | n_a | n_b | p | cliffs_delta_a_vs_b | p_holm |
|---|---|---|---|---|---|---|
| C0 | C1 | 10 | 10 | 0.0640 | -0.5000 | 0.0640 |
| C0 | C2 | 10 | 10 | 0.0002 | -1.0000 | 0.0005 |
| C1 | C2 | 10 | 10 | 0.0004 | -0.9400 | 0.0009 |

## Within-run optimism check, phase 1: AUPRC on held-out rows that share a leakage group with training vs rows that do not (model-agnostic; empty when a split already removes all shared groups)

| condition | n | median_auprc_exposed | median_auprc_unexposed | median_gap | n_with_gap |
|---|---|---|---|---|---|
| C0 | 10 | 0.749 | 0.562 | 0.198 | 10 |
| C1 | 10 | 0.737 | 0.769 | 0.021 | 10 |
| C2 | 10 |  | 0.811 |  | 0 |

## Study shortcut among trials that controlled leakage groups, phase 1

| condition | group_controlled | still_study_exposed | share_study_exposed |
|---|---|---|---|
| C2 | 10 | 10 | 1.000 |

## Reported vs recomputed AUPRC, phase 1

| condition | n | mean_reported_minus_recomputed | mismatch_share |
|---|---|---|---|
| C0 | 10 | 0.000 | 0.000 |
| C1 | 10 | 0.000 | 0.000 |
| C2 | 10 | 0.000 | 0.000 |

## Primary outcome, phase 2: share of trials with a group-leaky final split (valid submissions only)

| condition | k | n | share | ci_lo | ci_hi |
|---|---|---|---|---|---|
| C0 | 10 | 10 | 1.000 | 0.722 | 1.000 |
| C1 | 10 | 10 | 1.000 | 0.722 | 1.000 |
| C2 | 0 | 10 | 0.000 | 0.000 | 0.278 |

Permutation chi-square across the three conditions: chi2 = 30.00, p = 0.0000 (20000 permutations).

Pairwise Fisher exact tests (Holm-adjusted):

| a | b | share_a | share_b | diff | odds_ratio | p | p_holm |
|---|---|---|---|---|---|---|---|
| C0 | C1 | 1.0000 | 1.0000 | 0.0000 |  | 1.0000 | 1.0000 |
| C0 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0000 | 0.0000 |
| C1 | C2 | 1.0000 | 0.0000 | 1.0000 | inf | 0.0000 | 0.0000 |

## AUPRC above the leakage-controlled reference (recomputed AUPRC minus 0.861, agent-facing baseline on a leakage-group split), phase 2

| condition | n | mean | ci_lo | ci_hi | median | sd | min | max |
|---|---|---|---|---|---|---|---|---|
| C0 | 10 | -0.183 | -0.224 | -0.137 | -0.199 | 0.074 | -0.287 | -0.037 |
| C1 | 10 | -0.118 | -0.165 | -0.073 | -0.114 | 0.079 | -0.213 | -0.023 |
| C2 | 10 | -0.073 | -0.105 | -0.052 | -0.054 | 0.047 | -0.201 | -0.047 |

Kruskal-Wallis: H = 6.58, p = 0.0373.

Pairwise Mann-Whitney (Holm), Cliff's delta:

| a | b | n_a | n_b | p | cliffs_delta_a_vs_b | p_holm |
|---|---|---|---|---|---|---|
| C0 | C1 | 10 | 10 | 0.1212 | -0.4200 | 0.2424 |
| C0 | C2 | 10 | 10 | 0.0091 | -0.7000 | 0.0273 |
| C1 | C2 | 10 | 10 | 0.6232 | -0.1400 | 0.6232 |

## Within-run optimism check, phase 2: AUPRC on held-out rows that share a leakage group with training vs rows that do not (model-agnostic; empty when a split already removes all shared groups)

| condition | n | median_auprc_exposed | median_auprc_unexposed | median_gap | n_with_gap |
|---|---|---|---|---|---|
| C0 | 10 | 0.658 | 0.673 | -0.031 | 10 |
| C1 | 10 | 0.791 | 0.705 | 0.123 | 10 |
| C2 | 10 |  | 0.807 |  | 0 |

## Study shortcut among trials that controlled leakage groups, phase 2

| condition | group_controlled | still_study_exposed | share_study_exposed |
|---|---|---|---|
| C2 | 10 | 10 | 1.000 |

## Reported vs recomputed AUPRC, phase 2

| condition | n | mean_reported_minus_recomputed | mismatch_share |
|---|---|---|---|
| C0 | 10 | 0.000 | 0.000 |
| C1 | 10 | 0.000 | 0.000 |
| C2 | 10 | 0.000 | 0.000 |

## Self-review prompt (phase 1 -> phase 2), trials valid in both phases

| condition | n_pairs | leaky_before | fixed_after_review | newly_leaky | share_of_leaky_fixed | mcnemar_exact_p | median_change_auprc | wilcoxon_p |
|---|---|---|---|---|---|---|---|---|
| C0 | 10 | 10 | 0 | 0 | 0.0000 | 1.0000 | -0.0063 | 0.3750 |
| C1 | 10 | 10 | 0 | 0 | 0.0000 | 1.0000 | 0.0072 | 0.6250 |
| C2 | 10 | 0 | 0 | 0 |  | 1.0000 | 0.0000 | 0.3125 |
| all | 30 | 20 | 0 | 0 | 0.0000 | 1.0000 | 0.0000 | 0.4118 |

## Heuristic behaviour flags (share of trials; regex-based, check against manual labels)

| phase | condition | tx_mentions_leakage | tx_audit_similarity | tx_audit_overlap | tx_used_provided_groups | tx_code_grouped_split | tx_code_random_split | tx_escape_release_files | report_mentions_leakage |
|---|---|---|---|---|---|---|---|---|---|
| 1 | C0 | 0.300 | 0.000 | 0.800 | 0.000 | 0.900 | 0.000 | 0.000 | 0.700 |
| 1 | C1 | 0.500 | 0.000 | 0.600 | 0.000 | 1.000 | 0.000 | 0.000 | 0.600 |
| 1 | C2 | 0.900 | 0.300 | 0.300 | 1.000 | 1.000 | 0.000 | 0.000 | 0.900 |
| 2 | C0 | 0.400 | 0.100 | 0.600 | 0.000 | 0.100 | 0.000 | 0.000 | 0.400 |
| 2 | C1 | 0.700 | 0.200 | 0.700 | 0.000 | 0.200 | 0.000 | 0.000 | 0.600 |
| 2 | C2 | 0.700 | 0.200 | 0.000 | 0.900 | 0.400 | 0.000 | 0.000 | 0.800 |

## Cost and effort (as reported by the CLI)

| phase | condition | trials | total_cost_usd | mean_turns |
|---|---|---|---|---|
| 1 | C0 | 10 | 0.631 | 5.000 |
| 1 | C1 | 10 | 0.720 | 6.000 |
| 1 | C2 | 10 | 0.570 | 5.200 |
| 2 | C0 | 10 | 1.167 | 4.800 |
| 2 | C1 | 10 | 1.224 | 5.400 |
| 2 | C2 | 10 | 1.033 | 4.400 |
