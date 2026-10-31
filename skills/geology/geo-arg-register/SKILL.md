---
name: geo-arg-register
description: Fill a GeoArg contract for a geological claim. Use when the user wants to structure, register, or check a geological argument, or asks whether a claim's evidence actually supports it.
---

# Register a geological argument

A geological argument hides its load-bearing premises. This skill turns one claim into a **contract**: a small set of YAML files that name every premise, every condition under which the inference holds, every way the argument could be defeated, and the test that would settle each one. The contract is what makes the argument checkable by someone else.

Write the contract to be recomputable, not persuasive. The verdict is computed by `geoarg`, not by you.

## When to reach for this

- The user states a geological conclusion and wants it recorded, defended, or reviewed.
- The user asks what evidence supports a claim, or what would falsify it.
- A paper, report, or map makes a claim that will be cited by someone else.

## Steps

1. **Name the claim.** One sentence, one scope: what is claimed, where, and when. Choose `kind` (reconstruction, timing, correlation, mechanism, existence, classification) and `layer` (L0 definition to L4 interpretation).
   Done when: `claim` has `id`, `statement`, `kind`, `layer`, `scope`, and a reader can tell what would make it false.

2. **Split the premises.** Mark each premise `evidenced` (points at records in `evidence.yaml`) or `derived` (points at another registered argument). A premise that points at nothing is the thing this skill exists to expose.
   Done when: every premise resolves to a record or another argument, and no premise reads like general knowledge.

3. **Expose the warrant.** Give the inference a `rule_id` (for example `W.rigid-plate-euler`), then list the **conditions** it needs to hold (`cp`: structural, temporal, methodological, or calibration) and the **defeaters** that would break it (`undercutting` attacks the inference, `rebutting` attacks the conclusion). Every condition and every defeater gets a `test_ref`.
   Done when: no condition and no defeat condition lacks a test.

4. **Write the entailments.** State what must also be true if the claim holds, and how surprising each consequence is (`risk`: low, medium, high). The high-risk entailment is usually the argument's real test.
   Done when: at least one entailment is recorded with a test that could fail, preferably on an evidence family independent of the premises.

5. **Record the evidence.** For each record fill `source`, `coverage` (spatial extent, coverage fraction, detectability), `independence` (family, class, shared sources), `verification.level`, and `status`. A `transcription` record also needs `source_locator` (page plus the sentence as it appears in the source).
   Done when: every record has coverage numbers and an independence family, every transcription record has a locator, and unverified records say so instead of inheriting confidence. Only records referenced by an evidenced premise enter the independence report; a `derived` premise stays undetermined, so its evidence is audited inside the other argument.

6. **Declare the gaps.** List what the contract cannot express, with `kind` (cannot-express, ambiguous, missing-field, overspecified, other), a `description` of the information that cannot be carried, and `severity` (blocking, annoying, minor). A gap is instrumentation, not failure.
   Done when: `gaps` exists, or the contract says "none found" with one line of why.

7. **Run the gate.** If any record is transcription level, run `geoarg ground <case> --pdf <paper>` and fix every `not-found` or `page-mismatch` quote before continuing. Then run `geoarg check <case>` and fix every problem, run `geoarg judge <case>`, write the Word report with `geoarg report <case>` (it writes `<case>/report.docx`; add `--format md` only when Markdown is requested), and commit the verdict with `geoarg commit <case>`. If `geoarg` is not on PATH, use `python -m geoarg` for every command; a bare `.` works as the case path when you are inside the case directory.
   Done when: `check` exits 0, every accepted transcription quote is `grounded`, the verdict prints, and `<case>/report.docx` exists with a grounding table and a decisive-test table.

## Rules

- Every condition and every defeat condition carries a test. A condition without a test is rhetoric.
- `unknown` is a legal state. The contract reports unknowns; it does not fill them with confidence.
- A transcribed quote carries a `source_locator`, and `geoarg ground` decides whether it stays accepted. If the quote is not in the PDF, the record becomes `disputed`; do not rephrase the quote until it matches.
- Grounding is not verification of meaning. A grounded quote can still be cited for the wrong claim; that is the audit's problem, not the gate's.
- Cite the record you read. Evidence refs resolve to entries in `evidence.yaml` with a source, not to memory.
- One claim per contract. Two claims in one file hide the shared premises that the audit needs to see.
- When a premise rests on another argument, link it as `derived`. Do not copy the conclusion.
- Keep the scope small enough that one test can address it.

## Field reference and case

- `references/contract-fields.md` holds the required fields and allowed values for all three files. Read it the first time you fill a contract.
- `examples/south-atlantic` is a worked case (plate reconstruction). Copy its shape, not its content.
