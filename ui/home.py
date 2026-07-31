import streamlit as st

from macropulse.data.repository import MacroRepository


st.title("MacroPulse")
st.caption("Vintage-aware macroeconomic nowcasting, validation, and release attribution")

repository = MacroRepository()
repository.initialise()

counts = repository.query_df(
    """
    SELECT
        COUNT(DISTINCT series_id) AS series_count,
        COUNT(*) AS observation_rows,
        MAX(retrieved_at) AS last_download
    FROM observations
    """
)

latest_run = repository.query_df(
    """
    SELECT run_timestamp, target_period, model_name, status
    FROM model_runs
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)
latest_news = repository.query_df(
    """
    SELECT status, target_period, total_change, created_at
    FROM nowcast_news_runs
    ORDER BY created_at DESC
    LIMIT 1
    """
)

col1, col2, col3 = st.columns(3)
col1.metric("Loaded series", int(counts.iloc[0]["series_count"] or 0))
col2.metric("Observation rows", f"{int(counts.iloc[0]['observation_rows'] or 0):,}")
last_download = counts.iloc[0]["last_download"]
col3.metric("Last data refresh", "Not run" if last_download is None else str(last_download))

st.subheader("MacroPulse model suite")
st.markdown(
    """
### Model 1A — US GDP Nowcast

**Lifecycle:** Production v1.0.0. The validated Stable Stage Policy remains unchanged.

### Model 1B — US Inflation Nowcast

**Lifecycle:** Development v0.1.0. The foundation covers headline/core CPI and
headline/core PCE with transparent AR, rolling-mean, Ridge bridge, and ensemble
benchmarks. Vintage-aware validation and release-stage governance are intentionally
not yet complete.
"""
)

if latest_run.empty:
    st.info("No model run found. In CMD run: `python scripts\\run_dfm_nowcast.py`")
else:
    row = latest_run.iloc[0]
    st.success(
        f"Latest run: {row['target_period']} | {row['model_name']} | "
        f"{row['status']} | {row['run_timestamp']}"
    )

if latest_news.empty:
    st.info(
        "No news comparison exists yet. Two governed runs for the same target quarter "
        "are required."
    )
else:
    news = latest_news.iloc[0]
    if news["status"] == "success":
        st.info(
            f"Latest attribution for {news['target_period']}: production forecast "
            f"changed by {float(news['total_change']):+.2f} percentage points."
        )
    else:
        st.info(
            "Latest attribution status: " + str(news["status"]).replace("_", " ")
        )
