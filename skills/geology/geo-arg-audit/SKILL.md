---
name: geo-arg-audit
description: Audit a GeoArg contract for independence and discriminating power. Use when the user asks how strong a geological argument is, whether its evidence lines are really independent, how much confidence it deserves, or which test would settle it.
---

# Audit an argument

An audit answers two questions the contract's verdict cannot answer by itself: **how many independent lines does this argument really rest on**, and **which tests could have gone the other way**. `geoarg` computes both. Your job is to interpret them and name the decisive test.

The verdict without this audit is a number without a unit. Run `geoarg judge` for the verdict, `geoarg independence` for the effective evidence count, and `geoarg hit-set` for the tests that would retract the claim now. If `geoarg` is not on PATH, use `python -m geoarg` in every command.

## Steps

1. **Map the evidence families.** List the records from `evidence.yaml` with family, independence class, and shared sources. Follow the calibration chain: two records that share a timescale, a plate model, or a data release are one line of evidence wearing two names.
   Done when: every record sits in a family, and every shared source is named.

2. **Check the quotes before counting them.** If any record is transcription level, run `geoarg ground <case> --pdf <paper>`. Read the acceptance rate and every non-grounded status: `not-found` means the draft was fabricated and the record must become `disputed`; `page-mismatch` means the citation page is wrong and the page is fixed, not the quote; `not-groundable` means the PDF has no text layer, so OCR it or lower the verification level.
   Done when: every accepted transcription quote is `grounded`, or the record is `disputed` with a line saying why.

3. **Compute the effective evidence count.** Run `geoarg independence <case>`. Report `n_eff` against the raw record count, and explain each warning: a shared calibration labelled `data`, a `physical` label on records from one family, a declared calibration that no record attaches to.
   Done when: `n_eff / n` is in the report and each warning has a one-line cause.

4. **Grade the tests' power.** Run `geoarg hit-set <case>`. For each gating test, state in one sentence what the competing hypothesis predicts. If both hypotheses predict the same outcome, the power is `none`. Keep the contract's power labels honest: a test that cannot fail is not a test.
   Done when: every gating test has power and a stated counter-prediction.

5. **Find the decisive test now.** From the hit-set, choose the outcome with the highest power and the lowest cost that would change the verdict. If no single test changes it, say the claim is currently undecidable and name what would make it decidable.
   Done when: the report names one test (or states that none exists) and what its outcome would do to the verdict.

6. **Write the confidence statement.** One paragraph: verdict, `n_eff / n`, the acceptance rate when transcription evidence is involved, the power profile of the gating tests, the decisive test, and any blocking gap. Keep the numbers in the sentence.
   Done when: the statement stands alone without the rest of the report, and it uses counts, not adjectives.

## Rules

- Count families, not papers. Two papers built on one dataset are one line.
- Independence lives in the calibration chain: timescale, model, data release, inference step. Annotate it there.
- Quote grounding is not interpretation. A grounded quote can still be quoted for the wrong claim; a `not-found` quote is a fabrication and must not be kept.
- Report the acceptance rate (`grounded / drafted`) whenever transcription-level records are in play. An argument can rest on one independent line and on zero grounded quotes at the same time.
- Support requires a test that could have failed. A passed test with power `none` leaves the claim undetermined.
- Report `n_eff / n` explicitly. Write "5 records, 1.8 effective lines", not "several independent lines".
- Treat the rho values in `independence.py` as estimates: state them, and say what a calibration study would change.
- When the claim is already defeated, the audit reports why and does not re-litigate it.

## Formula and method reference

Read `references/metrics.md` for the n_eff formula, the rho table, set-discrimination and expected-information-gain versions of discriminating power, and the cost-weighted decisive-test rule.
