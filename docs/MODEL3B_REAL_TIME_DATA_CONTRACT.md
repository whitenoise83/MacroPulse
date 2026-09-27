# Model 3B Real-Time Data & Vintage Contract

## Scope

Model 3B defines the governed real-time data and vintage architecture for Model 3 — Potential Output & Macroeconomic Slack.

It descends from Model 3A commit `6f45208103a5ac1a900317a33c0038d56920ffbb` and ultimately from immutable Model 2 release `model2-bvar-v1.0.2` at `cda24988e772cd2b96be612b7d455c54a06f44fa`.

Passing 3B authorizes only **3C — Univariate Trend / Filter Benchmarks**. It does not authorize production estimation, database writes, model promotion, or release tagging.

## Required core series

- `GDPC1` — real GDP level.
- `UNRATE` — unemployment rate.
- `PCEPILFE` — core PCE price index.

`FEDFUNDS` is not a required Model 3B core series. Monetary-policy integration is not part of this workstream.

## Quarterly panel

The governed panel exposes:

- `real_gdp_level`
- `real_gdp_log`
- `unemployment_rate`
- `core_pce_level`
- `core_pce_inflation`

GDP remains available in level/log-level form because later Model 3 work decomposes log real output into potential output and an output gap.

Core PCE inflation is annualised quarter-on-quarter log growth. UNRATE uses the observed quarter-end month. Core PCE uses the observed quarter-end month.

## Exact-vintage rule

For historical cutoff `d`, Model 3B may use only observations demonstrated to have been available by `d`.

The condition `observation_date <= d` is necessary but not sufficient to establish historical availability. A currently revised series truncated at `d` must not be represented as an exact historical information set.

The snapshot supplied to the transformation layer is therefore an exact-vintage snapshot or a snapshot backed by separately governed availability evidence.

## Information-set identity

Each information set is identified deterministically from:

1. `as_of_date`;
2. the canonical hash of the required-series snapshot.

The inventory records the first and last jointly complete quarters, joint-quarter count, snapshot hash, left-censoring state and pseudo-real-time admissibility.

The first observed information-set state is left-censored because the repository cannot prove that it observed the preceding state. It is inventory but not admissible pseudo-real-time evidence.

## Publication lags and no look-ahead

Series need not share an artificial release date. At a cutoff, only actually available observations enter the snapshot.

No observation dated after the cutoff may enter the transformation layer. Publication lags must not be repaired by fabrication, interpolation, backfilling from future releases, or silent substitution of revised history.

## Model boundaries

Model 1 integration is deferred to 3F.

Model 2 forecast distributions are prohibited from determining the historical/current Model 3 information set in 3B. Forward-gap integration is deferred to 3G.

3B performs data normalization, transformation, vintage identity and inventory construction only. It estimates no potential output, trend growth or output gap.
