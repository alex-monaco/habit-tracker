"""Pure statistical helper functions — no framework dependencies."""

import numpy as np
import pandas as pd


def compute_streak(bool_series: pd.Series):
    """Return (current_streak, best_streak) from a boolean Series ordered by date."""
    vals = bool_series.tolist()
    current = run = best = 0
    for v in reversed(vals):
        if v:
            current += 1
        else:
            break
    for v in vals:
        if v:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return current, best


def compute_slope(series: pd.Series):
    """Fit a linear trend on a 7-day smoothed series.

    Returns (slope_per_day, r_squared, n, volatile).
    volatile = True when R² is low but variance is high (non-linear swings, not just flat).
    """
    s = series.dropna().astype(float)
    n = len(s)
    if n < 7:
        return 0.0, 0.0, n, False
    smoothed = s.rolling(7, min_periods=1).mean()
    x = np.arange(n, dtype=float)
    coeffs = np.polyfit(x, smoothed.values, 1)
    slope = float(coeffs[0])
    y_hat = np.polyval(coeffs, x)
    ss_res = float(np.sum((smoothed.values - y_hat) ** 2))
    ss_tot = float(np.sum((smoothed.values - smoothed.values.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    volatile = r2 < 0.15 and float(smoothed.std()) > 15.0
    return slope, r2, n, volatile


def trend_label(total_change: float, r2: float = 1.0, volatile: bool = False) -> str:
    """Map total pp change over a period to a human-readable trend label."""
    if volatile:
        return "↕ Volatile"
    if r2 < 0.15:
        return "→ Stable"
    if total_change > 5:
        return "↑ Improving"
    if total_change < -5:
        return "↓ Declining"
    return "→ Stable"
