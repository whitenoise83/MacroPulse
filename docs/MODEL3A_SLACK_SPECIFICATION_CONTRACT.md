# Model 3A — Potential Output & Macroeconomic Slack Specification & Governance Contract

Model 3A freezes the research design before estimator implementation. The
immutable base is `model2-bvar-v1.0.2` at `cda24988e772cd2b96be612b7d455c54a06f44fa`.

## Economic object

Model 3 decomposes observed real activity into latent sustainable capacity and
cyclical slack:

`y_t = y*_t + gap_t`

A baseline state-space family may represent potential output and trend growth as

`y*_t = y*_(t-1) + g*_(t-1) + eta_y,t`

`g*_t = g*_(t-1) + eta_g,t`

with a persistent cyclical component such as

`gap_t = phi_1 gap_(t-1) + phi_2 gap_(t-2) + epsilon_t`.

These equations define a candidate family, not a production winner.

## Candidate and benchmark discipline

3C will implement transparent trend/filter benchmarks. 3D will implement the
state-space potential-output family. 3E may add labour-market and inflation
information through economically interpretable multivariate slack relations.
The exact production specification must be selected using predeclared
pseudo-real-time development evidence and then frozen.

## Real-time contract

Real-time estimation is mandatory. Every historical origin must respect its
information cutoff and explicit vintage identity. Revised or smoothed estimates
are separate analytical objects and may not be represented as real-time
estimates. No look-ahead is permitted.

## Model 1 interface

Model 1 integration is deferred to 3F. Model 3 may consume governed current-state
information only through the later frozen interface. Model 3 cannot modify,
backfill, retune, promote, demote, or reinterpret frozen Model 1 releases.

## Model 2 interface

Model 2 integration is deferred to 3G. The immutable upstream release is
`model2-bvar-v1.0.2`. Model 2 forecast paths must not determine or retune the
historical/current potential-output estimator. A forward output-gap distribution
may be constructed only after a separate Model 3 potential/slack process and the
3G interface are frozen.

## Descendant contract

Later models, including Model 4, may consume released Model 3 outputs but may
not retune Model 3 merely because an alternative slack estimate improves a
downstream equation. Downstream performance is not authority to rewrite an
upstream governed history.

## Governance

The governed Model 3 core may not use generative AI, future information, silent
latest-vintage substitution, automatic specification switching, automatic
promotion, or mutation of frozen predecessor releases/tags.

Passing Model 3A authorizes only Model 3B real-time data and vintage
architecture. It does not authorize estimation, production use, database
writes, or release tagging.
