# Model 1D v0.1 Architecture

Model 1D is a governed synthesis layer over the three production engines:

1. Model 1A: annualised quarter-on-quarter real GDP growth
2. Model 1B: headline/core CPI and PCE annualised monthly inflation
3. Model 1C: payroll change, unemployment rate, and annualised wage growth

It selects the latest successful v1.0.0 production run from each source whose
information cutoff is no later than the requested state date. It stores all
source run IDs, source cutoffs, input intervals, source hashes, a source-bundle
hash, and a final state hash.

The first release uses transparent configured anchors to map heterogeneous
forecasts to three bounded scores from -2 to +2:

- Growth momentum
- Inflation pressure
- Labour tightness

It then applies explicit rules to classify the primary macro configuration.
The v0.1 rules are research hypotheses, not validated regime probabilities.
