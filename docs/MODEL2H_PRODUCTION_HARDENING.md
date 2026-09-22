# Model 2H — Production Hardening / Release Candidate

Model 2H begins from the closed Model 2G development-selection workstream at
`ad196fb5d9a2d0d2c9113ea94d1363573c0c3b56`, validated by Model 2 Bayesian VAR Guard run `35754237381`.

The frozen Model 2G selection is candidate `a69878bf644615c5`, lag order
`2`, Minnesota shrinkage `0.1`. The selection
evidence payload hash is `2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7`.

`macropulse.bvar.production.run_model2_forecast` is the governed pure forecast
interface. It requires an exact-vintage snapshot and information cutoff, rebuilds
the quarterly panel using frozen Model 2B rules, fits only the frozen selected
candidate, produces posterior-mean forecasts for 1/2/4/8 quarters, simulates
the Model 2D posterior predictive distribution, and computes the Model 2E
recursive IRF/FEVD objects.

It performs no database writes and does not run Model 2F scenario conditioning
automatically. Default simulation remains 5000 paths with seed
20260904. Output identity includes snapshot, panel, predictive-draw and
full-output fingerprints.

No candidate re-ranking, reselection, prospective retuning or automatic
switching is authorized.

This bootstrap creates a release candidate, not the immutable release tag.
The planned release tag is `model2-bvar-v1.0.0`. After the exact 2H source-hardening
commit passes branch CI, a separate release-metadata patch will freeze the
release manifest and add tag-specific release verification. Production
authority remains none until that immutable tag exists and its release CI passes.
