# geo-argument-skills

**Turn a geological argument into a checkable contract: one claim, its premises, its defeat conditions, and the tests that could retract it.**

An LLM can write "multiple independent lines of evidence support this conclusion", but it will not tell you which conclusions must be withdrawn when the evidence changes. This repository takes that part out of the model: the model fills the contract, a deterministic engine computes the verdict.

## What is here

Two agent skills plus a small engine:

| Capability | Owner |
| --- | --- |
| Split a claim into premises, warrant, ceteris paribus conditions, defeaters, entailments | [geo-arg-register](skills/geology/geo-arg-register/SKILL.md) (model) |
| Compute the verdict (SUPPORTED / UNDETERMINED / UNTESTED / SUSPENDED / DEFEATED) | `geoarg` (script) |
| Compute the effective independent evidence count `n_eff` and flag pseudo-independence | `geoarg` (script) |
| List the outcomes that would retract the claim now | `geoarg` (script) |
| Write a recomputable, tamper-evident audit record | `geoarg` (script) |
| Check every transcription quote against the source PDF and report an acceptance rate | `geoarg` (script) |

The verdict is a lattice, not a score. `UNTESTED` and `UNDETERMINED` are legal and common; they are closer to geology than a confident number.

> **Status: research prototype.** The engine and trust chain are covered by automated tests (272); the method itself has not been empirically evaluated outside the bundled fixtures. The examples demonstrate contracts and the engine, not that the method works. Use it for self-checks, teaching and review support, not as an authoritative conclusion. Chinese: [README.md](README.md).

## Quickstart

Clone or download the repository and run these commands from its root.

```bash
python -m pip install -e ".[schema]"     # jsonschema enables `schema --validate`; optional
geoarg --version                         # expected: geoarg 1.12.2
geoarg check examples/south-atlantic     # expected: OK C1 (0 problem(s))
geoarg judge examples/south-atlantic     # expected: UNTESTED
geoarg independence examples/south-atlantic
geoarg hit-set examples/south-atlantic
geoarg workspace examples
geoarg workspace examples/workspace-demo
geoarg ground examples/paper-demo --source examples/paper-demo/paper.pdf
geoarg verify examples/demo-trust-chain   # expected: OK (a demo trust chain ships in the repo)
geoarg report examples/south-atlantic
geoarg card examples/south-atlantic --for reviewer --lang zh
geoarg schema --list
python -m unittest discover -s scripts/tests
```

No network. Only PyYAML, pypdf and python-docx are required.

## Install as a project

The engine and both skills ship as one package. After installing, copy the skill directories into your agent host:

```bash
pip install .
geoarg install-skills              # installs into existing ~/.dsh/skills, ~/.claude/skills, ./.dsh/skills, ./.claude/skills
geoarg install-skills --dest <dir>  # or an explicit directory (repeatable)
geoarg install-skills --check       # compare installed copies with the packaged ones
geoarg doctor                       # engine, dependencies and installed skills in one check
```

Both skills preflight with `geoarg --version`: stop if the engine is missing or older than 1.12. The wheel bundles the skills (`geoarg/_skills`), so pip installs do not need the repository directory.

## Commands

| Command | What it does |
| --- | --- |
| `geoarg check <case>` | structural and cross-reference validation; a satisfied state (`holds`, `refuted`, `passed`) needs a passed test or it is reported as `unbacked`; `--profile draft` downgrades completeness gaps to warnings, `--explain` adds one fix hint per problem and lists remaining TODOs |
| `geoarg judge <case>` | verdict and reason chain |
| `geoarg independence <case>` | `n_eff / n`, mean rho, independence warnings; counts accepted records only; also reports a sensitivity range (`stress`) as the assumed rho varies |
| `geoarg hit-set <case>` | single-event defeat paths ranked by power, then cost |
| `geoarg report <case>` | Word report by default (`<case>/report.docx`); `--format md` prints Markdown; `--format html` writes a single-file HTML page; `--lang zh` renders the report frame in Chinese; `--lang auto` uses the machine system language; `--brief` writes a one-page brief; `--judgment` / `--judgment-file` attach the model-authored commentary (also in the brief) |
| `geoarg card <case> --for <reader>` | conclusion page adapted to one reader: `researcher` gets the conclusion, the number of items still without test backing, next tests and gaps; `reviewer` also gets every reason, what would change the conclusion, evidence independence, the quote-check table and audit information. `--judgment` / `--judgment-file` attaches a model-authored commentary |
| `geoarg commit <case>` | atomically write the registry record (directory lock) with input, engine and chain digests, then append a `commit` entry to `.geoarg/ledger.jsonl`; refuses `unbacked` states or an unresolved argument chain |
| `geoarg verify <case>` | recompute and report drift: changed input, engine, verdict, a registry record that is not the latest commit, changed deliverables, or a changed anchor; `--anchor <file>` also checks a checkpoint copy kept outside the repository |
| `geoarg attest <case>` | bind the current deliverables (`report.*`, `card.*`) and judgment files, by content hash, to the committed record; writes `.geoarg/attestation.json` and appends an `attestation` ledger entry; `--include` narrows the file set, `--judgment-file` binds a commentary |
| `geoarg anchor <case>` | write `.geoarg/anchor.json`, a checkpoint of the record digest, ledger head, entry count, engine digest (engine_sha256) and time; copy that file outside the repository to state "the ledger head at this time" |
| `geoarg ledger <case>` | show ledger entries (kind, time, verdict, digest, link); `--json` |
| `geoarg schema [name] [--validate <file>]` | list the shipped JSON Schemas (argument/evidence/test/bundle/workspace/attestation/anchor/domain) or print one; `--list`, `--json`; validates an instance when `jsonschema` is installed, and `--validate <file>` checks one document directly |
| `geoarg ground <case> --source <paper>` | match every source quote against the source document (PDF, DOCX, HTML, Markdown, plain text), write a grounding ledger, report an acceptance rate; exits non-zero when a declared quote fails (`--allow-partial` only inspects a partial ledger); the legacy `--pdf` still works |
| `geoarg migrate <case\|dir>` | rewrite the `schema_version` line of the three case YAML files (or `bundle.yaml`) to the current schema, leaving every other byte alone; `--dry-run` reports without writing |
| `geoarg bundle <dir>` | read `bundle.yaml`, run `judge` per case, and take the weakest required claim as the paper's bundle conclusion; `--json`, `--out`, `--lang` |
| `geoarg workspace <dir>` | scan every case under `<dir>`: verdicts, argument chains, evidence shared across cases, evidence-id conflicts, drift in committed records; `--no-judge` is a fast structural scan that skips verdicts, chains and drift; exits non-zero when anything is wrong; `--json`, `--format html`, `--out`, `--lang` |
| `geoarg patterns` | list the shipped argument patterns (age bracket, sequence boundary, slip rate) and how to scaffold one with `geoarg new` |
| `geoarg new <dir> --pattern <name>` | write the three YAML drafts for a pattern (TODO placeholders); `--id` / `--title` / `--claim` override; refuses to overwrite an existing case (`--force`) |
| `geoarg adopt <notes.md> --out <dir>` | deterministically turn a Markdown outline (`Claim` / `Premises` / `Evidence` / `Tests` sections) into a draft case; every guessed value becomes a TODO |
| `geoarg impact <case>` | decision value: leave-one-out ablation of evidence/tests (decisive/backing/redundant/unused/untapped), `--assume` changes, `--add-evidence` prospective data, remaining blockers and the independence delta; `--workspace` applies the same prospective evidence to a whole workspace; `--json`, `--out`, `--lang` |
| `geoarg domains [case]` | list the built-in enums, the `domain.yaml` pack that applies to a case (including bundled patterns and field advice), and the merged effective values; `--lang`, `--json` |
| `geoarg advise <case>` | an author checklist from the nearest domain pack: which suggested test methods and evidence families are still missing, plus the default profile and grounding hints; changes no verdict and commits nothing; `--lang`, `--json` |
| `geoarg edit <case>` | serve the local form editor (127.0.0.1 only, token protected, atomic save, validation on save); `--host`, `--port`, `--no-browser` |
| `geoarg figures <case>` | write four deterministic SVG figures (argument status, independence, decision value, evidence coverage); default `<case>/figures`, with `--out`, `--lang`, `--json`; `report --format html` embeds that directory, `package --include-figures` carries it |
| `geoarg sources <case>` | optional: list which citations carry a quoted passage and grounding source; `--require-quote` / `--require-source` fail the check |
| `geoarg references <case>` | optional: verify DOI/PMCID/PMID/arXiv against Crossref / Europe PMC and write a `.geoarg/references.json` snapshot; `--offline` reads the cache only |
| `geoarg package <case> --out <dir>` | write a portable evidence package: folded contract, ledger/record/attestation/anchor/grounding sidecars, bound deliverables, self-contained `report.html`, SHA-256 manifest and minimal RO-Crate; `--include-source` also copies the source document |
| `geoarg install-skills` | copy the bundled skills into the existing skill directories (`~/.dsh/skills`, `~/.claude/skills`, `./.dsh/skills`, `./.claude/skills`); `--dest` picks a directory, `--check` only compares copies for drift |
| `geoarg doctor` | self-check the engine version, dependencies, JSON Schemas, bundled skills and installed copies |
| `geoarg verify-package <dir>` | recompute every digest in the package and check the record, ledger chain, attestation, anchor and grounding ledger; non-zero on problems |

- Re-running `commit` only replaces the record; if you already ran `attest` or `anchor`, re-run them in the order commit → attest → anchor before `verify` passes again.

## Trust layer (1.12.2)

Before 0.9, `verify` could only compare the case input, engine, verdict, and argument chain. It did not know whether the report handed to a reader came from this commit, and it could not tell whether the ledger had been replaced wholesale. 1.0 adds both:

1. **Deliverable binding.** After `commit`, run `geoarg attest <case> --judgment-file <text>`. The engine records the content hashes of `report.*`, `card.*`, and the judgment files, plus engine/rule versions and the runtime environment, in `.geoarg/attestation.json`, and appends an `attestation` ledger entry. Changing a report without re-attesting makes `verify` report `deliverable changed since attestation`; changing the engine without re-attesting reports `engine changed since attestation`.
2. **Anchor.** `geoarg anchor <case>` writes `anchor.json` with the current record digest, ledger head, entry count, engine digest (`engine_sha256`), and time. Copy that file outside the repository (email, paper supplement, institutional archive, timestamp service); `geoarg verify <case> --anchor <file>` then checks that the ledger head still matches it. Plain `verify` only checks the local sidecar against the ledger. Replacing the whole ledger no longer matches the copied checkpoint.
3. **Atomic writes and locking.** `commit`, `attest`, `anchor`, and the grounding ledger write a sibling temporary file and `os.replace` it, under a per-case directory lock, so half-written files and concurrent overwrites are avoided.
4. **Shipped schemas.** Eight JSON Schemas now ship inside the wheel (`geoarg/_schema/`); `geoarg schema` lists or prints them, and `--validate <file>` checks one document; `geoarg schema <name> --validate <file>` checks one document directly. Schemas are documentation and a second opinion; `contract.validate` remains authoritative.
5. **Multi-format grounding.** Besides PDF, a source document may be DOCX, HTML, Markdown, or plain text. Page numbers are meaningful only for PDF; other formats use page 1.

The four trust levels are: structurally consistent (`check`) → record reproducible (`commit` / `verify`) → deliverable traceable (`attest`) → ledger head declarable (`anchor`). Each level adds one checkable promise on top of the previous one; "this is true" beyond an anchor is outside this repository's scope. Design references are in [docs/prior-art.md](docs/prior-art.md).

`card` does not change the verdict: the researcher page and the reviewer page report the same verdict, `n_eff`, and grounding acceptance, and differ only in selection and order. The reader is asked once per session; the answer is presentation state, never contract data. Both pages quote the author's own statements in ordinary language; machine field values stay in the ledgers.

`profile` is optional metadata. An argument may declare its field in `argument.yaml` (`primary`, an optional `secondary` list, and a one-line `rationale`); when omitted the deliverable says the field was not declared. It only labels the field in the header: it selects no vocabulary and changes no verdict, `n_eff`, or acceptance rate. Deliverables quote the author's own statements in ordinary language and coin no terms; machine values such as `UNTESTED` appear only in the ledger's `verdict` field.

A card may open with a two to four sentence commentary paragraph (`--judgment` or `--judgment-file`). The engine supplies the numbers, the model writes the prose; the audit block records the paragraph's sha256 so prose and computation stay distinguishable. When absent, the card says "commentary: not provided"; the engine template does not write prose.

## Result binding

A test's `status` no longer has to be typed in. Give a test a `result` block and a `pass_rule`, and the engine computes `passed` / `failed` / `inconclusive` from the recorded value; the computed status wins over the typed one, and `judge` reports a mismatch and uses the computed value.

```yaml
- id: T1
  name: Main test
  checks: [P1]
  method: {type: statistical, description: ...}
  discriminating_power: high
  cost: 3
  result:
    value: 0.5
    uncertainty: {kind: ci95, low: 0.4, high: 0.6}
  pass_rule: {op: ge, value: 0.0}
```

`pass_rule` supports `ge`, `le`, `between`, `within_ci`, and `ratio`. `commit` records the computed statuses; editing `result` or `pass_rule` without re-committing makes `verify` report `computed test statuses changed`. Tests without a `result` block still use the typed `status`.

## Paper bundle

When one paper carries several claims, put them in one directory with a `bundle.yaml`:

```yaml
schema_version: geoarg/bundle/0.1
id: paper.2026
title: Paper title
claims:
  - case: claims/c1
  - case: claims/c2
    label: second claim
    required: false
```

`geoarg bundle <dir>` runs `judge` on each case and takes the weakest required claim as the bundle conclusion, ordered `SUPPORTED < UNDETERMINED < UNTESTED < SUSPENDED < DEFEATED`. Optional claims are listed but do not enter the aggregate. Missing or invalid cases become problems, never silent passes. A `case` path is relative to the bundle root; an absolute path is also accepted.

## Argument chains and workspaces

A premise can come from another argument. Mark it `derived` with `argument_ref` instead of copying the conclusion:

```yaml
- id: P4
  statement: overlying strata are no older than 3.2 Ga
  kind: derived
  argument_ref: overlying-strata
```

Resolution order: an argument id declared in the nearest `workspace.yaml` → a relative or absolute case path → a sibling directory. The workspace file looks like this:

```yaml
schema_version: geoarg/workspace/0.1
id: project.example
arguments:
  - id: basement-age
    case: claims/basement-age
  - id: overlying-strata
    case: claims/overlying-strata
```

`judge` finds the nearest `workspace.yaml` above the case directory and maps the target verdict onto the premise: target supported → premise satisfied; target SUSPENDED, UNTESTED or UNDETERMINED → premise pending; target DEFEATED → hard problem; an unresolved reference, a cycle, or a broken target case becomes a workspace problem and `commit` refuses to run. `commit` records the chain digest; `verify` recomputes it and reports `argument chain changed since commit`. Reports and cards render a derived premise as "the conclusion comes from another argument (…)", never as an internal state name.

## Global evidence registry and drift

`geoarg workspace <dir>` scans every case directory under `<dir>` and prints:

- every argument's directory, claim id, field and verdict;
- every argument chain: which premise, which argument it references, whether the reference resolves, and the target's verdict;
- evidence ids shared across cases; when the same id carries different content in different cases it is listed as an evidence conflict and counts as a problem;
- drift for committed records: cases with `.geoarg/registry/` are re-verified, and changed inputs, engine, verdict or argument chain are reported;
- problems and the workspace conclusion; the command exits non-zero when anything is wrong.

It changes no case and recomputes no bundle conclusion: it checks whether a set of arguments is internally consistent, not what any one argument concludes.

## Append-only ledger

Besides writing `.geoarg/registry/<claim>.json` atomically, `commit` appends a line to `.geoarg/ledger.jsonl`: `{schema_version: geoarg/ledger/0.3, kind: commit, claim_id, created_at, record_sha256, verdict, rule_version, engine_sha256, prev, sha256}`, where `sha256` covers the entry body and `prev` points at the previous line's `sha256`. `attest` and `anchor` append `kind: attestation` and `kind: anchor` entries; `verify` checks the chain links, that the latest `commit` is the current registry record, and that any `attestation` or `anchor` still matches. The ledger still lives inside the case directory, so it proves "commit history was not quietly rewritten", not "no forged commit exists"; use `anchor` to carry the ledger head outside.

## Grounding gate

The most common LLM error in geology is not bad inference; it is quoting a sentence that the source never contains. The gate turns that check into a string match:

1. Transcription-level evidence carries a `source_locator`: page plus the sentence as it appears in the source.
2. `geoarg ground --source` opens the source document (PDF, DOCX, HTML, Markdown, plain text), normalizes the text, and searches the whole document (a quote that spans a page break still grounds). Page numbers are meaningful only for PDF; every quote in another format is recorded on page 1.
3. Four statuses: `grounded` (found on the declared page), `page-mismatch` (found elsewhere), `not-found` (fabricated), `not-groundable` (no text layer, or no readable text in the source). No OCR: a scanned PDF must be converted to text first.
4. `check` and `commit` reject an accepted transcription record whose quote is not grounded; `ground` exits non-zero when any declared quote fails; the ledger digest enters the registry, so editing a quote shows up as drift in `verify`. The ledger also records the source format and path; swapping the source file makes `check` report `source document changed since grounding`; `verify` compares the stored grounding-ledger digest instead of re-reading the source.

The acceptance rate is `grounded / drafted`. It is a different dimension from `n_eff`: one counts independent lines, the other counts quotes that exist. The gate proves the sentence is in the source. It does not prove the sentence supports the premise; that is the audit's job.

## Design principles

1. Determinism in the script, judgement in the model.
2. The contract is the interface: three YAML files, documented in [contract-fields.md](skills/geology/geo-arg-register/references/contract-fields.md).
3. Verdicts are recomputable: `commit` records input, engine, and chain digests; `attest` binds the deliverables produced from that record; `verify` reports drift at every level. The record, ledger, and anchor can be rewritten, so the repository proves the audit is recomputable, not that it is unforgeable.
4. Satisfied states need test backing: `cp` `holds`, defeater `refuted`, and entailment `passed` count only when a referenced test has passed. Otherwise the item is `unbacked`, the verdict stays at `UNDETERMINED`, and `commit` refuses it.
5. `unknown` is a legal state; the contract reports it instead of filling it with confidence.
6. Gaps are first-class: what the contract cannot express is registered, not hidden.
7. Quotes must land: transcription-level evidence carries a source locator and passes the grounding gate. An ungrounded quote may not stay `accepted`.
8. Bind a result when you can: when a test result fits a registered `pass_rule`, the engine computes its status instead of trusting a typed field; keep the typed status for results that cannot be recorded as a value.
9. A paper's conclusion is its weakest claim: the bundle aggregate is a conservative lower bound, and optional claims do not enter it.
10. Deliverables are bindable and ledger heads can leave the repository: `attest` ties reports/cards/commentary to the committed record, and `anchor` writes a checkpoint a reader can keep elsewhere; the repository supplies the bytes to check, it does not pretend to be a timestamp authority.

## Layout

```
skills/geology/            two skills
docs/geology/              Chinese usage pages
docs/prior-art.md          prior mechanisms the trust layer borrows from (English)
scripts/geoarg/            deterministic engine
  _schema/                 shipped JSON Schemas (8)
  _skills/                 shipped copies of the skills (wheel build artifact; absent from the checkout)
scripts/tests/             unit tests
examples/south-atlantic/   teaching fixture (placeholder citations)
examples/paper-demo/       synthetic PDF with a committed grounding ledger
examples/workspace-demo/   linked arguments and workspace index demo
examples/domain-demo/      one case widened by a domain pack
examples/domain-packs/     three reusable packs (geochronology/stratigraphy/tectonics)
```

`examples/workspace-demo` links two arguments (`basement-age` and `cover-age`) with a `workspace.yaml`; `cover-age` has a derived premise pointing at `basement-age`. Expected: `geoarg judge examples/workspace-demo/cover-age` is `UNTESTED` and the derived premise reads as a linked argument that is not tested; `geoarg workspace examples/workspace-demo` shows one resolved chain and a structurally consistent conclusion. Neither case is committed, so there is no registry record or anchor.

## Lowering the onboarding cost (1.3)

Three paths, pick one:

1. You already have a paper or a draft: `geoarg adopt notes.md --out my-case` turns an outline into a checkable draft. The Markdown needs four sections (`Claim`, `Premises`, `Evidence`, `Tests`) with bullets like `- P1: ...`; evidence bullets may carry `source`, `page` and `quote`.
2. You only have a question: `geoarg patterns` lists the shipped argument patterns; `geoarg new my-case --pattern geochronology-age-bracket` writes a skeleton.
3. Once it exists: `geoarg check my-case --profile draft --explain`. The draft profile only downgrades unfinished fields (scope, audit, coverage) to warnings; reference and enum errors stay errors. `--explain` adds one fix hint per problem. Run the strict profile after filling the TODOs.

Every `TODO` in a draft is a question for the author, not a value guessed by the engine. `adopt` does not infer evidence (it writes placeholder records when none is given); `new` does not rewrite the pattern's conclusion, it only substitutes id, title, claim and date.

## Decision value (1.3)

`geoarg impact <case>` answers "which data actually carries the conclusion, and what would change it". It estimates no probability and scores no plausibility:

- Ablation: drop one evidence record or one test at a time and recompute; classify the record as `decisive` (the verdict moves), `backing` (the verdict stays, the reasons move), `redundant` (nothing moves) or `untapped` (the test is not tied to any declared state).
- `--assume test:T1=passed --assume cp:CP1=holds`: simulate "the data exists and the interpretation holds". Give both the test outcome and the declared state, because the engine only counts a state when a test backs it.
- `--add-evidence new.yaml`: append prospective evidence to a copy and see whether the verdict or independence moves (no grounding ledger is required).
- The report also lists what remains (hard/soft/pending, unbacked states, gating tests not yet run) and the independence delta.
- `--workspace <dir>` applies the same prospective evidence to every case in a workspace, showing which claims one measurement would touch.
- Languages: `--lang en|zh`; `--out` writes Markdown; `--json` emits machine-readable fields.

Limits: impact only recomputes the engine's existing rules; declared states remain interpreted judgments; ablation moves one record at a time and does not measure interactions; it does not check whether the underlying data is reliable.

## HTML reports (1.4)

`geoarg report <case> --format html` writes a single `report.html`: inline styles, no external assets, openable in a browser or printable to PDF; every section collapses (native `<details>`), and the evidence, quotes and audit information sit on the same page. `geoarg workspace <dir> --format html` renders the same style of workspace page (multiple cases, argument chains, shared evidence, conflicts, drift).

HTML is a rendering like Markdown and Word: it changes no verdict and adds no checks. `attest` binds `report.html` by default, so the page you hand over sits inside the same commit → attest → anchor trust chain. The renderer HTML-escapes authored text and executes no script from the page.

## Domain packs, field advice and the form editor (1.6)

A `domain.yaml` lets one engine serve different geological subfields: place a pack beside a case (or in one of its parent directories) to widen 11 enum families for that case (domain, profile, claim kind, method type, entailment kind, cp type, defeater type, evidence kind, verification level, independence class, gap kind). The nearest pack wins; built-in values always remain, and a pack can only add values, never change semantics. `geoarg domains <case>` prints the effective values; `geoarg check` validates with the widened enums while schemas only check shape.

```yaml
schema_version: geoarg/domain/0.1
name: quaternary
enums:
  domains: [quaternary-geology]
  claim_kinds: [age-model]
  method_types: [tephrochronology]
```

`commit` records the pack digest; after editing the pack, `verify` reports `domain pack changed since commit`. See `examples/domain-demo` for a complete example.

From 1.6 a pack can also carry field knowledge: `default_profile` (with a rationale), `patterns_dir` (bundled argument patterns,
default `patterns/`), `test_suggestions` (per claim kind, with reasons), `evidence_families` (expected families and independence class)
and `grounding` (formats and notes). These fields are part of the pack digest, so `verify` reports an edit too. `geoarg patterns <case>`
lists the pack's patterns; `geoarg new` prefers them when the target sits inside the pack; `geoarg advise <case>` prints the checklist.
Three ready-to-use packs live under `examples/domain-packs/`.

`geoarg edit <case>` serves a local form editor on 127.0.0.1 (no external dependencies, token protected, atomic saves, validation on save) for the claim, inference, premises, conditions, defeaters, entailments, evidence and tests. It adds no trust level and does not lower the commit bar.

## Portable evidence packages (1.7)

`geoarg package <case> --out <dir>` folds a committed, attested case into a directory that can leave the machine:

- `argument.yaml` / `evidence.yaml` / `test.yaml` plus `.geoarg/`: the record, ledger, attestation, anchor and grounding ledger;
- the attested deliverables and judgment text, plus a self-contained `report.html` generated in the requested language;
- `manifest.json`: a SHA-256 for every file, the record/ledger-head/anchor/attestation digests, the engine and rule versions;
- `ro-crate-metadata.json`: minimal RO-Crate 1.1 metadata for repository archiving;
- `README.md`: what the package is, how to check it, and where its boundaries are.

The package is still a usable case directory for the same engine version: `geoarg check .` and `geoarg verify .` run on it directly. `geoarg verify-package <dir>` trusts nothing in the manifest: it recomputes every digest, reloads the contract, validates it and recomputes the verdict, and checks the record digest, the ledger self-hash chain, the attestation and anchor cross-references and the bytes of the bound deliverables; any mismatch exits non-zero and lists the problems.

Boundaries: digests prove byte identity, not that the data are true; the package does not replace an external timestamp or signature service; reading it with a different engine version produces a version warning and the verdict is recomputed from the packaged contract.

## Figures (1.8)

`geoarg figures <case>` writes four SVGs: argument status (how many premises, conditions, defeaters and entailments are blocking, weakening, pending or satisfied), independence stress (reported n_eff against an assumed pairwise rho), decision value (leave-one-out evidence classes and test power against cost), and evidence coverage against detectability. Figures are drawn at the landed 88 mm or 180 mm width, keep a minimum 6 pt landed type size, and use a semantic palette with a grayscale check.

`geoarg report <case> --format html` embeds `<case>/figures/*.svg` inline and keeps the page a single self-contained file; `geoarg package <case> --include-figures` copies the figures into `files/figures/` and records them in the manifest. Figures only render interpreted states: they do not enter `engine_digest`, change a verdict, or replace evidence. The rules and trade-offs are in `docs/figures.md`; some visual rules are adapted from [nature-figure-craft](https://github.com/Alto-R/nature-figure-craft) (code MIT, docs CC BY 4.0), with no code copied and no plotting dependency added.

## Citation checks (optional, 1.10)

Citation checks are an optional layer outside the trust chain. `check`, `commit` and `verify` do not contact the network and do not require it.

- `geoarg sources <case>` lists, offline, which citations carry a quoted passage and whether the case has a grounding source; `--require-quote` / `--require-source` fail the check.
- `geoarg references <case>` extracts DOI/PMCID/PMID/arXiv identifiers, queries Crossref and Europe PMC for existence plus year/first-author agreement, and reports retractions where providers expose them. The result is written to `.geoarg/references.json`; `--offline` reads the cache only, `--require-verified` passes only when everything is verified.

Statuses are verified / mismatch / not-found / retracted / unverifiable / no-identifier. It checks that a reference exists and its metadata agrees; it does not check that the paper supports the claim. Books, reports and regional journals often end up unverifiable. See `docs/references.md`.

This layer is an admission hint for authors and reviewers: it changes no verdict and is not a proof that a citation is true.

## Counter-evidence binding (1.10)

A `defeater` or an `entailment` may carry a `counter_evidence` list of evidence ids:

```yaml
inference:
  defeaters:
    - id: D1
      type: undercutting
      severity: fatal
      state: established
      test_ref: T1
      counter_evidence: [ev.surovell.resampling]
```

The field changes reporting and decision value, not the verdict rules:

- `independence` adds a `counter` block (count, n_eff, families) measuring how independent the counter lines are;
- `impact` ablation marks cited records `counter: true` and no longer labels them `unused`;
- `report` adds a "Counter-evidence records" column to the counter-evidence and prediction tables;
- `geoarg check` validates the ids (existing and unique); the field is optional, and leaving it out behaves exactly as in 1.9.

## Status and limits (v1.12.2)

- Does not verify the truth of a claim, only the structure, test status, and quote grounding of the argument.
- Contracts cost effort; that is the price of a checkable argument.
- The verdict is a self-consistent ledger, not automatic evidence. A satisfied state needs a passed backing test, but the test `status` is still typed into the contract: the engine does not read the data or rerun the test. It catches "claims built on no test", not "test ran and reported a wrong result".
- `hit-set` enumerates single-event defeat paths only.
- `n_eff` rho values are priors, not measurements; report them with the result.
- The grounding gate covers accepted transcription-level records only. It compares strings (no OCR, no layout or measurement/interpretation checks); a normalized miss is `not-found`. DOCX reads paragraphs and table text, HTML reads visible text nodes; a scanned PDF or image has no text layer and is `not-groundable`.
- Argument chains resolve only through the nearest `workspace.yaml`, a relative or absolute case path, or a sibling directory. No repository-wide or network search; an unresolved reference or a cycle is refused at `commit` instead of producing an optimistic verdict.
- Chains inherit the target's state one step only: the target verdict maps onto the premise, and evidence independence is not recomputed. When two arguments reuse an evidence id, `workspace` reports it as a conflict only if the content differs; it does not automatically reweight either argument.
- Workspace drift covers cases with a committed record only; uncommitted cases show structural problems. The evidence registry compares content hashes for the same id and does not prove common provenance.
- The registry record, ledger, and anchor can all be rewritten: `verify` detects post-commit drift, and re-running `commit` clears it. The `attest` and `anchor` commands supply checkable bindings and bytes to copy out of the repository; no timestamp service, transparency log, or signing identity is built in, and custody of the anchor file is the user's job.
- Deliverable binding covers content hashes only. `attest` proves "these files came from this commit and have not changed since"; it does not prove the commentary is faithful, nor that the same report was not copied elsewhere. The default set is `report.*` and `card.*`; other files need explicit `--include`.
- The eight shipped schemas are a second opinion: they validate document shape, while `contract.validate` remains authoritative; when they disagree, the engine wins.
- The append-only ledger resists local edits only: the whole `.geoarg/ledger.jsonl` can still be replaced; lines written before 1.2 have no per-entry `sha256`: editing their `record_sha256` breaks the next line's `prev`, but edits to their other fields are not detected (1.2+ lines are fully checked); compare the ledger with an anchor kept elsewhere using `geoarg verify <case> --anchor <file>` (plain `verify` checks local sidecars only).
- Result binding covers results that fit a registered rule. Binary outcomes, interval estimates, and relative changes can be computed; tests involving model selection, multiple-comparison correction, or subjective ratings still need a typed `status`. The engine performs no statistical inference.
- `migrate` rewrites only the schema line. Legacy string `result.value` fields and missing `pass_rule`s must be fixed by hand; `check` points at them after migration.
- A bundle conclusion is the weakest claim, a conservative bound, not a probability aggregate and not a substitute for editorial judgement about a claim's importance.
- The reader layer coins no terms: cards and the report quote the author's own statements in ordinary language; `profile` only labels the field and never changes wording, verdict, `n_eff`, or acceptance rate. Machine values (`verdict`, `n_eff`, `status`) stay in the ledgers and the audit block.
- The commentary is written by the model, not by the engine. The engine supplies numbers and reason items; the audit block records the paragraph digest, and a reader still judges whether the prose is faithful.
- The full research program (corpus, expert ratings, historical backtest) is outside this repository.

Skill layout, `SKILL.md` conventions, `docs/` page structure, and `plugin.json` follow [mattpocock/skills](https://github.com/mattpocock/skills). Content and engine are original.

- The draft profile is a writing-time lint: it does not lower the commit bar; `commit` still uses the strict profile.

## License

MIT
