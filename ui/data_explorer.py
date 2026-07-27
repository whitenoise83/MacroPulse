import streamlit as st

from macropulse.data.repository import MacroRepository


st.title("Data Explorer")

repository = MacroRepository()
repository.initialise()

metadata = repository.query_df(
    '''
    SELECT series_id, title, frequency, units, observation_start, observation_end,
           last_updated
    FROM series_metadata
    ORDER BY series_id
    '''
)

if metadata.empty:
    st.info("No data loaded. Run `python scripts\\download_fred_data.py`.")
    st.stop()

series_id = st.selectbox("Series", metadata["series_id"].tolist())

observations = repository.query_df(
    '''
    SELECT observation_date, value
    FROM observations
    WHERE series_id = ? AND vintage_type = 'latest'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY observation_date
        ORDER BY retrieved_at DESC
    ) = 1
    ORDER BY observation_date
    ''',
    [series_id],
)

series_meta = metadata.loc[metadata["series_id"] == series_id].iloc[0]
st.subheader(series_meta["title"])
st.caption(f"{series_meta['frequency']} | {series_meta['units']}")
st.line_chart(observations.set_index("observation_date")["value"])

st.dataframe(
    observations.sort_values("observation_date", ascending=False).head(50),
    use_container_width=True,
    hide_index=True,
)
