import streamlit as st

from macropulse.data.repository import MacroRepository


st.title("MacroPulse")
st.caption("Vintage-aware macroeconomic nowcasting and scenario infrastructure")

repository = MacroRepository()
repository.initialise()

counts = repository.query_df(
    '''
    SELECT
        COUNT(DISTINCT series_id) AS series_count,
        COUNT(*) AS observation_rows,
        MAX(retrieved_at) AS last_download
    FROM observations
    '''
)

latest_run = repository.query_df(
    '''
    SELECT run_timestamp, target_period, status
    FROM model_runs
    ORDER BY run_timestamp DESC
    LIMIT 1
    '''
)

col1, col2, col3 = st.columns(3)
col1.metric("Loaded series", int(counts.iloc[0]["series_count"] or 0))
col2.metric("Observation rows", f"{int(counts.iloc[0]['observation_rows'] or 0):,}")
last_download = counts.iloc[0]["last_download"]
col3.metric("Last data refresh", "Not run" if last_download is None else str(last_download))

st.subheader("Phase 1 workflow")
st.markdown(
    '''
1. Download current and initial-release FRED observations.
2. Store observation dates, real-time validity dates and retrieval timestamps.
3. Transform monthly indicators into quarterly bridge variables.
4. Estimate a Ridge bridge model and an AR(1) benchmark.
5. Combine them into an equal-weight real-GDP growth nowcast.
'''
)

if latest_run.empty:
    st.info(
        "No model run found. In CMD run: "
        "`python scripts\\run_baseline_nowcast.py`"
    )
else:
    row = latest_run.iloc[0]
    st.success(
        f"Latest run: {row['target_period']} | "
        f"{row['status']} | {row['run_timestamp']}"
    )

st.warning(
    "Phase 1 is a baseline system. It is not yet the full Dynamic Factor Model, "
    "release-news decomposition or pseudo-real-time backtest engine."
)
