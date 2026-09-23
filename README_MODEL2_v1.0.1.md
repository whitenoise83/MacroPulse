# Model 2 Bayesian VAR v1.0.1

This is a release-engineering compatibility patch only.

The immutable `model2-bvar-v1.0.0` tag remains fixed at `22664c1d3a102ce88b62966dfb6c1f8a3405023f`. Its tag
CI failed in Guard #15, run `35775232829`, because
GitHub Actions checked the tag out in detached HEAD while the Model 2G verifier
required the named development branch.

The compatibility patch makes the Model 2G verifier accept detached HEAD while
still rejecting any non-empty unexpected branch.

There are no changes to model logic, selected specification, forecasts,
uncertainty, structural identification, scenarios, or pseudo-real-time
selection evidence. Frozen Model 2 source remains `df1da2bcd54cf71277eb8bfe21f6c52caad1c302` and the
selected model remains BVAR(2), shrinkage 0.1, candidate `a69878bf644615c5`.

The new immutable release tag will be `model2-bvar-v1.0.1` after this single patch commit
passes exact branch CI.

The frozen Model 2H verifier is descendant-safe for this single exact Model 2G detached-HEAD branch-guard transformation and rejects any other change to the frozen 2G verifier.

Guard #16 (run 35781569124) failed only in release-verifier state detection after all Model 2 lineage verifiers and focused workstream tests passed. The final correction anchors release state to commit lineage and consistently excludes ignored/generated runtime paths. Model and forecast semantics remain unchanged.
