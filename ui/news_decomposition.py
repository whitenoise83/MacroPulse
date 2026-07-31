import json

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from macropulse.config import get_series_definitions
from macropulse.data.repository import MacroRepository


st.title("News Decomposition")
st.caption(
    "Explains changes in the Bridge–DFM production forecast between consecutive "
    "runs for the same GDP quarter."
)

repository = MacroRepository()
repository.initialise()

latest = repository.query_df(
    """
    SELECT *
    FROM nowcast_news_runs
    ORDER BY created_at DESC
    LIMIT 1
    """
)

if latest.empty:
    st.info(
        "No comparison snapshot is available yet. Run the model suite once to "
        "store an information set, then run it again after refreshing FRED data."
    )
else:
    news_run = latest.iloc[0]
    status = str(news_run["status"])
    if status != "success":
        st.warning(
            "The latest comparison is not yet decomposable: "
            + status.replace("_", " ")
            + ". A second governed run for the same target quarter may be required."
        )
        details = json.loads(news_run["details_json"] or "{}")
        with st.expander("Comparison details"):
            st.json(details)
    else:
        delta = float(news_run["total_change"])
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Target quarter", news_run["target_period"])
        col2.metric("Previous forecast", f"{news_run['previous_forecast']:.2f}%")
        col3.metric(
            "Current forecast",
            f"{news_run['current_forecast']:.2f}%",
            delta=f"{delta:+.2f} pp",
        )
        col4.metric("Residual interaction", f"{news_run['residual_interaction']:.6f} pp")

        contributions = repository.query_df(
            """
            SELECT *
            FROM nowcast_news_contributions
            WHERE decomposition_id = ?
            ORDER BY ABS(impact) DESC
            """,
            [news_run["decomposition_id"]],
        )
        definitions = {item.series_id: item.name for item in get_series_definitions()}

        if not contributions.empty:
            labels = {
                "bridge_refit": "Bridge model refit",
                "dfm_refit": "DFM parameter refit",
                "dfm_revision_grouped": "Older revisions (grouped)",
                "weight_change": "Ensemble weight change",
                "residual": "Residual interaction",
            }
            series_rows = contributions.loc[contributions["series_id"].notna()].copy()
            series_rows["driver"] = series_rows["series_id"].map(definitions).fillna(
                series_rows["series_id"]
            )
            series_summary = (
                series_rows.groupby("driver", as_index=False)["impact"].sum()
                if not series_rows.empty
                else pd.DataFrame(columns=["driver", "impact"])
            )
            aggregate_rows = contributions.loc[contributions["series_id"].isna()].copy()
            aggregate_rows["driver"] = aggregate_rows["contribution_type"].map(labels).fillna(
                aggregate_rows["contribution_type"]
            )
            aggregate_summary = aggregate_rows[["driver", "impact"]]
            chart_data = pd.concat([series_summary, aggregate_summary], ignore_index=True)
            chart_data = chart_data.loc[chart_data["impact"].abs() > 1e-8]
            chart_data = chart_data.sort_values("impact")

            st.subheader("Contribution waterfall")
            if chart_data.empty:
                st.info("No material changes were detected between the two runs.")
            else:
                starts = []
                running = float(news_run["previous_forecast"])
                for impact in chart_data["impact"]:
                    starts.append(running)
                    running += float(impact)
                fig, ax = plt.subplots(figsize=(10, max(4, 0.42 * len(chart_data))))
                ax.barh(chart_data["driver"], chart_data["impact"], left=starts)
                ax.axvline(float(news_run["previous_forecast"]), linewidth=1)
                ax.axvline(float(news_run["current_forecast"]), linewidth=1, linestyle="--")
                ax.set_xlabel("Annualised GDP growth nowcast (%)")
                ax.set_ylabel("")
                ax.set_title("Additive change from previous to current production forecast")
                st.pyplot(fig, clear_figure=True)

            st.subheader("Largest release and model drivers")
            display = chart_data.assign(
                **{"Impact (pp)": chart_data["impact"].map(lambda value: f"{value:+.3f}")}
            )[["driver", "Impact (pp)"]].rename(columns={"driver": "Driver"})
            st.dataframe(display.iloc[::-1], use_container_width=True, hide_index=True)

            with st.expander("Detailed model contributions"):
                detail = contributions.copy()
                detail["series_id"] = detail["series_id"].map(definitions).fillna(
                    detail["series_id"]
                )
                st.dataframe(
                    detail.rename(
                        columns={
                            "contribution_type": "Contribution type",
                            "model_name": "Model",
                            "series_id": "Series",
                            "observation_date": "Observation date",
                            "previous_value": "Previous model value",
                            "current_value": "Current model value",
                            "news": "News",
                            "weight": "Effective weight",
                            "impact": "Impact (pp)",
                        }
                    ).drop(columns=["decomposition_id", "created_at"]),
                    use_container_width=True,
                    hide_index=True,
                )

        changes = repository.query_df(
            """
            SELECT series_id, observation_date, change_type, previous_value,
                   current_value, value_change
            FROM nowcast_release_changes
            WHERE decomposition_id = ?
            ORDER BY observation_date DESC, series_id
            """,
            [news_run["decomposition_id"]],
        )
        st.subheader("Raw information-set changes")
        if changes.empty:
            st.info("No new or revised raw observations were detected.")
        else:
            changes["series_id"] = changes["series_id"].map(definitions).fillna(
                changes["series_id"]
            )
            st.dataframe(
                changes.rename(
                    columns={
                        "series_id": "Series",
                        "observation_date": "Observation date",
                        "change_type": "Change type",
                        "previous_value": "Previous raw value",
                        "current_value": "Current raw value",
                        "value_change": "Raw change",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

st.divider()
st.subheader("Release tracking")
calendar = repository.query_df(
    """
    WITH latest_observation AS (
        SELECT series_id, observation_date, value
        FROM observations
        WHERE vintage_type = 'latest'
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY series_id
            ORDER BY observation_date DESC, retrieved_at DESC
        ) = 1
    ),
    next_release AS (
        SELECT series_id, MIN(release_date) AS next_release_date
        FROM release_calendar
        WHERE release_date >= CURRENT_DATE
        GROUP BY series_id
    ),
    previous_release AS (
        SELECT series_id, MAX(release_date) AS previous_release_date
        FROM release_calendar
        WHERE release_date < CURRENT_DATE
        GROUP BY series_id
    )
    SELECT metadata.series_id, metadata.title, calendar_name.release_name,
           latest_observation.observation_date AS latest_observation,
           latest_observation.value AS latest_value,
           previous_release.previous_release_date,
           next_release.next_release_date
    FROM series_metadata AS metadata
    LEFT JOIN latest_observation USING (series_id)
    LEFT JOIN next_release USING (series_id)
    LEFT JOIN previous_release USING (series_id)
    LEFT JOIN (
        SELECT series_id, MAX(release_name) AS release_name
        FROM release_calendar
        GROUP BY series_id
    ) AS calendar_name USING (series_id)
    ORDER BY next_release.next_release_date NULLS LAST, metadata.series_id
    """
)
if calendar.empty or calendar["release_name"].isna().all():
    st.info(
        "Run `python scripts\\refresh_release_calendar.py` to load recent and "
        "upcoming FRED release dates."
    )
else:
    st.dataframe(
        calendar.rename(
            columns={
                "series_id": "Series",
                "title": "Indicator",
                "release_name": "Release",
                "latest_observation": "Latest observation",
                "latest_value": "Latest value",
                "previous_release_date": "Previous release",
                "next_release_date": "Next scheduled release",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    "DFM news and revision impacts use the previous run's fixed model parameters. "
    "Separate refit and ensemble-weight effects reconcile the attribution to the "
    "actual production forecast change. FRED release dates may precede data "
    "availability on FRED."
)
