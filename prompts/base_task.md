# Task

You are a data scientist working in the directory you start in. Use only files inside this directory; there is no internet access.

`data/dataset.csv.gz` holds <<N_ROWS>> rows, one per (peptide, HLA class I allele) pair. The column `label` is 1 if the peptide triggered a CD8+ T-cell response for that allele in laboratory assays and 0 if it was tested and did not. The other columns describe the peptide, the allele, the source organism and protein, the assays, and the publications. `data/data_dictionary.csv` describes every column.

Build a classifier that predicts `label` from the other columns, and report how well it performs.

Python 3 with numpy, pandas, scipy, scikit-learn and matplotlib is installed. Keep the work modest: a few minutes of compute on a laptop CPU is plenty. Do not modify anything in `data/`.
