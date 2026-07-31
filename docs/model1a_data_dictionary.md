# Model 1A Data Dictionary

| Series | Description | Frequency | Role | Source |
|---|---|---:|---|---|
| GDPC1 | Real Gross Domestic Product | Quarterly | Target | FRED/BEA |
| INDPRO | Industrial Production Index | Monthly | Feature | FRED/Federal Reserve |
| PAYEMS | Total Nonfarm Payroll Employment | Monthly | Feature | FRED/BLS |
| RSAFS | Advance Retail Sales | Monthly | Feature | FRED/Census |
| HOUST | Housing Starts | Monthly | Feature | FRED/Census |
| AWHMAN | Average Weekly Hours, Manufacturing | Monthly | Feature | FRED/BLS |
| UNRATE | Unemployment Rate | Monthly | Feature | FRED/BLS |
| CPIAUCSL | Consumer Price Index | Monthly | Feature | FRED/BLS |
| FEDFUNDS | Effective Federal Funds Rate | Monthly | Feature | FRED/Federal Reserve |

## Date fields

- `observation_date`: economic reference period.
- `realtime_start`: first date the stored vintage applies.
- `realtime_end`: final date the stored vintage applies; `9999-12-31` means open-ended.
- `retrieved_at`: time MacroPulse downloaded the row.
- `forecast_date`: information cutoff used in a backtest.
- `actual_release_date`: first stored release date for the target GDP quarter.
