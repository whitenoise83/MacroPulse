# Model 1D v0.2 Historical Reconstruction

Model 1D v0.2 reconstructs monthly macro-state snapshots using only source
runs whose information cutoffs are on or before each state date.

For each month-end it:

1. Selects the latest complete Model 1A GDP run.
2. Selects the latest complete Model 1B inflation run.
3. Selects the latest complete Model 1C labour run.
4. Applies the same v0.2 normalization and regime rules.
5. Stores source run IDs, source hashes, source-bundle hashes, and cutoffs.
6. Audits that no source cutoff is later than the reconstructed state date.
7. Enumerates possible regimes across the dimension uncertainty envelope.
8. Calculates regime durations and one-step transition frequencies.

The reconstruction is limited by the source-run history actually available in
DuckDB. It does not fabricate historical vintages that were never stored.
