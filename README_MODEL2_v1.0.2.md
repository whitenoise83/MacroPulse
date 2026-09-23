# Model 2 Bayesian VAR v1.0.2

This is a release-engineering compatibility patch only.

The immutable `model2-bvar-v1.0.1` tag remains fixed at
`7a54c19fe9216b2073b6bfc107ea5e4fc25bebd9`.

Its tag CI (Model 2 Bayesian VAR Guard #18, run `35822437102`, job
`107056962997`) passed the Model 2 v1.0.1 release verifier and the focused
release-metadata tests, then failed in the complete repository suite because
two historical bootstrap tests were not descendant/tag-checkout safe.

The v1.0.2 patch changes only those historical checkout assertions plus the
release-engineering metadata/verifier/tests required to govern this patch.
It does not change BVAR model logic, selected specification, forecast
semantics, probabilistic forecasts, structural identification, scenarios,
pseudo-real-time evidence, or the frozen semantic source manifest.

The selected model remains BVAR(2), shrinkage 0.1, candidate
`a69878bf644615c5`. Frozen Model 2 semantic source remains
`df1da2bcd54cf71277eb8bfe21f6c52caad1c302`.

The two historical tests are made descendant-safe:

- Model 2A continues to verify that the boundary metadata records
  `model2-bvar-development`, but no longer requires the current physical
  checkout to be that named branch.
- Phase III continues to verify the immutable final Phase III release commit
  and now requires that commit to be an ancestor of HEAD, which is valid for
  later governed release tags checked out in detached HEAD.

No existing immutable release tag may be moved or recreated.
