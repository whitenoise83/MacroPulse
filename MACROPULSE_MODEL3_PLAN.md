# MacroPulse Model 3 Plan — Potential Output & Macroeconomic Slack

Model 3 is the next governed MacroPulse modelling layer, beginning from immutable
`model2-bvar-v1.0.2` at `cda24988e772cd2b96be612b7d455c54a06f44fa` on branch `model3-output-gap-development`.

## Purpose

Model 3 estimates sustainable productive capacity and macroeconomic slack. It
separates observed/current and forecast economic activity from latent potential,
while preserving real-time information sets and uncertainty.

Model 3 answers: **How far are current and prospective economic paths from
sustainable economic capacity?**

## Workstreams

3A specification/governance; 3B real-time data/vintages; 3C univariate
trend/filter benchmarks; 3D state-space potential output; 3E multivariate
macroeconomic slack; 3F Model 1 current-state integration; 3G Model 2 forward-gap
integration; 3H pseudo-real-time evaluation/selection; 3I production hardening
and release.

## Core latent objects

- potential output level
- trend potential-output growth
- output gap
- uncertainty around potential output and the output gap

The core decomposition is

`y_t = y*_t + gap_t`

where `y_t` is log real output, `y*_t` is latent log potential output, and
`gap_t` is the cyclical output component.

## Initial candidate architecture

Model 3A freezes the research architecture, not a production winner. Candidate
development includes transparent univariate trend/filter benchmarks, a
state-space unobserved-components model, and a multivariate slack extension
using economically interpretable labour-market and inflation information.

No benchmark or candidate receives automatic production authority.

## Upstream interfaces

Model 1 supplies governed current-state information through a later explicit
3F integration contract. Model 2 supplies governed forecast distributions
through a later explicit 3G integration contract.

Model 2 forecasts may not determine or retune the historical/current potential
output estimate. Forward Model 2 paths may be combined with a separately
governed Model 3 potential/slack process only after the 3G contract is frozen.

## Real-time discipline

Pseudo-real-time evaluation is mandatory. Information must have existed by the
historical cutoff; vintage identity must be explicit; revised/smoothed estimates
must be separately labelled; and future releases may not fill historically
unavailable observations.

## Governance

Model 3 cannot mutate Models 1 or 2, move/recreate their frozen tags, backfill
their governed outputs, tune predecessor models, use future information,
silently substitute revised data for real-time vintages, use generative AI in
the governed econometric core, or automatically switch/promote specifications.

Passing 3A authorizes only Model 3B real-time data/vintage architecture.
