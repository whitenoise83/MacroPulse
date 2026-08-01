# MacroPulse Model 1C v0.6.0 — Governed Live Labour Forecasting

Model 1C advances from a validated candidate to a governed live candidate. The release does not approve Model 1C for production and does not modify the frozen Model 1A or Model 1B specifications.

## Governed headline policy

| Target | Month open | After week 1 | After week 2 | Month end | Pre-employment report |
|---|---|---|---|---|---|
| PAYEMS | Labour 12-Month Mean | Labour Equal-Weight Ensemble | Labour Bridge Ridge | Labour Bridge Ridge | Labour Bridge Ridge |
| UNRATE | Labour Equal-Weight Ensemble | Labour Equal-Weight Ensemble | Labour Equal-Weight Ensemble | Labour Equal-Weight Ensemble | Labour Equal-Weight Ensemble |
| CES0500000003 | Labour Bridge Ridge | Labour Bridge Ridge | Labour Equal-Weight Ensemble | Labour Equal-Weight Ensemble | Labour Equal-Weight Ensemble |

The adaptive selector is stored separately as a shadow challenger. It never controls the governed headline in v0.6.0.

## Live uncertainty

The governed 80% interval uses `exp_weighted_q80` with:

- strictly earlier target-month errors only;
- minimum 24 prior errors;
- rolling 48-month window;
- exponential decay of 0.94.

## Provenance and governance

Every governed run stores:

- candidate validation ID and vintage backtest ID;
- information cutoff and data-as-of date;
- configuration and code hashes;
- information-set hash;
- model-state hash;
- governance signature;
- stable and shadow forecasts separately.

## Labour news decomposition

Comparable governed runs are decomposed into:

- new observations;
- revisions and removed observations;
- model-refit effects;
- stable-policy changes caused by a stage transition;
- residual interaction.

The attribution is required to reconcile to the total headline forecast change within the operational tolerance.

## Commands

```cmd
python scripts\download_labour_data.py
python scripts\run_labour_nowcast.py
python scripts\run_labour_operational_validation.py
```

Optional commands:

```cmd
python scripts\run_labour_nowcast.py --as-of 2026-07-31
python scripts\run_labour_nowcast.py --skip-news
python scripts\run_labour_news.py
```

## Lifecycle

`US_LABOUR_NOWCAST_1C v0.6.0` remains `development` with status `governed_live_candidate`. A passing live operational validation is required before freeze assessment and model-owner signoff.
