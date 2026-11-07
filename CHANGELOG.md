# Changelog

## 1.12.1 - publication pass

- **Draft placeholder gate.** Contracts produced by `geoarg new` / `geoarg adopt`
  are valid YAML with `TODO` placeholders. `check` now reports each placeholder
  as a problem in the strict profile (and as a warning in `--profile draft`), and
  `commit` refuses a contract that still contains them. A scaffold can no longer
  be committed as if it were a finished argument.
- **Committed demo trust chain.** `examples/demo-trust-chain` now ships a committed
  record, ledger, attestation, anchor and `report.md`, so a fresh clone can run
  `geoarg verify examples/demo-trust-chain` successfully.
- **CI actually runnable.** The workflow installs `setuptools`/`wheel`, builds the
  wheel without `--no-build-isolation`, installs it through Python instead of a
  shell glob, tests Python 3.11 and 3.12 on Linux and Windows, and verifies the
  demo case.
- **Publication metadata and docs.** `CITATION.cff`, `CONTRIBUTING.md`,
  `SECURITY.md`, issue templates, `authors`/`keywords`/`classifiers` in
  `pyproject.toml`, a runnable README quickstart with expected output, fixed
  trust-layer list numbering, eight (not seven) schemas, and an English
  "Install as a project" section.
- `geoarg doctor` no longer suggests the nonexistent `geoarg[report]` extra.

No engine-digest change in this release; committed cases remain valid.

## 1.12.0 - workspace cache, fast mode, lazy PyYAML

- `geoarg workspace` now loads each case once and shares the loaded cases while
  resolving argument chains and judging; measured on `examples/` 534 ms -> ~66 ms,
  and on a 16-case workspace 808 ms -> ~235 ms.
- `geoarg workspace --no-judge` is a fast structural scan: it loads and validates
  every contract but skips verdicts, chain resolution and committed-record drift.
- The chain problem list is derived from the already resolved chain instead of
  resolving it a second time per case.
- PyYAML is now imported lazily in `contract.py` (via a proxy) so commands that
  never touch a contract keep a fast startup: `geoarg --version` ~182 ms -> ~120 ms.
- Chain resolution is still recursive and cached per workspace scan; the
  engine digest changed, so the five registered cases were re-committed,
  re-attested and re-anchored at 1.12.0.

## 1.11.0

Performance and structure pass, no behavior change:

- CLI startup is lazy: the parser and shared helpers moved to `cli_parser.py` and
  `cli_common.py`, and every command handler imports its engine modules inside
  the handler. `geoarg --version` dropped from ~237-338 ms to ~182-208 ms in the
  local measurement (warm/cold), with no command behavior change.
- `figures`, `advise` and `impact` reuse the `Case` already loaded for contract
  validation instead of loading the same case twice.
- The ledger is parsed once per append: `append_ledger` now reads, parses and
  rewrites the file in one pass instead of reading it twice.
- `audit.verify` already read the ledger once; this pass keeps that invariant and
  documents it.

Tests: 272 OK (skipped=1).

## 1.10.1 - 2026-11-06

- Fix: `impact` (single case and `--workspace`) validates the contract before computing decision values, refusing invalid contracts with exit 2.
- Fix: `figures` and `advise` refuse invalid contracts with the same clean `PROBLEM:` output instead of rendering them.
- Fix: `impact --assume` validates ids and values; unknown ids were silently ignored before.
- Tests: 4 new regression tests.

Version numbers follow semantic versioning. A major bump changes a committed
record's compatibility: records committed by an older major version should be
migrated and re-committed before they are trusted.

## 1.10.0

- `defeaters[]` and `entailments[]` accept an optional `counter_evidence` list of evidence ids, so real
  counter-evidence can be attached to the condition it defeats instead of floating unreferenced.
- `independence` reports a `counter` block (ids, count, n_eff, families) for those records without counting
  them as support; `impact` marks them `counter: true` in leave-one-out ablation; `report` gains a
  counter-evidence column; `contract.validate` rejects unknown or duplicate ids.
- Contract schema version is now `geoarg/0.7` (migrate rewrites the schema_version line); `judge` reports
  the field and `RULE_VERSION` is `geoarg/0.7`. All examples and the five real cases were migrated and
  re-signed (commit -> attest -> anchor) at 1.10.0.

## 1.9.0

- Optional citation checks outside the trust chain: `geoarg sources <case>` (offline quote/source audit, `--require-quote` / `--require-source`) and `geoarg references <case>` (DOI/PMCID/PMID/arXiv verification via Crossref and Europe PMC, cached `.geoarg/references.json` snapshot, `--offline`, `--require-verified`).
- `check` / `commit` / `verify` are unchanged and never touch the network; the new layer is advisory only.
- New module `scripts/geoarg/references.py`, CLI commands, 13 tests, `docs/references.md`, README sections.
- Engine digest unchanged, so existing commits remain valid.

## 1.8.0

Feature release: deterministic SVG argument figures. Presentation only; no engine or schema changes, so committed records do not need re-commit.

- New `geoarg figures <case>`: four deterministic SVG figures - argument status (reason buckets per item kind), independence stress (n_eff against an assumed pairwise rho), decision value (leave-one-out evidence classes plus test power against cost), and evidence coverage against detectability. Output defaults to `<case>/figures`, with `--out`, `--lang`, `--json`; `figures.json` records every file's byte count and SHA-256.
- `report --format html` now embeds `<case>/figures/*.svg` inline (or a `--figures <dir>` override) and keeps the page a single self-contained file; `package --include-figures` copies the figures into `files/figures/` and records them in the manifest.
- New `figstyle.py` (verdict/reason/evidence palettes, WCAG contrast, grayscale-conflict check, landed 88/180 mm widths, minimum 6 pt landed type) and `figsvg.py` (a small deterministic millimetre-unit SVG canvas); no new third-party dependency.
- Visual rules adapted from nature-figure-craft (code MIT, docs CC BY 4.0), with no code or assets copied; figures are not part of `engine_digest`, a verdict, or a trust-chain check.
- Docs: `docs/figures.md`; README (Chinese and English) gained the command row and a 1.8 section; 11 new tests cover determinism, landed widths, HTML embedding, CLI behaviour, and the palette/font rules.

## 1.7.2

Patch release: engine fixes found by the YDIH real-world pilot. Committed records must be re-committed (engine digest changed).

- Domain packs can now actually extend `profiles`: `contract.validate` bound the built-in profile set instead of the pack-widened one, so a valid pack that added a profile still failed validation.
- `geoarg workspace` now prints a "Committed-record drift" table for every committed case; previously the section always said "No case carries a committed record" and only leaked verify problems into the Problems list.
- The shipped `argument.schema.json` no longer rejects valid pack-extended profiles or a `failed` entailment status; it stays a shape check while `contract.validate` remains authoritative.
- New regression tests: `scripts/tests/test_domain_extensions.py` (pack profile widening, pack digest changes, workspace drift rows, schema acceptance).

## 1.7.1

Patch release: content cleanup, no engine or schema changes. Committed records do not need re-commit.

- Fixed a UTF-8 BOM in `examples/domain-packs/geochronology/README.md`.
- README (zh/en): command tables now include `install-skills` and `doctor`; directory trees list `examples/domain-demo/` and `examples/domain-packs/`; corrected the stale "three fixtures" sentence about `geoarg workspace examples` (it now lists six cases and one resolved chain); English schema count corrected to eight.
- Filled the `examples/domain-packs/geochronology/age-bracket` scaffold into a complete worked example.
- Removed the no-op `geoarg ground --strict` alias (failing on ungrounded quotes is the default; pass `--allow-partial` to inspect).
- Removed a few unused private helpers and imports outside the engine digest; `requirements.txt` now says the canonical dependency list is `pyproject.toml`.

## 1.7.0

- New `geoarg package <case> --out <dir>`: a portable evidence package that folds the contract, the trust-chain sidecars, the attested deliverables, a generated self-contained HTML report, a SHA-256 manifest and minimal RO-Crate 1.1 metadata into one directory. `--include-source` also copies the grounded source document. The package remains a usable case directory (`check`, `verify`).
- New `geoarg verify-package <dir>`: recomputes every package digest, reloads and validates the packaged contract, recomputes the verdict, and checks the record, ledger self-hash chain, attestation, anchor and grounding cross-references; exits non-zero on any mismatch.
- Tests: `scripts/tests/test_package.py` covers the round trip, edited deliverables, edited ledger, packaging without attestation, and the CLI.
- Docs: README/README.en command rows and sections, contract-fields package table, register/audit skill rules for handing off a package.

## 1.6.0

- Domain packs carry field knowledge: `default_profile`, bundled argument patterns
  (`patterns_dir`), `test_suggestions`, `evidence_families` and `grounding`. The pack
  digest covers them, so `verify` reports `domain pack changed since commit` after an edit.
- `geoarg advise <case>` prints an author checklist from the nearest pack: missing suggested
  test methods, missing expected evidence families, the default profile and grounding hints.
  It changes no verdict and commits nothing.
- `geoarg patterns [case]` now includes pack-provided patterns; `geoarg new` discovers the
  nearest pack from the target path and prefers its patterns; `check --advise` prints the
  same suggestions as warnings.
- `domain.schema.json` documents the new optional fields; three example packs ship under
  `examples/domain-packs/{geochronology,stratigraphy,tectonics}` with a scaffolded sample case.

## 1.5.0

- Domain packs: optional `domain.yaml` beside a case widens the extensible enums
  (domains, profiles, claim kinds, method types, entailment kinds, cp types,
  defeater types, evidence kinds, verification levels, independence classes,
  gap kinds) for that case and its children; nearest pack wins; the new
  `geoarg domains [case]` command lists the effective values.
- The engine digest covers `domains.py`, and `commit` records the pack digest;
  `verify` reports `domain pack changed since commit` after an edit.
- New `scripts/geoarg/_schema/domain.schema.json`; the extensible enum fields in
  the other schemas are shape checks while `contract.validate` stays authoritative.
- New `geoarg edit <case>` local form editor (127.0.0.1, token protected, atomic
  save, validation feedback) for claim, inference, premises, conditions,
  defeaters, entailments, evidence and tests.
- New `examples/domain-demo`: a Quaternary tephra case that uses a local pack.

## 1.4.0

- HTML 报告：`geoarg report <case> --format html` 生成单文件、内嵌样式、可折叠、打印友好的 `report.html`；`geoarg workspace <dir> --format html` 生成工作区页面。
- `attest` 默认绑定集加入 `report.html` / `report.*.html`；HTML 与 Markdown/Word 同源渲染，不改判决、不加校验，作者文本按 HTML 转义。
- 测试与文档：新增 HTML 渲染测试；README/README.en 增加 HTML 报告一节。

## 1.3.0

- 上手层：`geoarg adopt`（Markdown 提纲转草稿案例，不确定的值一律标 TODO）、`geoarg patterns` 与 `geoarg new --pattern`（随包三种论证骨架）、`check --profile draft`（完整性缺口降为警告，引用与枚举仍是错误）、`check --explain`（每条问题一句修复提示，并扫描剩余 TODO）。
- 决策价值：`geoarg impact`（留一法消融、`--assume` 假设、`--add-evidence` 待采证据、剩余阻塞、独立性变化、`--workspace` 区分能力、`--lang/--out/--json`）。
- 包与文档：`_patterns/*.yaml` 进入 wheel；README/README.en 增加"降低上手成本"与"决策价值"两节；`contract-fields.md` 增加 impact 字段；技能说明补 `adopt`/`new` 与 `impact` 用法。
- 兼容性：接口只增不改；1.2 的案例、台账、锚点与交付物继续可用，无需 migrate。

## 1.2.0

Trust-layer hardening after an independent audit.

- Ledger 0.3: every entry carries a `sha256` over its body, so an edited entry is
  reported instead of being re-rooted through `prev`; legacy 0.1/0.2 lines are
  still read via their `record_sha256`.
- Missing sidecars are reported: if the ledger records an `anchor` or
  `attestation` entry and the local file was deleted, `verify` fails instead of
  silently passing; a non-file path is reported explicitly.
- `verify --anchor FILE` checks a checkpoint kept outside the repository
  (edited content, different record, foreign ledger head, checkpoint newer than
  the ledger).
- Re-running `attest` without `--judgment-file` keeps the previously bound
  judgment entries and re-hashes them.
- `geoarg schema <name> --validate FILE` validates one instance; schemas now
  require the same fields as `contract.validate` (`gaps`, claim `scope`,
  condition/defeater/entailment `test_ref`, anchor `engine_sha256`) and accept
  evidence/test records that declare `claim_id`.
- Default attestation binding includes bare `card.md`/`card.docx`; `check` is
  documented as the source-swap check (verify compares the stored digest).
- Ledger lines written before 1.2 (schema 0.1/0.2) carry no self-hash, so
  editing their `record_sha256` breaks the next line's `prev`, but edits to
  their other fields cannot be detected; entries appended by 1.2+ are fully
  verifiable. Re-committing appends verifiable entries but does not repair old
  lines.
- Wheel rebuilt from source (the 1.1.0 wheel was stale); docs and contract
  reference corrected for ledger 0.3, anchor `engine_sha256`, and
  `verify --anchor`.

## 1.1.0

Small hardening release on top of the trust layer.

- `geoarg schema <name> --validate <file>` validates one instance document
  directly (JSON or YAML), exits 0 valid, 1 invalid, 2 error.
- `geoarg verify <case> --anchor <file>` reads a checkpoint copy kept outside
  the repository and checks its digest, record pointer and ledger head.
- An unreadable or corrupt `attestation.json` is now reported by `verify`
  instead of being silently ignored.
- `geoarg ledger` shows legacy ledger 0.1 entries via their `committed_at`,
  with `-` for missing fields instead of `None`.
- New `examples/workspace-demo`: two linked arguments plus a `workspace.yaml`,
  demonstrating derived-premise resolution and `geoarg workspace`.
- Schemas no longer require an `arg.` prefix for `argument_ref` or
  `dependencies.depends_on`; `contract.validate` remains authoritative and
  docs already use ids such as `overlying-strata`.

## 1.0.0

Trust layer and multi-format grounding.

- `geoarg attest <case>` binds report and card deliverables plus authored
  judgment text to the committed record by SHA-256, writes
  `.geoarg/attestation.json`, and appends a ledger entry. `verify` reports
  `deliverable changed since attestation` and `engine changed since
  attestation`.
- `geoarg anchor <case>` writes a checkpoint of the ledger head; `verify`
  reports edited anchors, anchors pointing at a different record, and anchors
  missing from the ledger.
- Ledger 0.2 records three entry kinds (`commit`, `attestation`, `anchor`) with
  `prev` linking (superseded by ledger 0.3 in 1.2.0); writes to the registry use atomic replace and a per-case
  lock, so concurrent readers do not see half-written records.
- JSON Schemas now ship inside the package (`scripts/geoarg/_schema/`) and are
  exposed with `geoarg schema`. Schemas are a documentation and machine-check
  second opinion; `contract.validate` remains authoritative.
- Grounding accepts DOCX, HTML, Markdown, and plain text in addition to PDF.
  Page numbers are meaningful for PDF only. The ledger records source path,
  format, and digest; `check` reports `source document changed since grounding`, while `verify` compares the stored ledger digest without re-reading the source.
- `geoarg independence` adds an assumption stress table: `n_eff` under assumed
  pairwise correlations of 0, 0.25, 0.5, 0.75, and 1.0.
- Windows consoles are switched to UTF-8 output; docs cover the trust model and
  the prior-art survey at `docs/prior-art.md`.
- Package is now 1.0.0 with an optional `schema` extra (`jsonschema`).

## 0.9.0

Argument chains and workspaces.

- New `chain.py`: derived premises point at another registered argument via
  `argument_ref`; `workspace.yaml` maps argument ids to case directories.
- `geoarg workspace <dir>` reports verdicts, resolved and broken chains,
  evidence shared across cases, evidence-id conflicts, and committed-record
  drift. It exits non-zero on problems and never changes a case.
- `commit` refuses unresolved references and cycles; the commit record carries
  a chain digest that `verify` recomputes.
- Reader output uses ordinary language for linked arguments.

## 0.8.0

Result binding and paper bundles.

- Tests may declare `result` and a `pass_rule` (`ge`, `le`, `between`,
  `within_ci`, `ratio`); computed statuses take precedence over declared ones.
- `geoarg bundle <dir>` aggregates required claims by the weakest verdict.
- `geoarg migrate` upgrades older schema versions.
- `.geoarg/ledger.jsonl` becomes an append-only history of commits.

## 0.7.1

Fix reader-layer wording: profile metadata no longer selects vocabulary, and
plain-language renderers stay out of the engine digest.

## 0.7.0

Plain-language reader layer. Reports and cards use the author's statements and
ordinary prose; machine state names stay in the registry and audit blocks.

## 0.6.0

Deliverables and profiles.

- `geoarg report` and `geoarg card` write Word files with an audit block that
  records input, rule, engine, and chain digests.
- Researcher and reviewer cards.
- Argument profile metadata (`general-geology`, `geochronology`,
  `planetary-geology`, `tectonics`).

## 0.5.0

Verdict binding and grounded quotes.

- Satisfied states need a passed gating test (`unbacked` is reported).
- `geoarg ground` checks transcription-level quotes against the source text
  layer and writes a grounding ledger.
- `geoarg verify` recomputes committed records and reports drift.
