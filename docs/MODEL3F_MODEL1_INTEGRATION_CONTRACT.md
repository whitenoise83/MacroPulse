# Model 3F — Model 1 Current-State Integration Contract

## Boundary

3F is an integration layer, not a new estimator. It consumes persisted Model 1 outputs read-only and aligns them with Model 3 slack research-candidate outputs. The exact governed predecessor is Model 3E commit `5378dd8aeef716f17e46f73716803ac20d101516`.

3F must not refit or mutate Model 1A–1D. It must not consume Model 2 forecasts; forward-gap integration belongs to 3G. It must not select between 3E-A and 3E-B; recursive pseudo-real-time evaluation and candidate selection belong to 3H.

## Provenance

Every integrated Model 1 observation must retain the source identity fields that are available in the persisted source, including model/run identity, model version, forecast stage/date, target period, information-set hash and creation timestamp. Missing optional source fields remain missing; they must not be fabricated.

Alignment is explicit. A caller may require matching target period, origin date and/or information-set identity. A mismatch must be surfaced as a diagnostic or exception and may not be silently coerced.

## Model 3 estimate labels

`filtered_full_sample_parameters` and `smoothed_revised` remain full-sample/revised research estimates. Neither may be relabelled strict real-time. `filtered_real_time_endpoint` construction remains 3H work.

## Persistence

3F performs no DuckDB writes. The bootstrap diagnostic may read existing Model 1 persistence tables/views and report their schemas and provenance, but it may not alter them.

Passing 3F authorizes only 3G — Model 2 Forward-Gap Integration.
