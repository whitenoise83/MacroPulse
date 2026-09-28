# GitHub Repository Hardening

This document describes the repository settings to apply **after** the repository-hardening branch passes CI.

## Canonical branch

1. Create `main` from the approved repository-hardening commit.
2. Push `main`.
3. In GitHub: **Settings → Branches → Default branch**, change the default branch from `model1d-development` to `main`.
4. Do not delete historical governed development branches until their release lineage is independently confirmed.

The current Model 3 release tag must remain immutable:

`model3-potential-output-v1.0.0`

## Protect `main`

Create a branch ruleset for `main` with at least:

- require a pull request before merge;
- require status checks to pass;
- require the repository-wide `MacroPulse Platform Guard`;
- block force pushes;
- block branch deletion;
- require conversation resolution;
- require branches to be up to date before merge where practical.

For a single-maintainer repository you may allow an explicit administrator bypass, but routine work should still go through the guarded branch.

## Protect release tags

Create a tag ruleset covering:

- `model1*-v*`
- `model2-bvar-v*`
- `model3-*-v*`
- `phase*-v*`

At minimum, block tag update and deletion for released tags. Existing release tags are immutable governance artifacts.

## GitHub Releases

Create GitHub Release records for:

- `model2-bvar-v1.0.2`
- `model3-potential-output-v1.0.0`

Use the committed release README/validation records as the source for release notes. Do not move tags when creating Releases.

## Security

Enable, where available:

- private vulnerability reporting;
- Dependabot alerts;
- dependency graph;
- secret scanning / push protection.

The repository is proprietary even though it is publicly visible. Keep `LICENSE` and the commercial notice on the canonical branch.

## Future work

New Model 4+ work should branch from the protected canonical branch, not from an old model-specific default branch.
