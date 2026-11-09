#!/usr/bin/env bash
# Whole study, start to finish. Edit REPS / MODEL as needed; every step can be run on its own and is resumable.
set -euo pipefail
cd "$(dirname "$0")"
REPS="${REPS:-10}"
MODEL="${MODEL:-sonnet}"

python3 src/00_validate_setup.py               # release checksums, exposure code reproduces the release's numbers
python3 src/07_reference_baseline.py           # agent-facing baseline (random / group / study-held-out AUPRC)
python3 -m unittest discover -s tests -t .     # optional but recommended: about 3 minutes

# 1. pilot (3 x 5), freeze docs/rubric.md, then discard the pilot runs from the final analysis
python3 src/03_run_batch.py --pilot --model "$MODEL"
python3 src/04_score_runs.py --runs-dir runs/pilot --label-sheet
python3 src/05_analyze.py --scores results/pilot_run_scores.csv

# 2. main experiment
python3 src/03_run_batch.py --reps "$REPS" --model "$MODEL"
python3 src/04_score_runs.py --runs-dir runs/main --label-sheet
python3 src/05_analyze.py --scores results/main_run_scores.csv
