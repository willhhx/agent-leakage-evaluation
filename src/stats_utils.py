"""Small, dependency-light statistics used by 05_analyze.py (scipy + numpy only)."""
from __future__ import annotations

import itertools

import numpy as np
from scipy import stats


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, returned in the input order."""
    p = np.asarray(pvals, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()


def bootstrap_ci(x, stat=np.mean, B: int = 10000, seed: int = 1, alpha: float = 0.05) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(B, len(x)))
    s = stat(x[idx], axis=1)
    return (float(np.quantile(s, alpha / 2)), float(np.quantile(s, 1 - alpha / 2)))


def cliffs_delta(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    gt = (a[:, None] > b[None, :]).sum()
    lt = (a[:, None] < b[None, :]).sum()
    return float((gt - lt) / (len(a) * len(b)))


def fisher_pair(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """(odds ratio, two-sided exact p) for k1/n1 vs k2/n2."""
    if n1 == 0 or n2 == 0:
        return (float("nan"), float("nan"))
    odds, p = stats.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])
    return float(odds), float(p)


def perm_chi2(counts: np.ndarray, B: int = 20000, seed: int = 1) -> tuple[float, float]:
    """Permutation test of independence for a (groups x outcomes) count table (valid for tiny cells).

    Statistic: Pearson chi-square. Rows are labels shuffled across individual observations.
    """
    counts = np.asarray(counts, dtype=int)
    counts = counts[counts.sum(axis=1) > 0][:, counts.sum(axis=0) > 0]
    if counts.shape[0] < 2 or counts.shape[1] < 2:
        return (0.0, 1.0)
    g = np.repeat(np.arange(counts.shape[0]), counts.sum(axis=1))
    o = np.concatenate([np.repeat(j, counts[i, j]) for i in range(counts.shape[0]) for j in range(counts.shape[1])])
    # o above is ordered group-major, matching g
    def chi(gv, ov):
        tab = np.zeros(counts.shape)
        np.add.at(tab, (gv, ov), 1)
        exp = tab.sum(1, keepdims=True) * tab.sum(0, keepdims=True) / tab.sum()
        return float(((tab - exp) ** 2 / exp).sum())
    obs = chi(g, o)
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(B):
        if chi(g, rng.permutation(o)) >= obs - 1e-12:
            ge += 1
    return obs, (ge + 1) / (B + 1)


def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar p from the discordant counts b (1->0) and c (0->1)."""
    n = b + c
    if n == 0:
        return 1.0
    return float(stats.binomtest(min(b, c), n, 0.5).pvalue)


def cohen_kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    cats = sorted(set(a) | set(b))
    po = float((a == b).mean())
    pe = sum(float((a == c).mean()) * float((b == c).mean()) for c in cats)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def pairwise_mwu(groups: dict[str, np.ndarray]) -> list[dict]:
    rows = []
    for (n1, a), (n2, b) in itertools.combinations(groups.items(), 2):
        a, b = np.asarray(a, float), np.asarray(b, float)
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if len(a) == 0 or len(b) == 0:
            p = float("nan")
        elif np.all(a == a[0]) and np.all(b == a[0]):
            p = 1.0
        else:
            p = float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
        rows.append({"a": n1, "b": n2, "n_a": len(a), "n_b": len(b), "p": p, "cliffs_delta_a_vs_b": cliffs_delta(a, b)})
    adj = holm([r["p"] if np.isfinite(r["p"]) else 1.0 for r in rows])
    for r, q in zip(rows, adj):
        r["p_holm"] = q
    return rows
