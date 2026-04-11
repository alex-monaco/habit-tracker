# Week Review Page — Technical Documentation

This document is a detailed reference for `dashboard/pages/week_review.py`, a Streamlit page that provides a weekly habit review dashboard.

## Purpose

The page answers one question: **how consistently am I completing my habits?** It shows completion data across three time horizons (7 days, 28 days, 84 days) using color-coded heatmaps, summary statistics, and per-habit trend classifications.

---

## Data Pipeline

### Source

- **`data/habits.json`** — JSON file keyed by date (`"YYYY-MM-DD"`), where each value is a dict of `{ "Habit Name": true/false }`. Produced by `extract_habits.py` from Obsidian daily notes.
- **`data/week_review_config.json`** — Optional config file containing a `"habits"` array that controls which habits appear and in what order. Habits not in this list are excluded; habits in the list but missing from the data are silently skipped.

### Loading

`load_data()` is decorated with `@st.cache_data` so it only reads and parses the JSON once per Streamlit session (until the cache is explicitly cleared by the sidebar reload/extract buttons).

The resulting DataFrame has:
- **Index:** `DatetimeIndex` (one row per day)
- **Columns:** one per habit (boolean values, cast to float for arithmetic)

### Sidebar Controls

The shared `sidebar.py` module (imported via `sys.path` manipulation since Streamlit pages can't do normal relative imports) provides two buttons:
- **Extract latest** — runs `extract_habits.py` to pull any new days since the last data point, then clears the cache and reruns.
- **Reload data** — clears the Streamlit data cache and reruns.

---

## Page Sections (Top to Bottom)

### 1. Stats Row

Three summary metrics displayed at week / month / quarter scale:

| Metric | Definition |
|---|---|
| **Completion rate** | `mean(daily_rate)` where `daily_rate = completed_habits / total_habits` for each day in the window. Shown as a percentage. |
| **Days above 80%** | The window is chunked into 7-day blocks. For each block, count the days where `daily_rate >= 80%`. Average those counts across blocks. Shown as `X.X/7`. |

The "Latest data" metric shows the most recent date in the dataset.

### 2. Heatmaps

Three heatmaps, each built by one of two rendering functions:

| Section | Window | Renderer | X-axis columns |
|---|---|---|---|
| **Week** | Last 7 days | `render_heatmap()` | One column per day (e.g. `Mon 4/7`) |
| **Month** | Last 28 days | `render_heatmap()` | One column per day |
| **Quarter** | Last 84 days | `render_weekly_heatmap()` | One column per 7-day chunk (e.g. `1/15–1/21`) |

#### Heatmap Structure

Both renderers produce a Plotly `go.Heatmap` with the following layout:

- **Y-axis (rows):** `"All habits"` on top, then one row per individual habit. A horizontal line separates the aggregate row from individual habits. Y-axis tick labels are hidden and replaced with left-aligned annotations positioned in the margin, giving a clean label layout.
- **X-axis (columns):** An `"Avg/wk"` summary column on the far left, followed by the time columns (days or weeks).
- **Cell values (z):**
  - For individual habit rows: `1.0` (done) or `0.0` (not done) for daily heatmaps; the mean completion rate across the chunk for the weekly heatmap.
  - For the `"All habits"` row: the mean completion rate across all habits for that day/week.
  - For the `"Avg/wk"` column: individual habits get their mean completion rate; `"All habits"` gets the average fraction of days above 80% per 7-day chunk (same metric as the stats row).

#### Color Scale

The heatmap uses a three-tier stepped color scale (no gradients within tiers):

| Range | Color | Hex |
|---|---|---|
| 0.0 – 0.499 | Red | `#f87171` |
| 0.5 – 0.799 | Yellow | `#fbbf24` |
| 0.8 – 1.0 | Green | `#4ade80` |

#### Text Overlays

- The `"Avg/wk"` column always shows the value as `X.X` (days per week, i.e. the rate multiplied by 7).
- Daily columns on the `"All habits"` row show the completion percentage (e.g. `75%`) when `show_text=True`.
- All other cells show no text but have hover data with the percentage.

#### Sizing

Figure width is calculated dynamically: `LABEL_MARGIN (200px) + TOTAL_PX (70px) + n_columns * COL_PX (38px for daily, 56px for weekly)`. Height scales with the number of habits: `max(300, 36px * n_rows + 60px)`.

### 3. Habit Averages Table

A styled table with one row per habit and three columns:

| Column | Window |
|---|---|
| **7-day** | Last 7 days |
| **28-day** | Last 28 days |
| **prior 56-day** | Days 29–84 (the 56 days before the most recent 28) |

Each cell shows the average completions per week (i.e. `mean(daily_bool) * 7`), colored by the same thresholds used in the trend section:

| Color | Threshold |
|---|---|
| Green | >= 6.0/wk |
| Yellow | >= 4.0/wk |
| Red | < 4.0/wk |

### 4. Per-Habit Trends

Each habit is classified into exactly one of six categories based on its 28-day and prior-56-day averages:

#### Classification Logic

```
For each habit:
  1. If any window has no data → "Not enough data"
  2. If 28-day AND prior-56-day are both green (>= 6/wk) → "Solid & Steady"
  3. If 28-day AND prior-56-day are both red (< 4/wk) → "Struggling"
  4. Otherwise, compute delta = recent_28day_avg - prior_56day_avg:
     - delta <= -0.5  → "Slipping"
     - delta >= +0.5  → "Improving"
     - |delta| < 0.5  → "Okay"
```

Steps 2 and 3 short-circuit: if a habit is consistently green or consistently red across both windows, trend analysis is skipped because the direction doesn't add useful information.

#### Display

Each non-empty category is rendered as a labeled section with its own styled table (same format as the averages table). Tables are sorted by 7-day average ascending (worst first). The "Not enough data" category is collapsed inside an expander.

An explanatory expander at the bottom documents the classification rules and color thresholds.

---

## Key Functions

| Function | Purpose |
|---|---|
| `load_data()` | Cached loader: JSON to DatetimeIndex DataFrame |
| `window_avg(days)` | Overall completion rate as a formatted percentage |
| `days_above_80(days)` | Avg days per 7-day chunk above 80%, formatted as `X.X/7` |
| `render_heatmap(window, show_text)` | Daily-granularity Plotly heatmap with Avg/wk summary |
| `render_weekly_heatmap(window)` | Weekly-aggregated Plotly heatmap with Avg/wk summary |
| `_avg_wk_range(habit, start, end)` | Raw avg completions/week for a habit over a date range (returns float or None) |
| `_fmt_avg(v)` | Format a float as `"X.X"` or `"—"` if None |
| `habit_avg_wk(habit, days)` | `_fmt_avg(_avg_wk_range(...))` for "last N days" convenience |
| `_color_avg(val)` | Pandas Styler callback: returns CSS `color:` rule based on avg/wk thresholds |
| `_tier(val_str)` | Maps an avg/wk string to tier int (2=green, 1=yellow, 0=red, None=unparseable) |
| `_trend_table(entries)` | Builds a styled DataFrame from a list of trend tuples, sorted by 7-day ascending |

---

## Constants

| Name | Value | Purpose |
|---|---|---|
| `RED` | `#f87171` | Tailwind red-400 |
| `YELLOW` | `#fbbf24` | Tailwind amber-400 |
| `GREEN` | `#4ade80` | Tailwind green-400 |
| `LABEL_MARGIN` | `200` px | Left margin for habit name annotations |
| `COL_PX` | `38` px | Width per daily column |
| `TOTAL_PX` | `70` px | Width for the Avg/wk column |
| `SUMMARY_COL` | `"Avg/wk"` | Label for the summary column |
| `COLORSCALE` | 3-tier stepped scale | Maps z values [0,1] to red/yellow/green |

---

## Time Windows

All windows are anchored to `last_date` (the most recent date in the dataset, not today):

| Name | Start | End | Days |
|---|---|---|---|
| Week | `last_date - 6` | `last_date` | 7 |
| Month | `last_date - 27` | `last_date` | 28 |
| Quarter | `last_date - 83` | `last_date` | 84 |
| Recent (for trends) | `last_date - 27` | `last_date` | 28 |
| Prior (for trends) | `last_date - 83` | `last_date - 28` | 56 |

The "prior" window is intentionally longer (56 days vs 28) to give a more stable baseline for trend comparison.

---

## Dependencies

- **streamlit** — page framework, caching, layout
- **pandas** — data manipulation, styled tables
- **plotly** (`graph_objects`) — heatmap figures
- **sidebar.py** — shared extract/reload buttons (imported via `sys.path` hack)
