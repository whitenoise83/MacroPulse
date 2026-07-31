# Model 1A Transformation Dictionary

| Series | Transformation | Interpretation |
|---|---|---|
| GDPC1 | `400 × Δlog(level)` | Annualised quarter-on-quarter real GDP growth |
| INDPRO | `100 × Δlog(level)` | Monthly percentage growth |
| PAYEMS | `100 × Δlog(level)` | Monthly percentage growth |
| RSAFS | `100 × Δlog(level)` | Monthly nominal retail-sales growth |
| HOUST | `100 × Δlog(level)` | Monthly housing-starts growth |
| AWHMAN | `100 × Δlog(level)` | Monthly growth in manufacturing hours |
| UNRATE | First difference | Monthly percentage-point change |
| CPIAUCSL | `100 × Δlog(level)` | Monthly CPI inflation |
| FEDFUNDS | First difference | Monthly percentage-point policy-rate change |

Monthly transformed indicators are aggregated to quarterly features for the
Bridge model. The DFM retains native monthly indicators and quarterly GDP in a
mixed-frequency state-space system.
