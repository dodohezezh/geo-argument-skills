# Changelog

Version numbers follow semantic versioning. A major bump changes a committed
record's compatibility: records committed by an older major version should be
migrated and re-committed before they are trusted.

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
