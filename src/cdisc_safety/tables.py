"""Standard clinical safety summaries built from ADaM datasets.

All adverse-event counts are numbers of subjects (not events) in the safety
population, so each subject counts once per row however many events they had.
"""

from __future__ import annotations

import pandas as pd

from cdisc_safety.stats import newcombe_diff
from cdisc_safety.terminology import CONTROL_ARM, RELATED_TERMS

HYS_ALT_AST_ULN = 3.0
HYS_BILI_ULN = 2.0


def arm_order(adsl: pd.DataFrame) -> list[str]:
    """Treatment arms ordered by their numeric code."""
    return adsl.drop_duplicates("TRT01A").sort_values("TRT01AN")["TRT01A"].tolist()


def safety_n(adsl: pd.DataFrame) -> pd.Series:
    """Number of subjects in the safety population per arm, plus a Total column."""
    saf = adsl[adsl["SAFFL"].eq("Y")]
    n = saf.groupby("TRT01A")["USUBJID"].nunique().reindex(arm_order(adsl), fill_value=0)
    n["Total"] = saf["USUBJID"].nunique()
    return n


def fmt_np(n: int, denom: int) -> str:
    """Format a count and percentage as 'n (x.x%)'."""
    if denom == 0:
        return "0"
    return f"{n} ({100 * n / denom:.1f}%)"


def _subjects_by_arm(df: pd.DataFrame, arms: list[str]) -> pd.Series:
    counts = df.groupby("TRTA")["USUBJID"].nunique().reindex(arms, fill_value=0)
    counts["Total"] = df["USUBJID"].nunique()
    return counts


def demographics(adsl: pd.DataFrame) -> pd.DataFrame:
    """Demographic summary by arm (safety population)."""
    saf = adsl[adsl["SAFFL"].eq("Y")]
    arms = arm_order(adsl)
    n = safety_n(adsl)
    cols = arms + ["Total"]
    rows: list[dict] = [{"Characteristic": "N", **{c: str(int(n[c])) for c in cols}}]

    def subset(col: str) -> list[pd.DataFrame]:
        return [saf[saf["TRT01A"].eq(a)] for a in arms] + [saf]

    ages = subset("AGE")
    rows.append(
        {
            "Characteristic": "Age, mean (SD)",
            **{c: f"{g['AGE'].mean():.1f} ({g['AGE'].std():.1f})" for c, g in zip(cols, ages, strict=True)},
        }
    )
    rows.append(
        {
            "Characteristic": "Age, median (min-max)",
            **{c: f"{g['AGE'].median():.0f} ({g['AGE'].min()}-{g['AGE'].max()})" for c, g in zip(cols, ages, strict=True)},
        }
    )
    for var, title in (("AGEGR1", "Age group"), ("SEX", "Sex"), ("RACE", "Race")):
        if var == "AGEGR1":
            levels = saf.drop_duplicates("AGEGR1").sort_values("AGEGR1N")["AGEGR1"].tolist()
        else:
            levels = saf[var].value_counts().index.tolist()
        for level in levels:
            counts = [int((g[var] == level).sum()) for g in subset(var)]
            rows.append(
                {"Characteristic": f"{title}: {level}", **{c: fmt_np(k, int(n[c])) for c, k in zip(cols, counts, strict=True)}}
            )
    return pd.DataFrame(rows)


def teae_overview(adsl: pd.DataFrame, adae: pd.DataFrame) -> pd.DataFrame:
    """Overview of treatment-emergent adverse events (TEAEs) by arm."""
    arms = arm_order(adsl)
    n = safety_n(adsl)
    cols = arms + ["Total"]
    teae = adae[adae["TRTEMFL"].eq("Y") & adae["SAFFL"].eq("Y")] if not adae.empty else adae
    categories = [
        ("Any TEAE", lambda d: d),
        ("Any serious TEAE", lambda d: d[d["AESER"].eq("Y")]),
        ("Any grade >=3 TEAE", lambda d: d[pd.to_numeric(d["ATOXGR"], errors="coerce") >= 3]),
        ("Any treatment-related TEAE", lambda d: d[d["AEREL"].isin(RELATED_TERMS)]),
        ("TEAE leading to treatment discontinuation", lambda d: d[d["AEACN"].eq("DRUG WITHDRAWN")]),
        ("TEAE leading to death", lambda d: d[d["AEOUT"].eq("FATAL")]),
    ]
    rows = []
    for label, select in categories:
        sub = select(teae) if not teae.empty else teae
        counts = _subjects_by_arm(sub, arms) if not sub.empty else pd.Series(0, index=cols)
        rows.append(
            {
                "Category": label,
                **{c: fmt_np(int(counts[c]), int(n[c])) for c in cols},
                **{f"_n_{c}": int(counts[c]) for c in cols},
            }
        )
    return pd.DataFrame(rows)


def teae_by_soc_pt(adsl: pd.DataFrame, adae: pd.DataFrame) -> pd.DataFrame:
    """Subjects with TEAEs by system organ class and preferred term, sorted by total frequency."""
    arms = arm_order(adsl)
    n = safety_n(adsl)
    cols = arms + ["Total"]
    out_cols = ["SOC", "PT", *cols, "_total"]
    teae = adae[adae["TRTEMFL"].eq("Y") & adae["SAFFL"].eq("Y")] if not adae.empty else adae
    if teae.empty:
        return pd.DataFrame(columns=out_cols)
    rows = []
    for soc, soc_df in teae.groupby("AEBODSYS"):
        soc_counts = _subjects_by_arm(soc_df, arms)
        rows.append(
            {
                "SOC": soc,
                "PT": "",
                **{c: fmt_np(int(soc_counts[c]), int(n[c])) for c in cols},
                "_total": int(soc_counts["Total"]),
                "_soc_total": int(soc_counts["Total"]),
            }
        )
        for pt, pt_df in soc_df.groupby("AEDECOD"):
            pt_counts = _subjects_by_arm(pt_df, arms)
            rows.append(
                {
                    "SOC": soc,
                    "PT": pt,
                    **{c: fmt_np(int(pt_counts[c]), int(n[c])) for c in cols},
                    "_total": int(pt_counts["Total"]),
                    "_soc_total": int(soc_counts["Total"]),
                }
            )
    df = pd.DataFrame(rows)
    df["_is_soc"] = df["PT"].eq("")
    df = df.sort_values(["_soc_total", "SOC", "_is_soc", "_total"], ascending=[False, True, False, False])
    return df[out_cols].reset_index(drop=True)


def risk_differences(adsl: pd.DataFrame, adae: pd.DataFrame, control: str = CONTROL_ARM) -> pd.DataFrame:
    """Risk difference (active minus control) with Newcombe 95% CI for each TEAE preferred term."""
    cols = [
        "PT",
        "SOC",
        "Arm",
        "n_active",
        "N_active",
        "n_control",
        "N_control",
        "Pct_active",
        "Pct_control",
        "Diff",
        "Lower",
        "Upper",
    ]
    n = safety_n(adsl)
    if adae.empty or control not in n.index:
        return pd.DataFrame(columns=cols)
    teae = adae[adae["TRTEMFL"].eq("Y") & adae["SAFFL"].eq("Y")]
    rows = []
    for (soc, pt), g in teae.groupby(["AEBODSYS", "AEDECOD"]):
        counts = g.groupby("TRTA")["USUBJID"].nunique()
        xc, nc = int(counts.get(control, 0)), int(n[control])
        for arm in arm_order(adsl):
            if arm == control:
                continue
            xa, na = int(counts.get(arm, 0)), int(n[arm])
            d, lo, hi = newcombe_diff(xa, na, xc, nc)
            rows.append(
                {
                    "PT": pt,
                    "SOC": soc,
                    "Arm": arm,
                    "n_active": xa,
                    "N_active": na,
                    "n_control": xc,
                    "N_control": nc,
                    "Pct_active": 100 * xa / na if na else float("nan"),
                    "Pct_control": 100 * xc / nc if nc else float("nan"),
                    "Diff": 100 * d,
                    "Lower": 100 * lo,
                    "Upper": 100 * hi,
                }
            )
    return pd.DataFrame(rows, columns=cols).sort_values(["Diff"], ascending=False).reset_index(drop=True)


_SEVERITY_RANK = {"": 0, "NORMAL": 1, "LOW": 2, "HIGH": 3}
_RANK_LABEL = {v: k for k, v in _SEVERITY_RANK.items()}


def lab_shift(adlb: pd.DataFrame) -> pd.DataFrame:
    """Shift from baseline range indicator to worst post-baseline indicator, by parameter and arm."""
    cols = ["PARAMCD", "TRTA", "BNRIND", "Worst post-baseline", "Subjects"]
    if adlb.empty:
        return pd.DataFrame(columns=cols)
    post = adlb[adlb["ABLFL"].ne("Y") & (adlb["ADY"].fillna(0) > 1) & adlb["ANRIND"].ne("") & adlb["BNRIND"].ne("")]
    if post.empty:
        return pd.DataFrame(columns=cols)
    ranked = post.assign(_rank=post["ANRIND"].map(_SEVERITY_RANK).fillna(0))
    worst = ranked.groupby(["PARAMCD", "TRTA", "USUBJID", "BNRIND"])["_rank"].max().reset_index()
    worst["ANRIND"] = worst["_rank"].map(_RANK_LABEL)
    table = worst.groupby(["PARAMCD", "TRTA", "BNRIND", "ANRIND"])["USUBJID"].nunique().reset_index()
    table.columns = cols
    return table


def hys_law(adlb: pd.DataFrame) -> pd.DataFrame:
    """Per-subject peak post-baseline ALT/AST and bilirubin as multiples of ULN (eDISH data)."""
    cols = ["USUBJID", "TRTA", "Peak ALT/AST xULN", "Peak bilirubin xULN", "Potential Hy's law"]
    if adlb.empty:
        return pd.DataFrame(columns=cols)
    post = adlb[adlb["ABLFL"].ne("Y") & (adlb["ADY"].fillna(0) > 1) & adlb["PARAMCD"].isin(["ALT", "AST", "BILI"])]
    if post.empty:
        return pd.DataFrame(columns=cols)
    wide = post.pivot_table(index=["USUBJID", "TRTA"], columns="PARAMCD", values="R2ANRHI", aggfunc="max").reset_index()
    for p in ("ALT", "AST", "BILI"):
        if p not in wide.columns:
            wide[p] = float("nan")
    wide["Peak ALT/AST xULN"] = wide[["ALT", "AST"]].max(axis=1)
    wide["Peak bilirubin xULN"] = wide["BILI"]
    wide["Potential Hy's law"] = (wide["Peak ALT/AST xULN"] >= HYS_ALT_AST_ULN) & (wide["Peak bilirubin xULN"] >= HYS_BILI_ULN)
    return wide[cols].sort_values("Peak ALT/AST xULN", ascending=False).reset_index(drop=True)


def lab_mean_change(adlb: pd.DataFrame) -> pd.DataFrame:
    """Mean change from baseline with standard error, by parameter, arm and visit."""
    cols = ["PARAMCD", "PARAM", "TRTA", "AVISITN", "AVISIT", "n", "Mean CHG", "SE"]
    if adlb.empty:
        return pd.DataFrame(columns=cols)
    post = adlb[adlb["ABLFL"].ne("Y") & adlb["CHG"].notna() & (adlb["AVISITN"] > 1)]
    if post.empty:
        return pd.DataFrame(columns=cols)
    g = post.groupby(["PARAMCD", "PARAM", "TRTA", "AVISITN", "AVISIT"])["CHG"]
    out = g.agg(["count", "mean", "std"]).reset_index()
    out["SE"] = out["std"] / out["count"].pow(0.5)
    out = out.rename(columns={"count": "n", "mean": "Mean CHG"})
    return out[cols]
