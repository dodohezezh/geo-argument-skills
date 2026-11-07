---
name: geo-arg-audit
description: Audit a GeoArg contract for independence and discriminating power. Use when the user asks how strong a geological argument is, whether its evidence lines are really independent, how much confidence it deserves, or which test would settle it.
---

# Audit an argument

An audit answers two questions the contract's verdict cannot answer by itself: **how many independent lines does this argument really rest on**, and **which tests could have gone the other way**. `geoarg` computes both. Your job is to interpret them and name the decisive test.

The verdict without this audit is a number without a unit. Run `geoarg judge` for the verdict, `geoarg independence` for the effective evidence count, and `geoarg hit-set` for the tests that would retract the claim now. If `geoarg` is not on PATH, use `python -m geoarg` in every command.

## Preflight

Run `geoarg --version` before anything else. If the command is missing, stop and tell the user the engine is not installed; do not compute verdicts, effective evidence counts, or acceptance rates by hand. If the version is older than 1.12.2, ask the user to upgrade before continuing.

## Steps

1. **Map the evidence families.** List the records from `evidence.yaml` with family, independence class, and shared sources. Follow the calibration chain: two records that share a timescale, a plate model, or a data release are one line of evidence wearing two names.
   Done when: every record sits in a family, and every shared source is named.

2. **Check the quotes before counting them.** If any record is transcription level, run `geoarg ground <case> --source <paper>` (PDF, DOCX, HTML, Markdown, or plain text; page numbers are meaningful only for PDF). Read the acceptance rate and every non-grounded status: `not-found` means the draft was fabricated and the record must become `disputed`; `page-mismatch` means the citation page is wrong and the page is fixed, not the quote; `not-groundable` means the source has no text layer, so OCR it or lower the verification level.
   Done when: every accepted transcription quote is `grounded`, or the record is `disputed` with a line saying why.

3. **Resolve any linked arguments.** If the argument has `derived` premises, run `geoarg workspace <dir>` (the directory holding the case, or the nearest workspace root). Check that every chain entry is resolved, read the target's verdict, and stop if the workspace reports an unresolved reference, a cycle, or a shared evidence id with different content. A resolved chain tells you which evidence to audit inside the other argument; it does not add independent lines to this one.
   Done when: every `derived` premise has a resolved chain entry, and any evidence conflict is named in the audit.

4. **Compute the effective evidence count.** Run `geoarg independence <case>`. Report `n_eff` against the raw record count, and explain each warning: a shared calibration labelled `data`, a `physical` label on records from one family, a declared calibration that no record attaches to.
   Done when: `n_eff / n` is in the report and each warning has a one-line cause.

5. **Grade the tests' power.** Run `geoarg hit-set <case>`. For each gating test, state in one sentence what the competing hypothesis predicts. If both hypotheses predict the same outcome, the power is `none`. Keep the contract's power labels honest: a test that cannot fail is not a test.
   Done when: every gating test has power and a stated counter-prediction.

6. **Find the decisive test now.** From the hit-set, choose the outcome with the highest power and the lowest cost that would change the verdict. If no single test changes it, say the claim is currently undecidable and name what would make it decidable.
   Done when: the report names one test (or states that none exists) and what its outcome would do to the verdict.

7. **Check the record and its bindings.** If the case has a committed record, run `geoarg verify <case>`. A non-zero exit means the audit is looking at drift, not at what was committed: report every problem (`input changed since commit`, `engine changed`, `registry record is not the latest commit`, `argument chain changed`, `deliverable changed since attestation`) and stop attributing the delivered files to the committed verdict. Run `geoarg ledger <case>` when the user asks for history; read `anchor.json` when one exists, and remember that an anchor only means something if it was kept outside the repository.
   Done when: the audit states whether the current files match the committed record and whether the deliverable was attested; a missing attestation is reported as such, never assumed.

8. **Write the confidence statement.** One paragraph: verdict, `n_eff / n`, the acceptance rate when transcription evidence is involved, the power profile of the gating tests, the decisive test, and any blocking gap. Keep the numbers in the sentence.
   Then write the commentary paragraph yourself: two to four sentences on what the verdict means for this argument, using the numbers the engine printed. Do not copy the template lines. Pass it to the card with `--judgment "<text>"` or `--judgment-file <path>`; the audit block records its digest. Quote the author's own condition, evidence, and prediction statements; do not invent labels for them.
   Then pick the reader. Ask once per session whether the output goes to the researcher (self-check) or a reviewer (assessment); remember the answer for the session. The identity is presentation state, not contract data: it changes what the card selects, never the verdict, `n_eff`, or grounding numbers. Write the card with `geoarg card <case> --for researcher` or `--for reviewer` (`--lang zh` for a Chinese frame; `--out` to a file). Write the full report with `geoarg report <case>` when the reader needs the complete contract: it writes `<case>/report.docx` in Word by default; `--format md` only when the user asks for Markdown; it accepts the same `--judgment` / `--judgment-file` flags.
   Done when: the card or report exists, its header names the reader and the declared field (if any), the commentary is yours and its digest appears in the audit block, and the numbers in the card match `geoarg judge`, `geoarg independence`, and the grounding ledger.

- Check the domain pack: `geoarg domains <case>` must list every non-built-in
  value the case uses, and `verify` reports `domain pack changed since commit` if
  the pack was edited after commit.

## Rules

- For a review hand-off, `geoarg report <case> --format html` produces a self-contained page; it is a rendering, not extra evidence.


- When the question is which data would matter, run `geoarg impact <case>`; it reports corollaries of declared states, not probabilities.


- A derived premise is audited through its target. `geoarg workspace` resolves the chain and lists shared evidence; do not count the target's evidence twice, and do not accept a chain the workspace cannot resolve.
- Count families, not papers. Two papers built on one dataset are one line.
- Independence lives in the calibration chain: timescale, model, data release, inference step. Annotate it there.
- Quote grounding is not interpretation. A grounded quote can still be quoted for the wrong claim; a `not-found` quote is a fabrication and must not be kept.
- Report the acceptance rate (`grounded / drafted`) whenever transcription-level records are in play. An argument can rest on one independent line and on zero grounded quotes at the same time.
- An attestation is a byte-level claim, not a quality claim. `geoarg attest` ties report/cards and the commentary to one committed record; it does not make the prose faithful, and a missing or stale attestation must be reported as a gap in provenance, not ignored.
- An anchor is only as good as its custody. If `anchor.json` never left the case directory, say that the ledger head is not externally anchored; do not describe a local file as a timestamp.
- Write the report twice: once in the language of the paper (`--lang en` or the paper's language) and once in the system language of the machine running the model (`--lang auto`). Name them `report.<lang>.docx` with `--out`, for example `report.en.docx` and `report.zh.docx`. The report frame is translated; contract content stays as the case is written.
- `--brief` writes a one-page brief instead of the full report. Use it when the user asks for a short version, not as the default.
- Ask the reader's identity once per session, not once per artifact. A researcher needs the next test and the gaps; a reviewer needs the reasons, what would change the conclusion, and the audit information. Both pages carry the same verdict, `n_eff`, and grounding numbers.
- Write the deliverable in the author's own terms. Quote the condition, evidence, and prediction statements as written; use ordinary language for status and reasons. Do not translate internal engine roles into new jargon. Machine values stay in the ledger and the audit block.
- The commentary is prose, not computation: two to four sentences, the engine's numbers, and the card records its digest. If it reads like a template, rewrite it.
- Support requires a test that could have failed. A satisfied condition (`cp` holds, defeater refuted, entailment passed) only counts when a referenced test has passed with power `low` or better; the engine reports the rest as `unbacked`. A passed test with power `none` leaves the claim undetermined.
- Computed statuses win. When a test records `result` and `pass_rule`, `geoarg judge` computes its status and flags any mismatch with the typed field; audit the recorded value and rule, not only the typed status.
- Report `n_eff / n` explicitly. Write "5 records, 1.8 effective lines", not "several independent lines".
- Treat the rho values in `independence.py` as estimates: state them, and say what a calibration study would change.
- When the claim is already defeated, the audit reports why and does not re-litigate it.

- When someone hands you a package instead of a repository, run `geoarg verify-package <dir>` before reading the report: it recomputes every digest and checks the record, ledger chain, attestation, anchor and grounding cross-references. A version warning is not a failure; a digest mismatch is.

## Formula and method reference

Read `references/metrics.md` for the n_eff formula, the rho table, set-discrimination and expected-information-gain versions of discriminating power, and the cost-weighted decisive-test rule.
