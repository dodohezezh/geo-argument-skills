# Metrics: independence and discriminating power

## Effective evidence count

    n_eff = n / (1 + (n - 1) * rho_bar)

`n` is the number of evidence records supporting the premises. `rho_bar` is the mean pairwise error correlation estimated from the contract's independence annotations:

| Situation | rho |
| --- | --- |
| shared calibration product (timescale, plate model, DEM, data release) | 0.75 |
| same `independence_class` | 0.15 (physical), 0.45 (method), 0.60 (data) |
| same evidence family only | 0.35 |
| no shared source, different family | 0.05 |

The estimates are priors for ranking, not measurements. A calibration study would replace them with measured correlations; until then, report `n_eff / n` and the rho assumption alongside it.

## Discriminating power, set version

For a test `T` and two hypotheses `H1`, `H2`:

    D(T) = 1 - |P1 ∩ P2| / |P1 ∪ P2|

where `Pi` is the set of outcomes test `T` could produce if `Hi` were true. `D = 0` when both hypotheses predict the same outcome set: the test cannot discriminate. Multiply by a reliability weight when measurements are noisy. This version needs no priors and survives a review.

## Discriminating power, information version

    EIG(T) = H(H) - E_outcome[ H(H | outcome) ]

Expected information gain about the hypothesis, in bits. Use it when you can state priors over hypotheses and a likelihood model. Use the set version when you cannot, which is the normal case in historical geology.

## Cost-weighted decisive test

    decisive = argmax_over_T  D(T) / cost(T)

An expensive test that barely discriminates loses to a cheap test that separates the hypotheses. The formula is the ideal ranking; the engine implements the simple version: `hit-set` reports each event's `cost` and sorts by power, then by cost. Name the best single test from that order.

## Minimal satisfying sets

When several conditions must hold together, the set of outcomes that defeats the claim is a minimal hitting set over the contract's defeat paths. The engine enumerates single-event paths only. For combinations of degrading defeaters, state the combination explicitly in the report rather than assuming the engine found it.

## Grounding acceptance rate

    acceptance_rate = grounded / drafted

`drafted` counts evidence records that declare a `source_locator`; `grounded` counts the quotes found on the declared page. `page-mismatch` is a citation error (the quote exists on another page); `not-found` is a fabricated draft. Report the rate next to `n_eff`: an argument can rest on one independent line and on zero grounded quotes at the same time. `geoarg ground` exits non-zero when any declared quote is not grounded, and `--allow-partial` exists only to inspect a partial ledger. The gate has the shape of speculative decoding (draft, verify, accept), but the verifier is a string match against the source, not a judge of meaning.

## Reporting units

- Independence: `n_eff / n`, mean rho, families, shared calibration.
- Grounding: acceptance rate, plus the count and status of every non-grounded quote.
- Power: the contract's `none/low/medium/high` label plus one sentence of counter-prediction.
- Confidence: one paragraph with the verdict, the numbers, and the decisive test.
