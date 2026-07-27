from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb
import pandas as pd

from macropulse.settings import settings


SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS series_metadata (
    series_id VARCHAR PRIMARY KEY,
    title VARCHAR,
    frequency VARCHAR,
    units VARCHAR,
    seasonal_adjustment VARCHAR,
    observation_start DATE,
    observation_end DATE,
    last_updated VARCHAR,
    source VARCHAR,
    loaded_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS observations (
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    realtime_start DATE,
    realtime_end DATE,
    value DOUBLE,
    vintage_type VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_series_date
ON observations(series_id, observation_date);

CREATE TABLE IF NOT EXISTS model_runs (
    run_id VARCHAR PRIMARY KEY,
    model_name VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    data_as_of DATE,
    target_period VARCHAR,
    status VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS forecasts (
    run_id VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    point_forecast DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS model_coefficients (
    run_id VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    feature VARCHAR NOT NULL,
    coefficient DOUBLE
);
'''


class MacroRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or settings.database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self, read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
        connection = duckdb.connect(str(self.database_path), read_only=read_only)
        try:
            yield connection
        finally:
            connection.close()

    def initialise(self) -> None:
        with self.connect() as connection:
            connection.execute(SCHEMA_SQL)

    def upsert_metadata(self, metadata: dict) -> None:
        frame = pd.DataFrame(
            [
                {
                    "series_id": metadata.get("id"),
                    "title": metadata.get("title"),
                    "frequency": metadata.get("frequency"),
                    "units": metadata.get("units"),
                    "seasonal_adjustment": metadata.get("seasonal_adjustment"),
                    "observation_start": metadata.get("observation_start"),
                    "observation_end": metadata.get("observation_end"),
                    "last_updated": metadata.get("last_updated"),
                    "source": "FRED",
                    "loaded_at": pd.Timestamp.utcnow().tz_localize(None),
                }
            ]
        )
        with self.connect() as connection:
            connection.register("_metadata", frame)
            connection.execute(
                "DELETE FROM series_metadata WHERE series_id IN "
                "(SELECT series_id FROM _metadata)"
            )
            connection.execute("INSERT INTO series_metadata SELECT * FROM _metadata")
            connection.unregister("_metadata")

    def upsert_observations(self, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0

        with self.connect() as connection:
            connection.register("_incoming", frame)
            connection.execute(
                '''
                DELETE FROM observations AS existing
                WHERE EXISTS (
                    SELECT 1
                    FROM _incoming AS incoming
                    WHERE existing.series_id = incoming.series_id
                      AND existing.observation_date = incoming.observation_date
                      AND COALESCE(existing.realtime_start, DATE '1900-01-01')
                          = COALESCE(incoming.realtime_start, DATE '1900-01-01')
                      AND existing.vintage_type = incoming.vintage_type
                )
                '''
            )
            connection.execute(
                '''
                INSERT INTO observations
                SELECT
                    series_id,
                    observation_date,
                    realtime_start,
                    realtime_end,
                    value,
                    vintage_type,
                    retrieved_at,
                    source
                FROM _incoming
                '''
            )
            connection.unregister("_incoming")
        return len(frame)

    def latest_observations(self, series_ids: list[str] | None = None) -> pd.DataFrame:
        where_clause = "WHERE vintage_type = 'latest'"
        parameters: list = []

        if series_ids:
            placeholders = ", ".join(["?"] * len(series_ids))
            where_clause += f" AND series_id IN ({placeholders})"
            parameters.extend(series_ids)

        query = f'''
        SELECT
            series_id,
            observation_date,
            value,
            realtime_start,
            realtime_end,
            retrieved_at
        FROM observations
        {where_clause}
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY series_id, observation_date
            ORDER BY retrieved_at DESC
        ) = 1
        ORDER BY series_id, observation_date
        '''

        with self.connect(read_only=True) as connection:
            return connection.execute(query, parameters).fetchdf()

    def query_df(self, query: str, parameters: list | None = None) -> pd.DataFrame:
        with self.connect(read_only=True) as connection:
            return connection.execute(query, parameters or []).fetchdf()

    def save_model_outputs(
        self,
        run_record: pd.DataFrame,
        forecasts: pd.DataFrame,
        coefficients: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            for table, frame in [
                ("model_runs", run_record),
                ("forecasts", forecasts),
                ("model_coefficients", coefficients),
            ]:
                connection.register(f"_{table}", frame)
                connection.execute(f"INSERT INTO {table} SELECT * FROM _{table}")
                connection.unregister(f"_{table}")
