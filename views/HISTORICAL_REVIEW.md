# Historical Review Page — Technical Documentation

This document is a detailed reference for `dashboard/pages/historical_review.py`, a Streamlit page that provides a comprehensive historical analysis of habit data.

## Purpose

The page has two modes:

1. **All Habits view** (default) — aggregate statistics, charts, per-habit breakdown table, day-of-week analysis, keystone habit detection, momentum analysis, correlation matrix, lead/lag correlations, and a consistency heatmap.
2. **Single Habit view** — selected via sidebar dropdown — focused stats, charts, DOW cards, momentum score, and a weekly rhythm heatmap for one habit.

---

## Data Pipeline

### Source

- **`data/habits.json`** — same source as the week review page. JSON keyed by date, values are `{ "Habit Name": true/false }`.

### Loading

`load_data()` is `@st.cache_data`-decorated. Unlike the week review (which loads into a wide DataFrame), this page normalizes into a long-form DataFrame with columns `date`, `habit`, `done` — one row per habit per day. This makes groupby operations and per-habit filtering straightforward.

### Sidebar

The sidebar provides:
- **Date range presets** — 30d, 90d, 180d, YTD, All (buttons that set session state and rerun)
- **Date pickers** — "From" and "To" date inputs
- **Habit focus dropdown** — "All habits" or a specific habit name
- **Extract/Reload buttons** — via the shared `sidebar.py` module

All subsequent analysis uses only the filtered date range.

---

## Helper Functions

### `rate_color(v)`
Maps a 0–100 percentage to a hex color: green (>=80), yellow (>=50), red (<50).

### `compute_streak(bool_series)`
Scans a boolean series to return `(current_streak, best_streak)`. Current streak counts backwards from the end; best streak tracks the longest consecutive run.

### `compute_slope(series)`
Fits a linear regression on a 7-day smoothed version of a 0–100 rate series. Returns `(slope_per_day, r_squared, n_points, volatile)`. A series is flagged as "volatile" when R² < 0.15 and the standard deviation of the smoothed series exceeds 15 — meaning there's real variance but it's non-linear (swings rather than a trend).

### `trend_label(total_change, r2, volatile)`
Converts slope output to a human label: "Improving" (>5pp total change), "Declining" (<-5pp), "Volatile" (low R² + high variance), or "Stable" (everything else).

### `phi_and_p(a, b)`
Computes the phi coefficient (measure of association for two binary variables) and Fisher exact test p-value from two integer arrays. Returns `(phi, p, n11, n10, n01, n00)` — the correlation, significance, and the four cells of the 2x2 contingency table.

---

## Page Sections — All Habits View

### 1. Stats Row

Six top-level metrics:

| Metric | Definition |
|---|---|
| **Days tracked** | Number of days in the selected range |
| **Avg completion** | Mean daily completion rate across all habits |
| **Current streak** | Consecutive days from the end where daily rate >= 80% |
| **Best streak** | Longest run of days with >= 80% daily rate |
| **28d trend** | Last 28 days avg minus prior 28 days avg (Improving/Declining/Stable) |
| **14d trend** | Last 14 days avg minus prior 14 days avg |

The trend thresholds here are >=10pp for "Improving" and <=-10pp for "Declining" (wider than the per-habit table's +-10pp, same threshold).

### 2. Completion Charts

Three chart functions render the overall daily completion rate at different aggregations:

#### `daily_chart(rate_series, title)`
Bar chart of daily values (colored by rate_color) plus a 7-day and 28-day moving average line. The 7-day MA (blue solid) shows weekly rhythm; the 28-day MA (amber dotted) shows monthly trend.

#### `weekly_chart(rate_series)`
Weekly bars (resampled Monday–Sunday) with text labels and a 4-week MA line.

#### `monthly_chart(rate_series)`
Monthly bars with a 3-month MA line.

All three use transparent backgrounds with dark gridlines for dark-mode rendering.

### 3. Per-Habit Breakdown Table

A custom HTML table showing every habit with sufficient data (>= 28 days for the 28d rate column). Each habit row includes:

| Column | Definition |
|---|---|
| **Habit** | Habit name |
| **28d Rate** | Completion rate over the last 28 days (colored by rate_color) |
| **Streak** | Current streak + best streak. Green = 3+ days active, amber = 1–2 days, red = broken (shows days since last done) |
| **28d Trend** | Last 28d vs prior 28d in pp (needs 56 days). Arrow + color coded |
| **14d Trend** | Last 14d vs prior 14d in pp (needs 28 days) |
| **Best Days** | DOW where completion is >= threshold above habit avg (green pills) |
| **Struggle Days** | DOW where completion is >= threshold below habit avg (red pills) |

#### Tier Classification

Habits are grouped into tiers based on their 28d rate:
- **Solid** — >= 80%
- **Okay** — 50–79%
- **Needs Attention** — < 50%

Within each tier, habits are sorted by 28d trend ascending (most declining first).

#### DOW Threshold

The threshold for "Best Days" and "Struggle Days" is computed dynamically as the 75th percentile of `|day_rate - habit_avg|` across all habit x day combinations with >= 4 occurrences. This adapts to the data rather than using a fixed cutoff.

#### Trend Calculation (`_window_mean`)

A local helper inside the per-habit loop that computes the mean completion rate for a slice of a habit's value series. Trends are computed as simple differences between adjacent windows:
- **14d trend** = last 14 days minus prior 14 days
- **28d trend** = last 28 days minus prior 28 days

### 4. Day of Week

#### Overall DOW Table

A custom HTML table with one row per weekday showing:
- **Rate** — overall completion rate for that day (colored)
- **vs Avg** — delta from the overall daily average in pp
- **Struggling** — habit pills showing which habits are significantly below their average on this day
- **Thriving** — habit pills showing which habits are significantly above their average

#### Per-Habit DOW Heatmap (expandable)

A Plotly heatmap inside an expander with habits on the y-axis, weekdays on the x-axis, and cell values showing completion rates (0–100%). Includes an "All habits daily avg" summary row at the bottom.

### 5. Keystone Habits

Identifies habits whose completion reliably predicts higher completion of all other habits.

#### Method

For each habit with enough done-days and skip-days (configurable, default 5):
1. Compute the mean completion rate of all *other* habits on done-days vs skip-days
2. Run a Welch's t-test; only keep habits with p < 0.05
3. For each significantly impacted other habit, test individually (t-test, p < 0.05) to identify which specific habits are lifted or suppressed

#### Table Columns

| Column | Definition |
|---|---|
| **Habit** | Name + overall completion rate badge |
| **Impact** | Difference in other-habit completion rate: done-days minus skip-days (pp) |
| **Consistency** | % of done-days where other-habit completion was above the overall median. Guards against a high impact score driven by a few outlier days |
| **Breadth** | Count of individually affected habits (X up / Y down / total), with per-habit pills showing the delta |

### 6. Habit Momentum

Tests whether doing a habit yesterday predicts doing it today.

#### Method

For each habit with >= 10 tracked days:
1. Build a yesterday/today pair DataFrame
2. Compute P(today | did yesterday) and P(today | skipped yesterday)
3. Fisher exact test on the 2x2 contingency table; keep p < 0.05
4. For 2-day momentum: P(today | did yesterday AND day before) — requires >= 5 qualifying rows

#### Table Columns

| Column | Definition |
|---|---|
| **Habit** | Name + completion rate badge |
| **Momentum** | P(done | did yesterday) - P(done | skipped yesterday), as a percentage |
| **Recovery** | P(done today | skipped yesterday) — how likely you are to bounce back |
| **2-Day Momentum** | P(done | 2 consecutive done-days) with delta vs 1-day rate. Positive delta = streaks compound |

### 7. Habit Correlations

#### Phi Matrix

Computes the phi coefficient (binary correlation) for every habit pair with >= 20 shared days. The matrix is reordered by hierarchical clustering (average linkage on `1 - phi` distance).

#### Habit Groups

Clusters are cut at distance 0.7 (phi >= 0.3) and validated: a cluster must have >= 3 habits, avg known phi >= 0.3, and >= 50% of pairs with sufficient data. Missing pairs are imputed with the mean of all known off-diagonal phi values before clustering (to avoid bias toward 0).

#### Notable Pairs Tables

Two tables split positive and negative correlations:
- **Habits that tend to happen together** — phi >= 0.3, p < 0.05
- **Habits that rarely happen on the same day** — phi <= -0.3, p < 0.05

Each shows Habit A, Habit B, Both Done %, Phi, and number of shared days.

#### Correlation Matrix (expandable)

Lower-triangle heatmap of phi values, with hierarchically-clustered ordering. Red = negative, gray = zero, green = positive.

### 8. Lead/Lag Correlations (T-1)

Tests whether doing Habit A *yesterday* predicts doing Habit B *today*. Same phi + Fisher exact method as same-day correlations, but with a 1-day shift.

- **Positive lead/lag** — phi >= 0.25, p < 0.05 (lower threshold than same-day since temporal effects are typically weaker)
- **Negative lead/lag** — phi <= -0.25, p < 0.05

### 9. Consistency Heatmap

A full-width heatmap showing every habit x every day in the selected range.

- **Z values:** 1 (done, green), -1 (skipped, red), NaN (not tracked, dark gray background)
- **Y-axis:** habits sorted by overall completion rate (highest first), each labeled with "Habit Name  XX%"
- **Bottom row:** "Daily total" — completion percentage mapped to [-1, 1] range for color continuity
- **X-axis:** date strings with monthly tick marks

---

## Page Sections — Single Habit View

Selected when a specific habit is chosen in the sidebar dropdown.

### Stats Row

| Metric | Definition |
|---|---|
| **Days tracked** | Days this habit was tracked (non-NaN) in range |
| **Completion rate** | % of tracked days completed |
| **Current streak** | Consecutive done-days from end |
| **Best streak** | Longest run ever |
| **Trend** | `trend_label()` output based on linear regression of 7-day smoothed series |

### Charts

Same `daily_chart`, `weekly_chart`, and `monthly_chart` functions as the all-habits view, but applied to this habit's 0/100 series.

### Day of Week

Uses `dow_cards()` — seven inline styled cards (one per weekday) showing the habit's completion rate on that day.

### Momentum

If >= 5 paired days exist: shows P(done | did yesterday), P(done | skipped yesterday), and the momentum score (difference).

### Weekly Rhythm Heatmap

A grid where:
- **X-axis:** one column per calendar week (labeled as month/day of Monday)
- **Y-axis:** Mon–Sun
- **Cells:** green (done), red (skipped), dark (no data)
- **X ticks:** only labeled at month boundaries to avoid crowding

---

## Constants and Thresholds

| Name | Value | Used In |
|---|---|---|
| `MIN_SHARED` | 20 days | Correlation/lead-lag pair filtering |
| `ks_min_days` | 5 (configurable) | Keystone habits minimum done/skipped days |
| Trend >=10pp | Improving | Stats row, per-habit table |
| Trend <=-10pp | Declining | Stats row, per-habit table |
| Phi >= 0.3 | Notable positive pair | Correlations |
| Phi <= -0.3 | Notable negative pair | Correlations |
| Phi >= 0.25 | Notable lead/lag | Lead/Lag section |
| Cluster distance 0.7 | phi >= 0.3 | Habit groups |
| DOW threshold | 75th percentile (dynamic) | Best/Struggle days |

---

## Statistical Methods

| Test | Where Used | Purpose |
|---|---|---|
| **Welch's t-test** (`ttest_ind`) | Keystone habits | Compare other-habit rates on done vs skip days |
| **Fisher exact test** (`fisher_exact`) | Momentum, Correlations, Lead/Lag | Test independence of two binary variables |
| **Phi coefficient** | Correlations, Lead/Lag | Measure association strength between two binary variables |
| **Hierarchical clustering** (`linkage` + `fcluster`) | Habit groups | Group correlated habits |
| **Linear regression** (`polyfit`) | `compute_slope` | Single-habit trend over time |

---

## Dependencies

- **streamlit** — page framework, caching, layout
- **pandas** — data manipulation
- **numpy** — array operations, clustering input
- **plotly** (`graph_objects`) — all charts and heatmaps
- **scipy** — `fisher_exact`, `ttest_ind`, `linkage`, `leaves_list`, `fcluster`, `squareform`
- **sidebar.py** — shared extract/reload buttons
