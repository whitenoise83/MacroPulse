# Model 2A — Bayesian VAR Specification & Governance Contract

Model 2A freezes the research design before estimation. Base: `phase3-evaluation-v1.0.1` at
`edfc37b8f5f016710fb96402d205dcd35f2e09ca`.

The forecast object is a quarterly joint posterior predictive distribution for
real GDP growth, core PCE inflation, unemployment and the federal funds rate at
1, 2, 4 and 8-quarter horizons.

The baseline family is a conjugate Normal-Inverse-Wishart BVAR with
Minnesota-style shrinkage. Predeclared candidates are lag orders 2/4 and overall
shrinkage 0.1/0.2/0.4. Prospective performance may not automatically retune the
specification.

Pseudo-real-time evaluation is mandatory: inputs must exist by cutoff, vintage
identity is explicit, first-release outcomes are default where defined, revised
outcomes are separate, and no future releases may fill unavailable values.

At minimum, Model 2G compares against univariate AR, classical VAR, and a simple
historical-mean/random-walk benchmark where economically appropriate. Point
metrics are RMSE/MAE/bias; density metrics include log predictive density, CRPS,
50/80/95% coverage and interval score.

Initial structural analysis uses recursive ordering GDP growth → core PCE
inflation → unemployment → policy rate. Scenario output is not a causal claim
without identification.

Model 2 cannot modify frozen Model 1 releases or use Model 1D prospective
outcomes for tuning. The Model 1 current-state interface is deferred to 2B.

The sole pre-existing-file exception in 2A is release-guard maintenance of
`tests/test_phase3_bootstrap_contract.py`, only to permit later roadmap branches
that descend from the immutable `phase3-evaluation-v1.0.1` release. It cannot move/recreate a
tag or alter Phase III evaluation/model semantics.

Passing 2A authorizes only Model 2B data/vintage architecture.
