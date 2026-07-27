from __future__ import annotations

import numpy as np
import pandas as pd


def transform_series(values: pd.Series, method: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)

    if method == "level":
        transformed = numeric
    elif method == "diff":
        transformed = numeric.diff()
    elif method == "mom_pct":
        transformed = numeric.pct_change(fill_method=None) * 100.0
    elif method == "mom_log_pct":
        transformed = np.log(numeric.where(numeric > 0)).diff() * 100.0
    elif method == "yoy_pct":
        transformed = numeric.pct_change(12, fill_method=None) * 100.0
    elif method == "yoy_log_pct":
        logged = np.log(numeric.where(numeric > 0))
        transformed = logged.diff(12) * 100.0
    elif method == "annualised_qoq_log":
        transformed = np.log(numeric.where(numeric > 0)).diff() * 400.0
    else:
        raise ValueError(f"Unsupported transformation: {method}")

    transformed.name = values.name
    return transformed.replace([np.inf, -np.inf], np.nan)
