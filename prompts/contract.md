## Deliverables

Put these four files in `submission/` (create the folder if needed). Keep your code in the working directory.

1. `submission/split.csv` with columns `row_id,fold`. Give every row you used a `fold` value. Rows used only for fitting or tuning (including any validation data) get `train`. Every other value (for example `test`, or `0`..`4` for cross-validation) names a held-out set; the model that scores a held-out set must be trained on the rows whose `fold` differs from that set's value. Rows you did not use can be left out.
2. `submission/predictions.csv` with columns `row_id,score`: the predicted probability that `label` is 1 for every held-out row, produced by a model that was not trained on that row's held-out set.
3. `submission/results.json` with the keys `model` (short description), `auprc`, `auroc` (both computed on the held-out rows, as one number each) and `n_heldout`.
4. `submission/report.md`, at most 400 words: what you built, how you evaluated it, the results, and any caveats.
