import numpy as np
import pandas as pd

from macropulse.processing.transforms import transform_series


def test_annualised_monthly_log_transform():
    index = pd.period_range("2020-01", periods=3, freq="M")
    values = pd.Series([100.0, 101.0, 102.01], index=index)
    result = transform_series(values, "annualised_mom_log")
    expected = np.log(1.01) * 1200.0
    assert np.isclose(result.iloc[1], expected)
    assert np.isclose(result.iloc[2], expected)
