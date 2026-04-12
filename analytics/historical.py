"""Business logic for the historical analysis page.

Pure computation — no Streamlit imports. Functions take DataFrames and
return plain data structures (dicts, lists, DataFrames).
"""

from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, leaves_list, linkage
from scipy.spatial.distance import squareform
from scipy.stats import fisher_exact, ttest_ind

from core.constants import DAY_ABBR, DAY_ORDER, DAY_TO_ABBR

# ── Statistical helpers ──────────────────────────────────────────────────────


def phi_and_p(a, b):
    """Compute phi coefficient and Fisher exact p-value for two binary arrays."""
    n11 = int(((a == 1) & (b == 1)).sum())
    n10 = int(((a == 1) & (b == 0)).sum())
    n01 = int(((a == 0) & (b == 1)).sum())
    n00 = int(((a == 0) & (b == 0)).sum())
    denom = ((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00)) ** 0.5
    phi = float((n11 * n00 - n10 * n01) / denom) if denom else 0.0
    _, p = fisher_exact([[n11, n10], [n01, n00]])
    return phi, float(p), n11, n10, n01, n00


# ── DOW threshold ────────────────────────────────────────────────────────────


def compute_dow_threshold(pivot: pd.DataFrame) -> float:
    """75th percentile of |day_rate - habit_avg| across all habit x day combos (min 4 occurrences)."""
    deltas = []
    for h in pivot.columns:
        c = pivot[h].dropna().astype(float)
        havg = c.mean() * 100
        for _day, grp in c.groupby(c.index.day_name()):
            if len(grp) >= 4:
                deltas.append(abs(grp.mean() * 100 - havg))
    return float(np.percentile(deltas, 75)) if deltas else 15.0


# ── Per-habit trend rows ────────────────────────────────────────────────────


def compute_trend_rows(pivot: pd.DataFrame, today: date, dow_threshold: float) -> list[dict]:
    """Compute per-habit breakdown data: rate, streak, trends, DOW, tier."""
    dow_abbr = DAY_TO_ABBR
    dow_order = DAY_ABBR
    rows = []

    for habit in pivot.columns:
        col = pivot[habit]
        rate = col.mean() * 100
        from core.stats import compute_streak

        cur, best = compute_streak(col.fillna(False).astype(bool))

        done_dates = col[col == True].index
        days_since = (today - done_dates[-1].date()).days if len(done_dates) else None

        vals = col.dropna().astype(float)

        def _window_mean(s, start, end):
            w = s.iloc[start:end] if end else s.iloc[start:]
            m = w.mean()
            return None if pd.isna(m) or len(w) == 0 else float(m) * 100

        r14 = _window_mean(vals, -14, None) if len(vals) >= 14 else None
        p14 = _window_mean(vals, -28, -14) if len(vals) >= 28 else None
        trend14 = (r14 - p14) if (r14 is not None and p14 is not None) else None

        r28 = _window_mean(vals, -28, None)
        p28 = _window_mean(vals, -56, -28) if len(vals) >= 56 else None
        trend28 = (r28 - p28) if (r28 is not None and p28 is not None) else None

        sort_trend = trend28 if trend28 is not None else (trend14 if trend14 is not None else 0.0)
        urgency = 0 if sort_trend < -10 else 2 if sort_trend > 10 else 1
        tier_rate = r28 if r28 is not None else rate
        tier_order = 0 if tier_rate < 50 else 1 if tier_rate < 80 else 2
        tier_name = ["Needs Attention", "Okay", "Solid"][tier_order]

        # DOW analysis
        col_clean = col.dropna().astype(float)
        dow_rates = col_clean.groupby(col_clean.index.day_name())
        best_days, struggle_days = [], []
        for day, group in dow_rates:
            if len(group) < 4:
                continue
            delta = group.mean() * 100 - rate
            if delta >= dow_threshold:
                best_days.append(dow_abbr[day])
            elif delta <= -dow_threshold:
                struggle_days.append(dow_abbr[day])
        best_days = [d for d in dow_order if d in best_days]
        struggle_days = [d for d in dow_order if d in struggle_days]

        rows.append(
            {
                "Habit": habit,
                "Rate": rate,
                "Rate28": r28,
                "Trend14": trend14,
                "Trend28": trend28,
                "CurStreak": cur,
                "BestStreak": best,
                "DaysSince": days_since,
                "Tier": tier_name,
                "TierOrder": tier_order,
                "Urgency": urgency,
                "BestDays": best_days,
                "StruggleDays": struggle_days,
            }
        )

    return rows


def build_trend_df(trend_rows: list[dict]) -> pd.DataFrame:
    """Sort and filter trend rows into a display-ready DataFrame."""
    return (
        pd.DataFrame([r for r in trend_rows if r["Rate28"] is not None])
        .assign(Trend28Sort=lambda d: d["Trend28"].fillna(0))
        .assign(Rate28Sort=lambda d: d["Rate28"].fillna(d["Rate"]))
        .sort_values(["TierOrder", "Trend28Sort", "Rate28Sort"], ascending=[True, True, False])
    )


# ── DOW analysis ─────────────────────────────────────────────────────────────


def compute_dow_data(pivot: pd.DataFrame, daily_rate: pd.Series, dow_threshold: float) -> dict:
    """Compute day-of-week analysis data.

    Returns a dict with keys:
      - dow_avg: Series of overall daily rate by day name
      - dow_overall: float overall average
      - pills_per_day: dict[day_name -> list[(habit, deviation)]]
    """
    dow_overall = daily_rate.mean()
    dow_avg = daily_rate.groupby(daily_rate.index.day_name()).mean().reindex(DAY_ORDER)

    pills_per_day = {}
    for day in DAY_ORDER:
        day_habits = []
        for h in pivot.columns:
            col = pivot[h].dropna().astype(float)
            on_day = col[col.index.day_name() == day]
            if len(on_day) < 4:
                continue
            dev = on_day.mean() * 100 - col.mean() * 100
            if abs(dev) >= dow_threshold:
                day_habits.append((h, dev))
        pills_per_day[day] = sorted(day_habits, key=lambda x: x[1])

    return {
        "dow_avg": dow_avg,
        "dow_overall": dow_overall,
        "pills_per_day": pills_per_day,
    }


def compute_dow_heatmap_data(pivot: pd.DataFrame, daily_rate: pd.Series) -> dict:
    """Compute per-habit DOW heatmap data.

    Returns dict with z_vals, cell_text, hover_text, y_labels (habits + daily avg),
    and day_abbr for x-axis.
    """
    habits_dow = pivot.mean().sort_values(ascending=False).index.tolist()

    z_dow, cell_text, hover_text = [], [], []
    for h in habits_dow:
        col = pivot[h].dropna().astype(float) * 100
        by_rate = col.groupby(col.index.day_name()).mean().reindex(DAY_ORDER)
        by_n = col.groupby(col.index.day_name()).count().reindex(DAY_ORDER)
        z_dow.append(by_rate.values)
        cell_text.append([f"{r:.0f}%" if not np.isnan(r) else "" for r in by_rate.values])
        hover_text.append(
            [
                f"{r:.0f}% (n={int(n)})" if not np.isnan(r) else "no data"
                for r, n in zip(by_rate.values, by_n.values, strict=True)
            ]
        )

    z_dow = np.array(z_dow, dtype=float)
    overall_dow = daily_rate.groupby(daily_rate.index.day_name()).mean().reindex(DAY_ORDER)
    overall_n = daily_rate.groupby(daily_rate.index.day_name()).count().reindex(DAY_ORDER)

    z_full = np.vstack([z_dow, overall_dow.values.reshape(1, -1)])
    y_full = habits_dow + ["── Daily avg"]
    cell_text_full = cell_text + [[f"{v:.0f}%" if not np.isnan(v) else "" for v in overall_dow]]
    hover_text_full = hover_text + [
        [
            f"{r:.0f}% (n={int(n)})" if not np.isnan(r) else "no data"
            for r, n in zip(overall_dow.values, overall_n.values, strict=True)
        ]
    ]

    return {
        "z": z_full,
        "y_labels": y_full,
        "cell_text": cell_text_full,
        "hover_text": hover_text_full,
        "day_abbr": DAY_ABBR,
    }


# ── Keystone habits ──────────────────────────────────────────────────────────


def compute_keystone_habits(pivot: pd.DataFrame, min_days: int = 5) -> list[dict]:
    """Identify keystone habits via Welch's t-test (p < 0.05)."""
    ks_rows = []
    for habit in pivot.columns:
        habit_col = pivot[habit].dropna()
        done_idx = habit_col[habit_col == True].index
        skip_idx = habit_col[habit_col == False].index
        if len(done_idx) < min_days or len(skip_idx) < min_days:
            continue

        other_habits = [h for h in pivot.columns if h != habit]
        base = pivot.loc[habit_col.index, other_habits]
        other_rate = base.mean(axis=1) * 100
        done_vals = other_rate[other_rate.index.isin(done_idx)].dropna().astype(float)
        skip_vals = other_rate[other_rate.index.isin(skip_idx)].dropna().astype(float)
        done_rate = done_vals.mean()
        skip_rate = skip_vals.mean()
        _, p_val = ttest_ind(done_vals, skip_vals, equal_var=False)

        lifted, suppressed = [], []
        for other in other_habits:
            d = base.loc[done_idx, other].dropna().astype(float)
            s = base.loc[skip_idx, other].dropna().astype(float)
            if len(d) >= 5 and len(s) >= 5:
                _, p_other = ttest_ind(d, s, equal_var=False)
                if p_other < 0.05:
                    delta = (d.mean() - s.mean()) * 100
                    if delta > 0:
                        lifted.append((other, delta))
                    else:
                        suppressed.append((other, delta))
        lifted.sort(key=lambda x: x[1], reverse=True)
        suppressed.sort(key=lambda x: x[1])

        if p_val >= 0.05:
            continue

        completion_rate = habit_col.mean() * 100
        overall_median = other_rate.median()
        consistency = (done_vals >= overall_median).mean() * 100
        ks_rows.append(
            {
                "Habit": habit,
                "CompletionRate": completion_rate,
                "Impact": done_rate - skip_rate,
                "Consistency": consistency,
                "Done Days": len(done_vals),
                "Skip Days": len(skip_vals),
                "p": p_val,
                "Lifted": lifted,
                "Suppressed": suppressed,
                "Total": len(other_habits),
            }
        )

    return ks_rows


# ── Momentum ─────────────────────────────────────────────────────────────────


def compute_momentum(pivot: pd.DataFrame) -> list[dict]:
    """Compute habit momentum via Fisher exact test (p < 0.05)."""
    mom_rows = []
    for habit in pivot.columns:
        col = pivot[habit].dropna()
        if len(col) < 10:
            continue
        both = pd.DataFrame({"today": col, "yesterday": col.shift(1)}).dropna()
        if len(both) < 5:
            continue
        p_done = both[both["yesterday"] == True]["today"].mean()
        p_skip = both[both["yesterday"] == False]["today"].mean()
        if pd.isna(p_done) or pd.isna(p_skip):
            continue

        n11 = int(((both["yesterday"] == True) & (both["today"] == True)).sum())
        n10 = int(((both["yesterday"] == True) & (both["today"] == False)).sum())
        n01 = int(((both["yesterday"] == False) & (both["today"] == True)).sum())
        n00 = int(((both["yesterday"] == False) & (both["today"] == False)).sum())
        _, p_val = fisher_exact([[n11, n10], [n01, n00]])
        if p_val >= 0.05:
            continue

        triple = pd.DataFrame(
            {
                "today": col,
                "yesterday": col.shift(1),
                "day_before": col.shift(2),
            }
        ).dropna()
        streak_rows = triple[(triple["yesterday"] == True) & (triple["day_before"] == True)]
        streak_rate = streak_rows["today"].mean() * 100 if len(streak_rows) >= 5 else None
        completion_rate = col.mean() * 100

        mom_rows.append(
            {
                "Habit": habit,
                "CompletionRate": completion_rate,
                "Momentum": (p_done - p_skip) * 100,
                "After1": p_done * 100,
                "Recovery": p_skip * 100,
                "StreakRate": streak_rate,
                "p": p_val,
            }
        )

    return mom_rows


# ── Correlations ─────────────────────────────────────────────────────────────


def compute_correlations(pivot: pd.DataFrame, min_shared: int = 20) -> dict:
    """Compute phi correlation matrix, clustering, and notable pairs.

    Returns a dict with keys:
      - habits_list: ordered list of habit names (cluster-ordered if possible)
      - cluster_labels: list of int cluster labels (or None)
      - pair_rows: list of dicts with pair correlation data
      - phi_matrix: n x n numpy array
    """
    habits_orig = list(pivot.columns)
    n = len(habits_orig)

    phi_matrix = np.full((n, n), np.nan)
    np.fill_diagonal(phi_matrix, 1.0)
    pair_rows = []

    for i in range(n):
        for j in range(i):
            h1, h2 = habits_orig[i], habits_orig[j]
            shared = pivot[[h1, h2]].dropna().astype(int)
            if len(shared) < min_shared:
                continue
            a, b = shared[h1].values, shared[h2].values
            phi, p, n11, n10, n01, n00 = phi_and_p(a, b)
            phi_matrix[i][j] = phi_matrix[j][i] = phi
            pair_rows.append(
                {
                    "Habit A": h1,
                    "A Rate": a.mean() * 100,
                    "Habit B": h2,
                    "B Rate": b.mean() * 100,
                    "Both Done": n11 / len(a) * 100,
                    "Phi": phi,
                    "P": p,
                    "Days": len(shared),
                }
            )

    # Impute missing pairs
    known_phis = phi_matrix[~np.isnan(phi_matrix) & ~np.eye(n, dtype=bool)]
    impute_val = float(np.mean(known_phis)) if len(known_phis) else 0.0
    phi_imputed = np.where(np.isnan(phi_matrix), impute_val, phi_matrix)

    # Cluster
    habits_list = list(habits_orig)
    cluster_labels = None
    if n > 2:
        dist = np.clip(1 - phi_imputed, 0, 2)
        np.fill_diagonal(dist, 0)
        Z = linkage(squareform(dist), method="average")
        order = leaves_list(Z)
        cluster_labels_orig = fcluster(Z, t=0.7, criterion="distance")
        habits_list = [habits_orig[i] for i in order]
        cluster_labels = [int(cluster_labels_orig[i]) for i in order]

    return {
        "habits_list": habits_list,
        "cluster_labels": cluster_labels,
        "pair_rows": pair_rows,
        "phi_matrix": phi_matrix,
        "min_shared": min_shared,
    }


def validate_clusters(
    cluster_labels: list[int],
    habits_list: list[str],
    pivot: pd.DataFrame,
    min_shared: int = 20,
) -> list[tuple[list[str], float]]:
    """Validate clusters: require avg phi >= 0.3 and >= 50% pair coverage."""
    raw_clusters = defaultdict(list)
    for habit, label in zip(habits_list, cluster_labels, strict=True):
        raw_clusters[label].append(habit)

    validated = []
    for members in raw_clusters.values():
        if len(members) < 3:
            continue
        pairs_total = len(members) * (len(members) - 1) / 2
        known_phi_vals = []
        for ii, ha in enumerate(members):
            for jj, hb in enumerate(members):
                if jj >= ii:
                    continue
                shared = pivot[[ha, hb]].dropna().astype(int)
                if len(shared) < min_shared:
                    continue
                phi, _, *_ = phi_and_p(shared[ha].values, shared[hb].values)
                known_phi_vals.append(phi)
        if not known_phi_vals:
            continue
        coverage = len(known_phi_vals) / pairs_total
        avg_phi = float(np.mean(known_phi_vals))
        if avg_phi >= 0.3 and coverage >= 0.5:
            validated.append((members, avg_phi))

    return sorted(validated, key=lambda x: x[1], reverse=True)


def build_correlation_display(
    habits_list: list[str], pivot: pd.DataFrame, min_shared: int = 20
) -> tuple[np.ndarray, np.ndarray]:
    """Build lower-triangle display matrix and text matrix for the correlation heatmap."""
    n = len(habits_list)
    corr_display = np.full((n, n), np.nan)
    corr_text = np.full((n, n), "", dtype=object)

    for i, h1 in enumerate(habits_list):
        for j, h2 in enumerate(habits_list):
            if j >= i:
                continue
            shared = pivot[[h1, h2]].dropna().astype(int)
            if len(shared) < min_shared:
                corr_text[i][j] = "—"
                continue
            a, b = shared[h1].values, shared[h2].values
            phi, _, *_ = phi_and_p(a, b)
            corr_display[i][j] = phi
            corr_text[i][j] = f"{phi:.2f}"

    return corr_display, corr_text


# ── Lead/Lag correlations ────────────────────────────────────────────────────


def compute_lead_lag(pivot: pd.DataFrame, min_shared: int = 20) -> list[dict]:
    """Compute T-1 lead/lag correlations between all habit pairs."""
    lag_rows = []
    habits = list(pivot.columns)
    pivot_sorted = pivot.sort_index()

    for lead_habit in habits:
        for lag_habit in habits:
            if lead_habit == lag_habit:
                continue
            combined = (
                pd.DataFrame(
                    {
                        "lead": pivot_sorted[lead_habit].shift(1),
                        "lag": pivot_sorted[lag_habit],
                    }
                )
                .dropna()
                .astype(int)
            )
            if len(combined) < min_shared:
                continue
            a, b = combined["lead"].values, combined["lag"].values
            phi, p, n11, n10, n01, n00 = phi_and_p(a, b)
            lag_rows.append(
                {
                    "Yesterday (Lead)": lead_habit,
                    "Today (Lag)": lag_habit,
                    "Lead Rate": a.mean() * 100,
                    "Lag Rate": b.mean() * 100,
                    "Both": n11 / len(a) * 100,
                    "Phi": phi,
                    "P": p,
                    "Days": len(combined),
                }
            )

    return lag_rows


# ── Consistency heatmap data ─────────────────────────────────────────────────


def compute_consistency_data(pivot: pd.DataFrame) -> dict:
    """Prepare data for the consistency heatmap.

    Returns dict with z_combined, y_labels, custom_combined, date_strs,
    tick_vals, tick_text.
    """
    habits_sorted = pivot.mean().sort_values(ascending=False).index.tolist()
    habit_rates_map = (pivot.mean() * 100).to_dict()
    y_labels = [f"{h}  {habit_rates_map[h]:.0f}%" for h in habits_sorted]

    z_numeric = pivot[habits_sorted].apply(lambda col: col.map({True: 1.0, False: -1.0}))
    z_vals = z_numeric.T.values.astype(float)

    daily_pct = pivot.mean(axis=1) * 100
    daily_z_row = (daily_pct.fillna(0) / 50) - 1
    daily_z_row = daily_z_row.values.reshape(1, -1).astype(float)
    daily_hover = np.array([[f"{v:.0f}% of habits done" for v in daily_pct.values]])

    z_combined = np.vstack([z_vals, daily_z_row])
    y_combined = y_labels + ["── Daily total"]
    custom_habit = np.where(np.isnan(z_vals), "no data", np.where(z_vals == 1, "done", "skipped"))
    custom_combined = np.vstack([custom_habit, daily_hover])

    date_strs = pivot.index.strftime("%Y-%m-%d").tolist()
    month_starts = pivot.index[pivot.index.to_series().dt.day == 1]
    if len(month_starts) >= 1:
        tick_vals = month_starts.strftime("%Y-%m-%d").tolist()
        tick_text = [d.strftime("%b %Y") for d in month_starts]
    else:
        tick_vals = tick_text = None

    return {
        "z": z_combined,
        "y_labels": y_combined,
        "customdata": custom_combined,
        "date_strs": date_strs,
        "tick_vals": tick_vals,
        "tick_text": tick_text,
    }


# ── Single-habit helpers ─────────────────────────────────────────────────────


def compute_single_habit_momentum(h_series: pd.Series) -> dict | None:
    """Compute momentum for a single habit. Returns dict or None if insufficient data."""
    col_clean = h_series.dropna()
    both = pd.DataFrame({"today": col_clean, "yesterday": col_clean.shift(1)}).dropna()
    if len(both) < 5:
        return None
    p_done = both[both["yesterday"] == True]["today"].mean()
    p_skip = both[both["yesterday"] == False]["today"].mean()
    if pd.isna(p_done) or pd.isna(p_skip):
        return None
    momentum = (p_done - p_skip) * 100
    return {
        "after_doing": p_done * 100,
        "after_skipping": p_skip * 100,
        "score": momentum,
    }


def compute_weekly_rhythm_data(h_series: pd.Series) -> dict:
    """Compute weekly rhythm heatmap data for a single habit.

    Returns dict with z, hover, week_labels, tick_x, tick_lbl, dow_labels.
    """
    dates = h_series.index
    week_starts = dates - pd.to_timedelta(dates.dayofweek, unit="D")
    grid_df = pd.DataFrame(
        {
            "week": week_starts,
            "dow": dates.dayofweek,
            "val": h_series.map({True: 1.0, False: -1.0}).values,
        }
    )
    week_grid = grid_df.pivot(index="dow", columns="week", values="val").reindex(index=range(7))
    unique_weeks = week_grid.columns
    week_labels = [f"{w.month}/{w.day}" for w in unique_weeks]
    z = week_grid.values.astype(float)

    hover = np.empty(z.shape, dtype=object)
    for ci, ws in enumerate(unique_weeks):
        for ri in range(7):
            d = ws + pd.Timedelta(days=ri)
            status = "no data" if np.isnan(z[ri, ci]) else ("done" if z[ri, ci] == 1 else "skipped")
            hover[ri, ci] = f"{d.strftime('%b %d, %Y')}: {status}"

    seen_months, tick_x, tick_lbl = set(), [], []
    for i, w in enumerate(unique_weeks):
        mk = (w.year, w.month)
        if mk not in seen_months:
            seen_months.add(mk)
            tick_x.append(week_labels[i])
            tick_lbl.append(w.strftime("%b %Y"))

    return {
        "z": z,
        "hover": hover,
        "week_labels": week_labels,
        "tick_x": tick_x,
        "tick_lbl": tick_lbl,
        "dow_labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    }
