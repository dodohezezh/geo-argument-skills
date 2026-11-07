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

## Preflight

Run `geoarg --version` before anything else. If the command is missing, stop and tell the user the engine is not installed; do not compute verdicts, effective evidence counts, or acceptance rates by hand. If the version is older than 1.12, ask the user to upgrade before continuing.

Starting from a paper or a draft? `geoarg adopt notes.md --out <case>` writes a draft case and `geoarg check <case> --profile draft --explain` lints it. Starting from a question? `geoarg patterns` lists the shipped skeletons and `geoarg new <case> --pattern <name>` writes one. Neither replaces the strict profile.

## Steps

1. **Name the claim.** One sentence, one scope: what is claimed, where, and when. Choose `kind` (reconstruction, timing, correlation, mechanism, existence, classification) and `layer` (L0 definition to L4 interpretation). Also record the argument's field if you can name it: `profile.primary` (general-geology, geochronology, planetary-geology, or tectonics), an optional `secondary` list, and a one-line `rationale`. The profile is metadata only: the deliverable header labels the field, and it selects no vocabulary and changes no verdict, `n_eff`, or acceptance rate.
   Done when: `claim` has `id`, `statement`, `kind`, `layer`, `scope`, a reader can tell what would make it false, and the field is either declared or deliberately omitted.

2. **Split the premises.** Mark each premise `evidenced` (points at records in `evidence.yaml`) or `derived` (points at another registered argument via `argument_ref`). A premise that points at nothing is the thing this skill exists to expose.
   Done when: every premise resolves to a record or another argument, and no premise reads like general knowledge.

3. **Expose the warrant.** Give the inference a `rule_id` (for example `W.rigid-plate-euler`), then list the **conditions** it needs to hold (`cp`: structural, temporal, methodological, or calibration) and the **defeaters** that would break it (`undercutting` attacks the inference, `rebutting` attacks the conclusion). Every condition and every defeater gets a `test_ref`. Write each test in `test.yaml`; when a test's outcome is a number, record `result` plus a `pass_rule` so the engine computes `passed`/`failed` instead of trusting a typed status.
   Done when: no condition and no defeat condition lacks a test.

4. **Write the entailments.** State what must also be true if the claim holds, and how surprising each consequence is (`risk`: low, medium, high). The high-risk entailment is usually the argument's real test.
   Done when: at least one entailment is recorded with a test that could fail, preferably on an evidence family independent of the premises.

5. **Record the evidence.** For each record fill `source`, `coverage` (spatial extent, coverage fraction, detectability), `independence` (family, class, shared sources), `verification.level`, and `status`. A `transcription` record also needs `source_locator` (page plus the sentence as it appears in the source).
   Done when: every record has coverage numbers and an independence family, every transcription record has a locator, and unverified records say so instead of inheriting confidence. Only records referenced by an evidenced premise enter the independence report; a `derived` premise is resolved through the workspace, so its evidence is audited inside the other argument.

6. **Declare the gaps.** List what the contract cannot express, with `kind` (cannot-express, ambiguous, missing-field, overspecified, other), a `description` of the information that cannot be carried, and `severity` (blocking, annoying, minor). A gap is instrumentation, not failure.
   Done when: `gaps` exists, or the contract says "none found" with one line of why.

7. **Run the gate.** If any record is transcription level, run `geoarg ground <case> --source <paper>` and fix every `not-found` or `page-mismatch` quote before continuing; `ground` exits non-zero when any declared quote fails, and `--allow-partial` exists only to inspect a partial ledger. Then run `geoarg check <case>` and fix every problem, run `geoarg judge <case>`, deliver with `geoarg report <case>` (it writes `<case>/report.docx`; add `--format md` only when Markdown is requested) or with `geoarg card <case> --for <reader>` when the reader asked for a conclusion page, and commit the verdict with `geoarg commit <case>`. If the argument links another argument (`derived` premise), run `geoarg workspace <dir>` first: it resolves every chain, lists shared evidence, and reports drift; `commit` refuses an unresolved reference or a cycle. When the deliverable is ready to hand over, bind it to the committed record with `geoarg attest <case> --judgment-file <text>`; add `geoarg anchor <case>` when the reader needs a checkpoint that can be kept outside the repository. Run `geoarg verify <case>` as the final check. If `geoarg` is not on PATH, use `python -m geoarg` for every command; a bare `.` works as the case path when you are inside the case directory.
   Done when: `check` exits 0, every accepted transcription quote is `grounded`, every `derived` premise resolves in the workspace, the verdict prints, the deliverable exists with a grounding table and a decisive-test table, `commit` accepted the contract, `attest` binds the delivered files, and `verify` exits 0.

- A case may widen the built-in enums with a `domain.yaml` next to it (or in a
  parent directory). Prefer a pack over inventing new YAML fields, and run
  `geoarg domains <case>` to confirm the effective values before `check`, and `geoarg advise <case>` once to see the pack's suggested tests and evidence families (advice is a checklist, not a requirement).
- `geoarg edit <case>` opens a local form editor; it writes the same YAML files
  and validates on save. It is a convenience, not a new trust level.

## Rules

- A reader who cannot run Python or open Word gets `geoarg report <case> --format html`: one self-contained page, bound by `attest` like any other deliverable.


- Every condition and every defeat condition carries a test. A condition without a test is rhetoric, and the engine will not let a condition count as satisfied without a passed test.
- `unknown` is a legal state. The contract reports unknowns; it does not fill them with confidence.
- A transcribed quote carries a `source_locator`, and `geoarg ground` decides whether it stays accepted. If the quote is not found, the record stays as written; `check` and `commit` fail with `not-found` until the quote or the record is fixed.
- An attested deliverable is a claim about bytes: `attest` binds the report/cards and commentary to the committed record. If you edit a deliverable after attesting, re-run `attest`; otherwise `verify` reports `deliverable changed since attestation`.
- `anchor` writes a checkpoint, but custody is yours: copy `anchor.json` outside the repository (or hand it to a timestamp service) before telling a reader the ledger head is anchored.
- Grounding is not verification of meaning. A grounded quote can still be cited for the wrong claim; that is the audit's problem, not the gate's.
- Cite the record you read. Evidence refs resolve to entries in `evidence.yaml` with a source, not to memory.
- One claim per contract. Two claims in one file hide the shared premises that the audit needs to see. One claim also means one declared field, if any: set it per argument, not per paper.
- When a premise rests on another argument, link it as `derived` with an `argument_ref` and register the target in the nearest `workspace.yaml` (or a relative/sibling case path); run `geoarg workspace <dir>` before `commit`. Do not copy the conclusion.
- Keep the scope small enough that one test can address it.

- A package you hand to someone else is a claim about bytes: `geoarg package <case> --out <dir>` folds the contract, trust-chain sidecars and bound deliverables into one directory with a SHA-256 manifest; the reader can run `geoarg verify-package <dir>` without trusting your machine.

## Field reference and case

- `references/contract-fields.md` holds the required fields and allowed values for all three files. Read it the first time you fill a contract.
- `examples/south-atlantic` is a worked case (plate reconstruction). Copy its shape, not its content.
