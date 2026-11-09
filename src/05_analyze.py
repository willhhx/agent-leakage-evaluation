#!/usr/bin/env python3
"""Statistics, tables and figures from results/<name>_run_scores.csv.

  python3 src/05_analyze.py --scores results/main_run_scores.csv [--manual labels/manual_a.csv labels/manual_b.csv]

Outputs go to results/analysis_<name>/ : CSV tables, figures (PNG + PDF) and summary.md.
Hypotheses (see README): H1 C0 mostly leaky; H2 C1 recovers only part; H3 study shortcut rarely controlled.
Primary outcome ("group-leaky"): share of trials whose final split leaves more than 5% of held-out rows sharing a leakage
group with training rows (split types random_like, peptide_dedup_only, similarity_aware, study_held_out). Phase 1 = before the self-review prompt,
phase 2 = after it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common import CONDITION_LABELS, CONDITIONS, PROJECT_ROOT, SPLIT_TYPE_LABELS, SPLIT_TYPES, reference_values, wilson  # noqa: E402
from src.stats_utils import (bootstrap_ci, cohen_kappa, fisher_pair, holm, mcnemar_exact, pairwise_mwu,  # noqa: E402
                             perm_chi2)

OKABE = {"group_and_study_held_out": "#009E73", "study_held_out": "#CC79A7", "group_held_out": "#56B4E9", "similarity_aware": "#F0E442",
         "peptide_dedup_only": "#E69F00", "random_like": "#D55E00", "invalid": "#999999"}


def md_table(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
    head = "| " + " | ".join(map(str, d.columns)) + " |\n|" + "|".join("---" for _ in d.columns) + "|\n"
    return head + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in d.astype(str).values) + "\n"


def prop_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for c in CONDITIONS:
        s = df.loc[df["condition"] == c, col].dropna().astype(bool)
        k, n = int(s.sum()), len(s)
        lo, hi = wilson(k, n)
        rows.append({"condition": c, "k": k, "n": n, "share": k / n if n else np.nan, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def pairwise_fisher(tab: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for a, b in (("C0", "C1"), ("C0", "C2"), ("C1", "C2")):
        ra, rb = tab[tab.condition == a].iloc[0], tab[tab.condition == b].iloc[0]
        odds, p = fisher_pair(int(ra.k), int(ra.n), int(rb.k), int(rb.n))
        rows.append({"a": a, "b": b, "share_a": ra.share, "share_b": rb.share, "diff": ra.share - rb.share, "odds_ratio": odds, "p": p})
    adj = holm([r["p"] if np.isfinite(r["p"]) else 1.0 for r in rows])
    for r, q in zip(rows, adj):
        r["p_holm"] = q
    return pd.DataFrame(rows)


def delta_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for c in CONDITIONS:
        x = df.loc[df["condition"] == c, col].dropna().to_numpy(float)
        lo, hi = bootstrap_ci(x)
        rows.append({"condition": c, "n": len(x), "mean": np.mean(x) if len(x) else np.nan, "ci_lo": lo, "ci_hi": hi,
                     "median": np.median(x) if len(x) else np.nan, "sd": np.std(x, ddof=1) if len(x) > 1 else np.nan,
                     "min": np.min(x) if len(x) else np.nan, "max": np.max(x) if len(x) else np.nan})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scores", type=Path, default=PROJECT_ROOT / "results" / "main_run_scores.csv")
    ap.add_argument("--manual", type=Path, nargs="*", default=[])
    ap.add_argument("--outdir", type=Path)
    ap.add_argument("--perm", type=int, default=20000)
    args = ap.parse_args(argv)

    df = pd.read_csv(args.scores)
    name = args.scores.name.replace("_run_scores.csv", "")
    out = args.outdir or args.scores.parent / f"analysis_{name}"
    out.mkdir(parents=True, exist_ok=True)
    refs = reference_values()
    for b in ("contract_ok", "leaky", "study_exposed", "reported_mismatch"):
        if b in df.columns:
            df[b] = df[b].map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))
    df["split_type"] = df["split_type"].fillna("invalid")
    use_base = "delta_vs_base_S1" in df.columns and df["delta_vs_base_S1"].notna().any()
    dcol = "delta_vs_base_S1" if use_base else "delta_vs_S1"
    dref = refs["base_S1"] if use_base and "base_S1" in refs else refs["S1_group"]
    dlabel = "agent-facing baseline on a leakage-group split" if use_base else "release GBM on S1"
    md = [f"# Analysis of `{args.scores.name}`\n",
          f"Release reference AUPRC (peptide-feature GBM, primary P vs N2): random split S4 {refs['S4_random']:.3f}; leakage-group split S1 "
          f"{refs['S1_group']:.3f}; study-held-out S5 {refs['S5_study']:.3f}; chance {refs['chance']:.3f}.\n"]
    if use_base:
        md.append(f"Agent-facing baseline (same table the agents saw): random {refs['base_S4']:.3f}; leakage-group {refs['base_S1']:.3f}; "
                  f"study-held-out {refs['base_S5']:.3f}.\n")
    else:
        md.append("**Note:** results/reference_baseline.csv not found, so excess AUPRC is measured against the release GBM, which "
                  "uses fewer features than agents do. Run 07_reference_baseline.py and re-score.\n")

    # --- completeness --------------------------------------------------------------------------------------------
    comp = df.groupby(["phase", "condition"]).agg(trials=("run_id", "nunique"), valid=("contract_ok", "sum")).reset_index()
    comp["valid_share"] = comp["valid"] / comp["trials"]
    comp.to_csv(out / "t0_completeness.csv", index=False)
    md += ["## Completeness\n", md_table(comp)]

    # --- split types ---------------------------------------------------------------------------------------------
    st = df.groupby(["phase", "condition"])["split_type"].value_counts().unstack(fill_value=0)
    for t in SPLIT_TYPES:
        if t not in st.columns:
            st[t] = 0
    st = st[list(SPLIT_TYPES)].reset_index()
    st.to_csv(out / "t1_split_types.csv", index=False)
    md += ["## Final split type by condition (counts)\n", md_table(st)]

    valid = df[df["contract_ok"]].copy()
    results = {}
    for phase in (1, 2):
        v = valid[valid["phase"] == phase]
        if v.empty:
            continue
        tab = prop_table(v, "leaky")
        pf = pairwise_fisher(tab)
        counts = np.array([[int(r.k), int(r.n - r.k)] for r in tab.itertuples()])
        chi, p_perm = perm_chi2(counts, B=args.perm)
        tab.to_csv(out / f"t2_leaky_share_phase{phase}.csv", index=False)
        pf.to_csv(out / f"t2_leaky_pairwise_phase{phase}.csv", index=False)
        results[phase] = {"tab": tab, "pf": pf, "chi": chi, "p": p_perm}
        md += [f"## Primary outcome, phase {phase}: share of trials with a group-leaky final split (valid submissions only)\n",
               md_table(tab), f"Permutation chi-square across the three conditions: chi2 = {chi:.2f}, p = {p_perm:.4f} "
               f"({args.perm} permutations).\n\nPairwise Fisher exact tests (Holm-adjusted):\n", md_table(pf, "{:.4f}")]

        d = delta_table(v, dcol)
        d.to_csv(out / f"t3_auprc_excess_phase{phase}.csv", index=False)
        groups = {c: v.loc[v.condition == c, dcol].to_numpy(float) for c in CONDITIONS}
        nonempty = [g[np.isfinite(g)] for g in groups.values() if np.isfinite(g).sum() > 0]
        kw = (float("nan"), float("nan"))
        if len(nonempty) >= 2 and not all(np.all(g == nonempty[0][0]) for g in nonempty):
            kw = stats.kruskal(*nonempty)
        mw = pd.DataFrame(pairwise_mwu(groups))
        mw.to_csv(out / f"t3_auprc_excess_pairwise_phase{phase}.csv", index=False)
        md += [f"## AUPRC above the leakage-controlled reference (recomputed AUPRC minus {dref:.3f}, {dlabel}), phase {phase}\n",
               md_table(d), f"Kruskal-Wallis: H = {kw[0]:.2f}, p = {kw[1]:.4f}.\n\nPairwise Mann-Whitney (Holm), Cliff's delta:\n",
               md_table(mw, "{:.4f}")]

        if "auprc_gap_group" in v.columns:
            ex = v.groupby("condition").agg(n=("run_id", "count"), median_auprc_exposed=("auprc_group_exposed", "median"),
                                            median_auprc_unexposed=("auprc_group_unexposed", "median"),
                                            median_gap=("auprc_gap_group", "median"), n_with_gap=("auprc_gap_group", "count")).reset_index()
            ex.to_csv(out / f"t3b_exposed_vs_unexposed_phase{phase}.csv", index=False)
            md += [f"## Within-run optimism check, phase {phase}: AUPRC on held-out rows that share a leakage group with training "
                   "vs rows that do not (model-agnostic; empty when a split already removes all shared groups)\n", md_table(ex)]

        # H3: among trials that did control leakage groups, how many still share studies with training?
        ctrl = v[v["split_type"].isin(["group_held_out", "group_and_study_held_out"])]
        h3 = ctrl.groupby("condition").agg(group_controlled=("run_id", "count"), still_study_exposed=("study_exposed", "sum")).reset_index()
        h3["share_study_exposed"] = h3["still_study_exposed"] / h3["group_controlled"]
        h3.to_csv(out / f"t4_study_shortcut_phase{phase}.csv", index=False)
        md += [f"## Study shortcut among trials that controlled leakage groups, phase {phase}\n", md_table(h3)]

        # honesty of self-report
        rep = v.groupby("condition").agg(n=("run_id", "count"), mean_reported_minus_recomputed=("reported_gap", "mean"),
                                         mismatch_share=("reported_mismatch", "mean")).reset_index()
        rep.to_csv(out / f"t5_self_report_phase{phase}.csv", index=False)
        md += [f"## Reported vs recomputed AUPRC, phase {phase}\n", md_table(rep)]

    # --- phase 1 -> 2 --------------------------------------------------------------------------------------------
    p1 = valid[valid["phase"] == 1].set_index("run_id")
    p2 = valid[valid["phase"] == 2].set_index("run_id")
    both = p1.index.intersection(p2.index)
    if len(both):
        pair = pd.DataFrame({"condition": p1.loc[both, "condition"], "leaky_1": p1.loc[both, "leaky"], "leaky_2": p2.loc[both, "leaky"],
                             "auprc_1": p1.loc[both, "auprc"], "auprc_2": p2.loc[both, "auprc"],
                             "type_1": p1.loc[both, "split_type"], "type_2": p2.loc[both, "split_type"]})
        pair["fixed"] = pair.leaky_1 & ~pair.leaky_2
        pair["broke"] = ~pair.leaky_1 & pair.leaky_2
        pair["d_auprc"] = pair.auprc_2 - pair.auprc_1
        pair.reset_index().to_csv(out / "t6_paired_runs.csv", index=False)
        rows = []
        for c in list(CONDITIONS) + ["all"]:
            s = pair if c == "all" else pair[pair.condition == c]
            if s.empty:
                continue
            leaky1 = int(s.leaky_1.sum())
            b, cc = int(s.fixed.sum()), int(s.broke.sum())
            dd = s.d_auprc.to_numpy(float)
            try:
                wp = float(stats.wilcoxon(dd).pvalue) if np.any(dd != 0) else 1.0
            except ValueError:
                wp = float("nan")
            rows.append({"condition": c, "n_pairs": len(s), "leaky_before": leaky1, "fixed_after_review": b, "newly_leaky": cc,
                         "share_of_leaky_fixed": b / leaky1 if leaky1 else np.nan, "mcnemar_exact_p": mcnemar_exact(b, cc),
                         "median_change_auprc": float(np.median(dd)), "wilcoxon_p": wp})
        pr = pd.DataFrame(rows)
        pr.to_csv(out / "t6_self_correction.csv", index=False)
        md += ["## Self-review prompt (phase 1 -> phase 2), trials valid in both phases\n", md_table(pr, "{:.4f}")]

    # --- heuristic behaviour flags -------------------------------------------------------------------------------
    flag_cols = [c for c in ("tx_mentions_leakage", "tx_audit_similarity", "tx_audit_overlap", "tx_used_provided_groups",
                             "tx_code_grouped_split", "tx_code_random_split", "tx_escape_release_files", "report_mentions_leakage") if c in df.columns]
    if flag_cols:
        fl = df.copy()
        for c in flag_cols:
            fl[c] = fl[c].map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))
        ft = fl.groupby(["phase", "condition"])[flag_cols].mean().reset_index()
        ft.to_csv(out / "t7_heuristic_flags.csv", index=False)
        md += ["## Heuristic behaviour flags (share of trials; regex-based, check against manual labels)\n", md_table(ft)]
        if "tx_escape_release_files" in fl.columns and fl["tx_escape_release_files"].any():
            md += [f"\n**Warning:** {int(fl['tx_escape_release_files'].sum())} trial-phases touched the study's own release files "
                   "(tx_escape_release_files). Inspect and consider excluding them.\n"]

    # --- manual labels and agreement -----------------------------------------------------------------------------
    labs = [pd.read_csv(p) for p in args.manual]
    if labs:
        key = ["run_id", "phase"]
        for i, l in enumerate(labs, 1):
            md += [f"\nManual label file {i}: {args.manual[i - 1].name} ({len(l)} rows)\n"]
        if len(labs) >= 2:
            m = labs[0].merge(labs[1], on=key, suffixes=("_a", "_b"))
            rows = []
            for col in ("audit_performed", "self_corrected"):
                if f"{col}_a" in m.columns:
                    s = m[[f"{col}_a", f"{col}_b"]].dropna()
                    rows.append({"variable": col, "n": len(s), "percent_agree": float((s.iloc[:, 0] == s.iloc[:, 1]).mean()),
                                 "cohens_kappa": cohen_kappa(s.iloc[:, 0].to_numpy(), s.iloc[:, 1].to_numpy())})
            if rows:
                k = pd.DataFrame(rows)
                k.to_csv(out / "t8_rater_agreement.csv", index=False)
                md += ["## Inter-rater agreement\n", md_table(k)]
        auto = df.assign(auto_audit=df[["tx_audit_similarity", "tx_audit_overlap"]].apply(
            lambda r: any(str(x).strip().lower() in ("true", "1", "1.0") for x in r), axis=1)) if "tx_audit_similarity" in df.columns else None
        if auto is not None and "audit_performed" in labs[0].columns:
            m = labs[0].merge(auto[["run_id", "phase", "auto_audit"]], on=key)
            s = m[["audit_performed", "auto_audit"]].dropna()
            if len(s):
                kk = cohen_kappa(s["audit_performed"].astype(int).to_numpy(), s["auto_audit"].astype(int).to_numpy())
                md += [f"\nManual `audit_performed` vs automatic regex flag: kappa = {kk:.2f} on {len(s)} rows.\n"]

    # --- cost ---------------------------------------------------------------------------------------------------
    if "tx_cost_usd" in df.columns:
        cost = df.groupby(["phase", "condition"]).agg(trials=("run_id", "nunique"), total_cost_usd=("tx_cost_usd", "sum"),
                                                      mean_turns=("tx_num_turns", "mean")).reset_index()
        cost.to_csv(out / "t9_cost.csv", index=False)
        md += ["## Cost and effort (as reported by the CLI)\n", md_table(cost)]

    make_figures(df, valid, refs, out)
    (out / "summary.md").write_text("\n".join(md))
    print(f"analysis written to {out}")
    return 0


def make_figures(df, valid, refs, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 120})
    phases = [p for p in (1, 2) if (df["phase"] == p).any()]
    # Fig 1: split types
    fig, axes = plt.subplots(1, len(phases), figsize=(4.6 * len(phases), 3.8), sharey=True, squeeze=False)
    for ax, phase in zip(axes[0], phases):
        sub = df[df["phase"] == phase]
        bottoms = np.zeros(len(CONDITIONS))
        for t in SPLIT_TYPES[::-1]:
            vals = np.array([(sub[(sub.condition == c)]["split_type"] == t).sum() for c in CONDITIONS], float)
            tot = np.array([max(1, (sub.condition == c).sum()) for c in CONDITIONS], float)
            share = vals / tot
            if share.sum() == 0:
                continue
            ax.bar(range(len(CONDITIONS)), share, bottom=bottoms, color=OKABE[t], label=SPLIT_TYPE_LABELS[t], edgecolor="white", width=0.7)
            for i, (s, b, n) in enumerate(zip(share, bottoms, vals)):
                if n > 0:
                    ax.text(i, b + s / 2, int(n), ha="center", va="center", fontsize=9)
            bottoms += share
        ax.set_xticks(range(len(CONDITIONS)), [CONDITION_LABELS[c] for c in CONDITIONS], rotation=15)
        ax.set_title("Phase 1: first attempt" if phase == 1 else "Phase 2: after self-review prompt")
        ax.set_ylim(0, 1)
    axes[0][0].set_ylabel("Share of trials")
    h, l = axes[0][-1].get_legend_handles_labels()
    fig.legend(h[::-1], l[::-1], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(out / "fig1_split_types.png", bbox_inches="tight", dpi=200)
    fig.savefig(out / "fig1_split_types.pdf", bbox_inches="tight")
    plt.close(fig)
    # Fig 2: recomputed AUPRC
    fig, axes = plt.subplots(1, len(phases), figsize=(4.4 * len(phases), 3.8), sharey=True, squeeze=False)
    rng = np.random.default_rng(3)
    for ax, phase in zip(axes[0], phases):
        sub = valid[valid["phase"] == phase]
        for i, c in enumerate(CONDITIONS):
            s = sub[sub.condition == c]
            x = i + rng.uniform(-0.15, 0.15, len(s))
            ax.scatter(x, s["auprc"], c=[OKABE.get(t, "#999999") for t in s["split_type"]], s=38, edgecolor="black", linewidth=0.4, zorder=3)
            if len(s):
                ax.hlines(s["auprc"].median(), i - 0.3, i + 0.3, color="black", lw=2, zorder=4)
        if "base_S4" in refs:
            lines = (("baseline, random split", refs["base_S4"], "--", "bottom"), ("baseline, leakage-group split", refs["base_S1"], "-.", "bottom"),
                     ("baseline, study held out", refs["base_S5"], ":", "bottom"), ("chance", refs["chance"], (0, (1, 3)), "top"))
        else:
            lines = (("release GBM, random (S4)", refs["S4_random"], "--", "bottom"), ("release GBM, group (S1)", refs["S1_group"], "-.", "bottom"),
                     ("release GBM, study (S5)", refs["S5_study"], ":", "bottom"), ("chance", refs["chance"], (0, (1, 3)), "top"))
        for name, val, ls, va in lines:
            ax.axhline(val, color="#555", ls=ls, lw=1)
            if phase == phases[-1]:
                ax.text(len(CONDITIONS) - 0.45, val + (0.004 if va == "bottom" else -0.004), f"{name} {val:.2f}", fontsize=7.5,
                        ha="right", va=va, color="#333")
        ax.set_xticks(range(len(CONDITIONS)), [CONDITION_LABELS[c] for c in CONDITIONS], rotation=15)
        ax.set_title("Phase 1" if phase == 1 else "Phase 2")
    axes[0][0].set_ylabel("AUPRC recomputed from predictions")
    fig.tight_layout()
    fig.savefig(out / "fig2_auprc.png", bbox_inches="tight", dpi=200)
    fig.savefig(out / "fig2_auprc.pdf", bbox_inches="tight")
    plt.close(fig)
    # Fig 3: paired change
    p1 = valid[valid["phase"] == 1].set_index("run_id")
    p2 = valid[valid["phase"] == 2].set_index("run_id")
    both = p1.index.intersection(p2.index)
    if len(both):
        fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
        for ax, c in zip(axes, CONDITIONS):
            ids = [i for i in both if p1.loc[i, "condition"] == c]
            for i in ids:
                ax.plot([0, 1], [p1.loc[i, "auprc"], p2.loc[i, "auprc"]], marker="o", color="#0072B2", alpha=0.7, lw=1.2)
            ax.axhline(refs["S1_group"], color="#555", ls="-.", lw=1)
            ax.set_xticks([0, 1], ["Phase 1", "Phase 2"])
            ax.set_title(CONDITION_LABELS[c])
        axes[0].set_ylabel("AUPRC recomputed")
        fig.tight_layout()
        fig.savefig(out / "fig3_paired_change.png", bbox_inches="tight", dpi=200)
        fig.savefig(out / "fig3_paired_change.pdf", bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
