# Habit Tracker

![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![Streamlit](https://img.shields.io/badge/streamlit-app-FF4B4B)
![Lint: ruff](https://img.shields.io/badge/lint-ruff-D7FF64)
![Tests: pytest](https://img.shields.io/badge/tests-pytest-0A9EDC)
![CodeQL](https://img.shields.io/badge/security-CodeQL-2088FF)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**Live demo:** https://habit-analytics.streamlit.app/

A personal analytics system that extracts daily habit completion data from an Obsidian vault and surfaces it through a multi-page Streamlit dashboard. The goal is to turn a simple daily checklist into actionable insight — which habits are slipping, which ones anchor the rest of your routine, and whether this week was better than last month.

## Features

- **Two-page dashboard** — a Sunday-morning Weekly Review and a deep Historical Analysis page
- **Statistical rigor** — keystone-habit detection (Welch's t-test), momentum (Fisher exact), phi-coefficient correlations with hierarchical clustering, and lead/lag pairings, all gated at p<0.05
- **Pluggable data backends** — runs from a local JSON file, a Supabase table, or a built-in demo dataset
- **Zero-dependency extractor** — pure-stdlib Python CLI that parses Obsidian daily notes incrementally
- **CI-backed** — ruff, pytest with coverage, CodeQL, and Dependabot wired up out of the box

## How It Works

```
Obsidian daily notes  ──>  extract_habits.py  ──>  data/habits.json  ──>  Streamlit dashboard
```

1. Each day's Obsidian note has a `## Habits` section with callout-style checkboxes (`> - [x] Habit Name`).
2. `extract_habits.py` scans the vault for a date range, parses those checkboxes, and writes a JSON file mapping each date to a dict of habit names and booleans.
3. The dashboard reads that JSON and renders two pages of analysis.

## Project Structure

```
habit-tracker/
├── app.py                         # Streamlit entry point (page navigation)
├── auth.py                        # Optional password gate for hosted deployments
├── helpers.py                     # Shared constants, analysis funcs, HTML table utilities
├── sidebar.py                     # Shared sidebar controls (extract + reload)
├── data_loader.py                 # Backend router: demo / local / supabase
├── supabase_sync.py               # Supabase read/write for the habit_data table
├── extract_habits.py              # CLI script: Obsidian notes -> JSON
├── pyproject.toml                 # ruff + pytest + coverage config
├── requirements.txt
├── data/
│   ├── habits.json                # Extracted habit data (date -> {habit: bool})
│   └── week_review_config.json    # Optional: habit order/filter for week review
├── views/
│   ├── week_review.py             # Weekly Review page
│   └── historical_review.py       # Historical Analysis page
├── tests/                         # pytest suite
└── .github/workflows/             # CI + CodeQL
```

## Extracting Data

`extract_habits.py` is a pure-stdlib Python script (no dependencies beyond the standard library).

```bash
python3 extract_habits.py --start 2025-10-01 --end 2026-04-06
```

- `--output` — path to write JSON (default: `data/habits.json`)
- Re-running merges into the existing file, so you can extract incrementally
- Set the `VAULT_DIR` environment variable to your Obsidian vault path (e.g. add `export VAULT_DIR="/path/to/your/vault"` to `~/.zshrc`)

Daily notes are expected at `<VAULT_DIR>/03-Resources/Calendar/Daily Notes/YYYY-MM-DD.md`. The script parses only the `## Habits` section (assumed to be the last section), strips bold markers and trailing parentheticals from habit names, and writes the result as `{ "YYYY-MM-DD": { "Habit Name": true/false } }`.

## Dashboard

**First time setup** — create a virtual environment using Python 3.13:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Run the app:**

```bash
source .venv/bin/activate  # if not already active
python3 -m streamlit run app.py
```

The dashboard has two pages, selectable from the left nav.

### Page 1: Weekly Review

A focused, at-a-glance view of recent habit performance across three time horizons. Designed for a quick Sunday check-in.

**Stats row** — overall completion rate and days-above-80% metric at the week, month, and quarter scale.

**Heatmaps** — three color-coded grids (7-day, 28-day, and 84-day) where each row is a habit and each column is a day (or a week, for the quarter view). An "All habits" summary row sits at the top. Every heatmap includes an "Avg/wk" summary column showing average completions per week. Colors are stepped: green (>=80%), yellow (50–79%), red (<50%).

**Habit averages table** — per-habit avg completions/week across three windows: 7-day, 28-day, and prior 56-day. Cell text is colored by the same green/yellow/red thresholds.

**Per-habit trends** — each habit is classified into one of six categories based on how its recent 28-day average compares to the prior 56-day baseline:
- **Struggling** — both windows red
- **Slipping** — recent avg dropped >= 0.5/wk
- **Improving** — recent avg rose >= 0.5/wk
- **Okay** — change within 0.5/wk
- **Solid & Steady** — both windows green
- **Not enough data** — habit is too new

An optional config file (`data/week_review_config.json`) controls which habits appear and in what order.

### Page 2: Historical Analysis

A deep statistical analysis over any date range. Has two modes depending on the sidebar dropdown.

#### All Habits mode

- **Stats** — days tracked, average completion rate, current/best streak (>=80% day), 28-day and 14-day trend deltas
- **Charts** — daily bar + 7-day/28-day moving averages, weekly bars + 4-week MA, monthly bars + 3-month MA
- **Per-habit breakdown** — HTML table with 28d rate, streak status, 28d/14d trend arrows, best days and struggle days (DOW pills). Habits are grouped into tiers (Solid/Okay/Needs Attention) and sorted by trend within each tier
- **Day of week** — per-weekday completion rates with vs-avg deltas, plus per-habit struggling/thriving pills. Expandable per-habit DOW heatmap
- **Keystone habits** — habits whose completion predicts significantly higher other-habit completion (Welch's t-test, p<0.05). Shows impact, consistency (% of done-days above median), and breadth (which specific habits are lifted or suppressed)
- **Momentum** — tests whether doing a habit yesterday predicts doing it today (Fisher exact test). Shows momentum score, recovery rate, and 2-day compounding effect
- **Correlations** — phi coefficient matrix of all habit pairs, hierarchically clustered. Validated habit groups (>=3 habits, avg phi>=0.3). Notable positive and negative pairs tables
- **Lead/lag correlations** — does yesterday's Habit A predict today's Habit B? (phi on T-1 shifted pairs)
- **Consistency heatmap** — every habit x every day, green/red/gray, with monthly tick marks

#### Single Habit mode

Select a habit from the sidebar dropdown to see a focused view:

- Stats (days tracked, rate, streaks, trend via linear regression on 7-day smoothed series)
- Daily/weekly/monthly charts
- Day-of-week cards
- Momentum (P(done|did yesterday) vs P(done|skipped yesterday))
- Weekly rhythm heatmap (Mon–Sun rows x week columns)

### Sidebar Controls

Both pages share sidebar buttons from `sidebar.py`:
- **Extract latest** — runs `extract_habits.py` for any new days since the last data point, then reloads
- **Reload data** — clears the Streamlit cache and reruns

The historical review page also has:
- **Date range presets** — 30d / 90d / 180d / YTD / All
- **Date pickers** — custom From/To range
- **Habit focus dropdown** — switch between All Habits and Single Habit mode

## Data Format

`data/habits.json` is keyed by date, each value a map of habit names to booleans:

```json
{
  "2026-03-29": {
    "Morning Walk": true,
    "Exercise": true,
    "Meditate": false
  }
}
```

`data/week_review_config.json` (optional) controls habit ordering on the weekly review page:

```json
{
  "habits": ["Morning Walk", "Exercise", "Meditate"]
}
```

## Data Backends

`data_loader.py` routes all reads and writes through a single `current_mode()` switch, so pages and the sidebar never branch on the backend. Three modes are supported:

- **`demo`** — a bundled sample dataset. Useful for hosted deployments and for trying the dashboard without any setup.
- **`local`** (default) — reads and writes `data/habits.json`. This is what you get on a fresh clone.
- **`supabase`** — reads and writes rows in a `habit_data` table keyed by filename. Credentials come from `st.secrets["SUPABASE_URL"]` and `st.secrets["SUPABASE_KEY"]` in `.streamlit/secrets.toml`.

The "Extract latest" sidebar button is automatically hidden in modes where local extraction isn't meaningful (e.g. a cloud deploy with `REMOTE_MODE` set, or an active demo session).

## Development

```bash
# install dev deps (ruff, pytest, pytest-cov are pinned in requirements.txt)
pip install -r requirements.txt

# lint + format
ruff check .
ruff format .

# run the test suite with coverage
pytest
```

CI runs the same `ruff check` and `pytest` on every push and PR. CodeQL scans on a weekly schedule, and Dependabot keeps GitHub Actions versions up to date.

## Dependencies

The extraction script uses only the Python standard library. The dashboard requires:

- **streamlit** — app framework
- **pandas** — data manipulation
- **plotly** — charts and heatmaps
- **numpy** — array operations
- **scipy** — statistical tests (Fisher exact, Welch's t-test) and hierarchical clustering

## License

Released under the [MIT License](LICENSE). This is a personal project — issues are welcome, but PRs are not actively reviewed.