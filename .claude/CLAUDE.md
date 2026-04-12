# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Privacy Rules

**NEVER write the following into any file in this repo:**
- Real names, usernames, or email addresses
- File paths containing usernames (e.g. `/Users/someone/...`)
- API tokens, secrets, or credentials of any kind
- GitHub repo names or URLs pointing to private repos
- Any vault paths, iCloud paths, or machine-specific paths

All secrets and personal config belong in `.streamlit/secrets.toml` (gitignored) or environment variables set outside the repo.

## What This Is

A personal habit analytics system: a CLI extraction script pulls daily habit data from an Obsidian vault, and a multi-page Streamlit dashboard visualizes it. The extraction script is pure-stdlib Python; the dashboard uses Streamlit, Pandas, Plotly, NumPy, and SciPy.

## Project Structure

```
habit-tracker/
├── .venv/                         # Virtual environment (Python 3.13)
├── app.py                         # Streamlit entry point (page navigation)
├── extract_habits.py              # CLI: Obsidian notes -> JSON
├── requirements.txt
├── core/                          # Bottom of dependency tree (no framework deps)
│   ├── constants.py               # Color constants, rate_color, DOW lookups
│   └── stats.py                   # Pure stat functions: streak, slope, trend_label
├── analytics/                     # Pure business logic (no Streamlit)
│   ├── week_review.py             # Window averages, trends, deltas, habit classification
│   └── historical.py              # Per-habit stats, keystone, momentum, correlations, lead/lag
├── charts/                        # Plotly figure builders (no Streamlit)
│   ├── common.py                  # Shared layout & colorscale constants
│   ├── week_review.py             # Heatmaps, bar charts for weekly review
│   └── historical.py              # Daily/weekly/monthly charts, DOW/correlation/consistency heatmaps
├── ui/                            # Shared Streamlit UI components
│   ├── auth.py                    # Authentication gate + sidebar controls
│   ├── sidebar.py                 # Extract / reload buttons, data source label
│   └── html_tables.py             # HTML table primitives: open/close, trend cells, pills
├── services/                      # Data access layer
│   ├── data_loader.py             # Mode-aware data loading (local / Supabase / demo)
│   └── supabase_sync.py           # Supabase read/write helpers
├── views/                         # Streamlit pages (thin rendering layer)
│   ├── week_review.py             # Page 1: Weekly Review
│   └── historical_review.py       # Page 2: Historical Analysis
├── data/
│   ├── habits.json                # Extracted data (date -> {habit: bool})
│   └── week_review_config.json    # Optional habit order/filter for week review
└── tests/
    ├── test_extract_habits.py
    └── test_helpers.py
```

## Running

### Extraction

```bash
python3 extract_habits.py --start 2026-01-01 --end 2026-03-31
```

- `--output`: JSON output path (default: `data/habits.json`)
- Merges into existing output file, so you can run incrementally
- Set `VAULT_DIR` env var to point at your Obsidian vault (e.g. in `~/.zshrc`)

### Dashboard

```bash
source .venv/bin/activate  # first time: python3 -m venv .venv && pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Key Design Details

### Extraction (`extract_habits.py`)

- Daily notes expected at `<VAULT_DIR>/03-Resources/Calendar/Daily Notes/YYYY-MM-DD.md`
- Parses only the `## Habits` section (assumed to be the last section in each note)
- Habits are Obsidian callout checkboxes: `> - [x] Habit Name` or `> - [ ] Habit Name`
- Habit names are cleaned: bold markers (`**`) stripped, trailing parentheticals removed
- Output JSON is keyed by date string, each value is a dict of habit name -> bool

### Dashboard Architecture

The dashboard follows a three-layer separation of concerns:
- **`analytics/`** — pure business logic (no Streamlit). Functions take DataFrames and return plain data structures. Testable in isolation.
- **`charts/`** — Plotly figure builders (no Streamlit). Functions return `go.Figure` objects.
- **`views/`** — thin Streamlit rendering layer. Wires analytics + charts into `st.*` calls and HTML tables.

Core plumbing:
- `app.py` uses `st.navigation()` / `st.Page()` for multi-page routing
- `core/constants.py` has color constants (`RED`, `YELLOW`, `GREEN`, `MUTED`), `rate_color()`, and DOW lookups (`DAY_ORDER`, `DAY_ABBR`, `DAY_TO_ABBR`)
- `core/stats.py` has pure stat functions (`compute_streak`, `compute_slope`, `trend_label`)
- `charts/common.py` has shared Plotly layout (`DARK_LAYOUT`) and colorscale constants (`STEPPED_COLORSCALE`, `DIVERGING_COLORSCALE`, `GRADIENT_COLORSCALE`)
- `ui/html_tables.py` has HTML table primitives (`TD_STYLE`, `html_table_open`, `html_table_close`, `trend_cell`, `habit_tags`)
- `ui/sidebar.py` is shared between pages (Streamlit puts the app directory on sys.path)
- Both pages load data via `services.data_loader.load_habits()`, which delegates to `current_mode()` (`demo` / `supabase` / `local`). Views and the sidebar must never branch on the backend — call `data_loader` functions instead.
- `services/supabase_sync.py` owns all Supabase I/O (reads/writes rows in the `habit_data` table keyed by filename); credentials come from `st.secrets["SUPABASE_URL"]` / `SUPABASE_KEY`
- The "Extract latest" sidebar button runs `extract_habits.py` to update local `data/habits.json`, then calls `data_loader.persist_habits_after_extract()` which pushes to Supabase when in that mode. The button is hidden when `data_loader.can_run_extraction()` is false (e.g. cloud deploy with `REMOTE_MODE` set, or demo session).

### Page 1: Weekly Review (`week_review.py`)

Focused on recent performance across three fixed windows anchored to the latest data date (not today):
- **Week** (7 days), **Month** (28 days), **Quarter** (84 days)
- Three color-coded Plotly heatmaps (daily columns for week/month, weekly-aggregated columns for quarter)
- Each heatmap has an "All habits" summary row and an "Avg/wk" summary column
- Color scale is stepped: green (>=80%), yellow (50-79%), red (<50%)
- Per-habit trend classification: Struggling / Slipping / Improving / Okay / Solid & Steady / Not enough data
- Trends compare recent 28-day avg to prior 56-day baseline (delta >= 0.5/wk threshold)
- `data/week_review_config.json` optionally controls which habits appear and in what order

### Page 2: Historical Analysis (`historical_review.py`)

Deep statistical analysis over a user-selected date range. Two modes:

**All Habits mode** (default):
- Stats row, daily/weekly/monthly charts with moving averages
- Per-habit breakdown table with tiers (Solid/Okay/Needs Attention), 28d/14d trend arrows, DOW best/struggle days
- Day-of-week analysis with per-habit struggling/thriving pills and a per-habit DOW heatmap
- Keystone habits (Welch's t-test, p<0.05): impact, consistency, breadth
- Momentum (Fisher exact test, p<0.05): self-reinforcing habits, recovery rate, 2-day compounding
- Correlations: phi coefficient matrix, hierarchical clustering into habit groups, notable pairs
- Lead/lag correlations (T-1): yesterday's habit predicting today's
- Consistency heatmap: every habit x every day

**Single Habit mode** (selected via sidebar dropdown):
- Stats, daily/weekly/monthly charts, DOW cards, momentum, weekly rhythm heatmap

### Shared Patterns

- All HTML tables are hand-built (not `st.dataframe`) for styling control — colored text, pills, tier headers. Use `html_table_open()` / `html_table_close()` from `ui/html_tables.py` for the boilerplate and `TD_STYLE` for cell styling
- Color constants live in `core/constants.py`: `RED` (`#f87171`), `YELLOW` (`#fbbf24`), `GREEN` (`#4ade80`), `MUTED` (`#6b7280`). Use these instead of inline hex values
- Statistical significance threshold is p<0.05 throughout
- Dark-mode styling: transparent backgrounds, `#222` gridlines, `#e2e8f0` text
