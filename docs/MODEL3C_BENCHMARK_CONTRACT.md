# Model 3C — Univariate Trend / Filter Benchmark Contract

## Authority

Model 3C descends from the closed Model 3B commit `5849b89367defdef68c0676fdcd1d2f7182bd873`. Its ultimate immutable predecessor remains Model 2 release `model2-bvar-v1.0.2` at `cda24988e772cd2b96be612b7d455c54a06f44fa`.

Passing 3C authorizes only **3D — State-Space Potential Output**.

## Purpose

3C creates transparent univariate reference estimators for log real GDP. These are benchmark and diagnostic objects, not a production selection mechanism.

The sole governed input is `real_gdp_log` from the 3B quarterly information-set panel.

## Benchmark families

### Deterministic linear trend

OLS of log real GDP on an intercept and deterministic time trend. A full-sample estimate is two-sided. In pseudo-real-time evaluation it must be re-estimated using only the information set available at each origin.

### Hodrick–Prescott diagnostic benchmark

Quarterly HP filter with lambda 1600. The conventional full-sample HP trend is explicitly two-sided and must not masquerade as a real-time estimate.

The conventional full-sample HP diagnostic is not eligible for recursive-origin pseudo-real-time scoring. The one-sided HP benchmark owns the origin-safe HP role.

### One-sided HP benchmark

At origin `t`, the HP filter is fit only to observations available through `t`; only the terminal trend estimate is retained for that origin. Future observations may not revise that stored origin estimate.

### Hamilton regression benchmark

The governed benchmark uses horizon `h=8` quarters and `p=4` lags. For log output `y`, estimate

`y_(t+h) = beta_0 + beta_1 y_t + ... + beta_p y_(t-p+1) + epsilon_(t+h)`.

The Hamilton cyclical component at `t+h` is the regression residual. The corresponding benchmark potential log output is observed log output minus that residual.

At a pseudo-real-time origin, fitting and estimation may use only data available through that origin.

## Output convention

Every benchmark result exposes:

- benchmark identifier;
- estimate origin;
- observed log real GDP;
- potential log output;
- potential output level;
- output gap in percent.

For 3C, `output_gap_pct = 100 * (observed_log_output - potential_log_output)`.

## Governance

3C does not:

- choose a production winner;
- estimate the 3D state-space core;
- estimate the 3E multivariate slack model;
- integrate Model 1;
- consume Model 2 forecast distributions;
- write governed production tables;
- alter predecessor files or tags.

Two-sided full-sample benchmark estimates are diagnostics. They must be clearly distinguishable from origin-specific pseudo-real-time estimates.
