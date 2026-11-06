# Contract field reference

Three files per case directory: `argument.yaml`, `evidence.yaml`, `test.yaml`. `schema_version` is `geoarg/0.7` in all three. The same documents are described by the JSON Schemas shipped in `scripts/geoarg/_schema/` (also inside the wheel, reachable with `geoarg schema`); `validate` in `contract.py` is authoritative and enforces the required fields, enums and unique ids listed below.

## argument.yaml

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | `geoarg/0.7` |
| `id` | yes | stable case id, for example `arg.south-atlantic.m0` |
| `title` | yes | human name of the claim |
| `domain` | yes | `plate-tectonics`, `stratigraphy`, `petrology`, `geomorphology`, `geophysics`, `other` |
| `claim` | yes | the single conclusion under test |
| `claim.id` | yes | short id used in reports, for example `C1` |
| `claim.statement` | yes | one sentence, falsifiable |
| `claim.kind` | yes | `reconstruction`, `timing`, `correlation`, `mechanism`, `existence`, `classification` |
| `claim.layer` | yes | `L0` to `L4` |
| `claim.scope` | yes | where and when the claim applies |
| `premises[]` | yes | at least one load-bearing statement |
| `premises[].id` | yes | `P1`, `P2`, ... |
| `premises[].statement` | yes | the premise itself, not a pointer |
| `premises[].kind` | yes | `evidenced` or `derived` |
| `premises[].layer` | yes | `L0` to `L4` |
| `premises[].status` | yes | `untested`, `supported`, `defeated`, `undetermined` (declarative; the judge aggregates evidenced premises from the worst referenced evidence status, and resolves a derived premise through the nearest `workspace.yaml` or a sibling case path, inheriting the target argument's verdict state) |
| `premises[].evidence_refs` | for evidenced | ids from `evidence.yaml` |
| `premises[].argument_ref` | for derived | id of another registered argument; resolved through the nearest `workspace.yaml`, a relative or absolute case path, or a sibling directory |
| `premises[].test_refs` | no | tests that check the premise |
| `premises[].independence_group` | no | coarse family hint used by audits |
| `inference.rule_id` | yes | warrant name, for example `W.rigid-plate-euler` |
| `inference.warrant` | yes | one sentence: why the premises support the claim |
| `inference.cp[]` | yes | conditions the warrant needs (ceteris paribus) |
| `cp[].id` | yes | `CP1`, `CP2`, ... |
| `cp[].statement` | yes | the condition that must hold |
| `cp[].cp_type` | yes | `structural`, `temporal`, `methodological`, `calibration` |
| `cp[].state` | yes | `unknown`, `holds`, `fails` |
| `cp[].test_ref` | yes | the test that decides this condition |
| `inference.defeaters[]` | yes | ways the argument breaks |
| `defeaters[].id` | yes | `D1`, `D2`, ... |
| `defeaters[].type` | yes | `undercutting` (attacks the inference) or `rebutting` (attacks the conclusion) |
| `defeaters[].statement` | yes | the defeat condition itself |
| `defeaters[].severity` | yes | `fatal` or `degrading` |
| `defeaters[].state` | yes | `unknown`, `established`, `refuted` |
| `defeaters[].test_ref` | yes | the test that establishes or refutes it |
| `defeaters[].counter_evidence` | optional | evidence ids recording the counter-evidence this defeat rests on |
| `entailments[]` | yes | consequences that must hold if the claim holds |
| `entailments[].id` | yes | `E1`, `E2`, ... |
| `entailments[].statement` | yes | the consequence |
| `entailments[].kind` | yes | `geometric-consistency`, `quantitative`, `blind-prediction`, `spatial-pattern`, `temporal-pattern` |
| `entailments[].risk` | yes | `low`, `medium`, `high` (how surprising the consequence is) |
| `entailments[].status` | yes | `untested`, `supported`, `defeated`, `undetermined` |
| `entailments[].test_ref` | expected | without a test the entailment cannot become a decisive event |
| `entailments[].counter_evidence` | optional | evidence ids recording the result that counts against this prediction |
| `dependencies.shared_calibration` | no | calibration products several records depend on |
| `dependencies.depends_on` | no | argument ids this one consumes |
| `gaps[]` | yes | what the contract cannot express |
| `gaps[].kind` | yes | `cannot-express`, `ambiguous`, `missing-field`, `overspecified`, `other` |
| `gaps[].description` | yes | the information that cannot be carried |
| `gaps[].severity` | yes | `blocking`, `annoying`, `minor` |
| `gaps[].where` | no | field path that cannot hold the information |
| `audit.author` | yes | who filled the contract |
| `audit.created` | yes | ISO date-time |
| `audit.updated` | yes | ISO date-time |
| `audit.version` | yes | contract revision |
| `audit.reviewed_by` | no | reviewers |
| `audit.source_case` | no | earlier case this one revises |

## Field of the argument (optional metadata)

`profile` is optional metadata. It labels the argument's field in the deliverable header; it selects no vocabulary and changes no verdict, `n_eff`, acceptance rate, or any test's discriminating power.

| Field | Required | Meaning |
| --- | --- | --- |
| `profile.primary` | if profile is declared | `general-geology`, `geochronology`, `planetary-geology`, `tectonics` |
| `profile.secondary[]` | no | additional fields; no duplicates, and none may repeat `primary` |
| `profile.rationale` | if profile is declared | one line: why this field describes the argument |

Omitted means "not declared"; the header says so. One claim per contract means one declared field per argument, not per paper. Deliverables quote the author's own condition, evidence, and prediction statements in ordinary language; they do not translate internal engine roles into new labels. Machine values such as `verdict`, `n_eff`, and `status` stay in the ledgers and the audit block.

The card may also carry a model-authored commentary paragraph: two to four sentences, the engine's numbers, passed with `--judgment "<text>"` or `--judgment-file <path>`. The audit block records the sha256 of the normalised paragraph text; when absent the card says the commentary was not provided. The paragraph is deliverable prose, not contract data. `geoarg report` accepts the same two flags.

## evidence.yaml

`records[]` entries:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | stable record id, for example `ev.airmag.sa-1997.m-series` |
| `kind` | yes | `observation`, `measurement`, `compilation`, `model-output`, `literature-derived` |
| `layer` | yes | `L1`, `L2`, or `L3` |
| `statement` | yes | what the record shows |
| `source` | yes | citation, dataset, version, access |
| `source.citation` | yes | human citation string |
| `source.doi` | no | DOI when one exists |
| `source.dataset` | no | dataset or archive name |
| `source.version` | no | dataset or product version |
| `source.access` | no | how the record was read |
| `coverage.spatial_extent` | yes | spatial footprint |
| `coverage.coverage_fraction` | yes | 0 to 1, measured fraction of the target area |
| `coverage.detectability` | yes | 0 to 1, probability of detecting the feature if present |
| `coverage.sample_count` | no | number of independent samples or sites |
| `independence.family` | yes | evidence family, for example `G.marine-geophysics` |
| `independence.independence_class` | yes | `physical`, `method`, `data`, `shared-calibration` |
| `independence.shared_sources` | no | calibration products shared with other records |
| `verification.level` | yes | `transcription`, `measurement`, or `interpretation` |
| `source_locator.page` | for transcription | 1-based page in the source PDF |
| `source_locator.quote` | for transcription | the sentence as it appears in the source |
| `status` | yes | `accepted`, `disputed`, `retracted`, `superseded` |

Coverage answers "could this evidence have found the feature if it were there?". A record without coverage numbers cannot support an absence claim. Only accepted records referenced by an evidenced premise count toward `n_eff`; a disputed, retracted or superseded record is listed under `excluded_records` and does not inflate the count. Calibration names declared in `dependencies` but attached to no counted record are reported as unattached.

## Transcription gate

A transcription-level record must carry a `source_locator`. `geoarg ground <case> --source <paper>` checks every declared quote against the source document (PDF, DOCX, HTML, Markdown, or plain text; the legacy `--pdf` flag still works) and writes `.geoarg/ground/<claim>.json`. Page numbers are meaningful only for PDF; other formats record every quote on page 1. Only a `grounded` quote may stay `accepted`; an accepted transcription-level quote without a grounded ledger entry fails `geoarg check`.

| Ledger status | Meaning | What to do |
| --- | --- | --- |
| `grounded` | quote found on the declared page | keep |
| `page-mismatch` | quote found on another page | fix the citation, do not delete the quote |
| `not-found` | quote found nowhere in the source | the draft was fabricated; mark the record `disputed` |
| `not-groundable` | the source has no usable text layer | OCR first, or keep the record at interpretation level |
| `no-locator` | no `source_locator` declared | add one or lower the verification level |

The ledger also records the source path, format and digest together with `acceptance_rate = grounded / drafted`; replacing the source file makes `geoarg verify` report `source document changed since grounding`. The gate proves that a string occurs in the source, not that the interpretation built on it is right.

## test.yaml

`records[]` entries:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | test id, for example `T2` |
| `name` | yes | human name |
| `checks` | yes | ids of premises, cp, defeaters, or entailments the test addresses (the claim id itself is not a condition) |
| `method.type` | yes | `geometric-consistency`, `statistical`, `blind-prediction`, `field-check`, `numerical-model`, `literature-review` |
| `method.description` | yes | what is measured and how |
| `method.threshold` | no | the pass/fail bound |
| `blind.is_blind` | yes | whether the test uses held-out data |
| `blind.held_out` | no | what was held out |
| `blind.preregistered` | no | whether the prediction was fixed before seeing the result |
| `discriminating_power` | yes | `none`, `low`, `medium`, `high` |
| `status` | conditionally | `planned`, `running`, `passed`, `failed`, `not-run`; required unless a `result` + `pass_rule` pair supplies a computed status |
| `result.value` | with `result` | numeric outcome (a pass rate, an effect size, a count) |
| `result.uncertainty` | no | `kind`, `low`, `high` interval around the value |
| `result.n` | no | sample size behind the value |
| `result.data_ref` | no | pointer to the data (a record id or a file) |
| `result.notes` | no | free text |
| `pass_rule` | with `result` | `op` (`ge`, `le`, `between`, `within_ci`, `ratio`) plus the operands that op needs (`value`, `low`, `high`, `target`, `tolerance`); the engine computes `passed` / `failed` / `inconclusive` |
| `cost` | no | numeric relative cost; `hit-set` ranks by power, then by cost |

`counter_evidence` links real counter-evidence to the defeat condition or prediction it supports. The ids must
exist in `evidence.yaml` and must not repeat inside one row. `geoarg independence` reports these records in a
separate `counter` block and does not count them as supporting lines; `geoarg impact` marks them `counter: true`
in leave-one-out ablation instead of `unused`; `geoarg report` prints them in the counter-evidence and prediction
tables. The field is optional and is not part of the verdict rules.

A satisfied state is bound to its test: `cp[].state: holds`, `defeaters[].state: refuted` and an entailment `status: passed` only count when a referenced test has `status: passed` with power `low` or better. Otherwise `geoarg judge` lists the item as `unbacked`, the verdict cannot rise above `UNDETERMINED`/`UNTESTED`, and `geoarg commit` refuses the case. A passed test with `discriminating_power: none` does not support anything.

When a test records a numeric result and a pass rule, the engine computes its status and that value wins over the typed `status`. `judge` reports a mismatch between the two and uses the computed value; `commit` records the computed statuses, and `verify` reports `computed test statuses changed` if `result` or `pass_rule` is edited afterwards. Tests without a `result` block keep using the typed `status`.

`discriminating_power` answers "would the competing hypothesis predict something different?". A test both hypotheses pass has power `none`, even if it passes.

## bundle.yaml

`id`, `title`, and the top-level `arguments` list are optional: `bundle` and `workspace` auto-discover cases from the filesystem, and the schemas do not require these fields.

A paper with several claims gets one `bundle.yaml` in the directory above the case directories:

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | `geoarg/bundle/0.1` |
| `id` | yes | bundle id |
| `title` | yes | paper title |
| `claims` | yes | non-empty list of `{case, label, required}`; `case` is a case directory relative to the bundle root (an absolute path is also accepted), `label` is optional, `required` defaults to `true` |

`geoarg bundle <dir>` runs `judge` on every case and aggregates the required claims with `SUPPORTED < UNDETERMINED < UNTESTED < SUSPENDED < DEFEATED`, taking the weakest one. Missing or invalid cases are reported as problems, never silently aggregated.

## workspace.yaml

A set of related arguments gets one `workspace.yaml` at or above their common directory. `judge` walks up from each case directory to the nearest workspace file and resolves `derived` premises through it.

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | `geoarg/workspace/0.1` |
| `id` | no | workspace id |
| `title` | no | human label used by the workspace report |
| `arguments` | yes | non-empty list of `{id, case, label}`; `id` is the argument id referenced by `argument_ref`, `case` is a case directory relative to the workspace root (an absolute path is also accepted), `label` is optional |

Resolution order for an `argument_ref`: an `id` in the nearest workspace → a relative or absolute case path → a sibling directory. If the target argument's premise is itself derived, the chain is followed recursively; a cycle or an unresolved reference is a workspace problem and `commit` refuses it. `commit` records the chain digest; `verify` recomputes it and reports `argument chain changed since commit`.

## migrate

`geoarg migrate <case|dir>` rewrites only the `schema_version` line of `argument.yaml`, `evidence.yaml`, and `test.yaml` (or of `bundle.yaml` or `workspace.yaml`) to the current schema, preserving every other byte. `--dry-run` reports without writing; the command is idempotent.

## attestation.json

`geoarg attest <case> --judgment-file <text>` binds the deliverables produced from a committed record. It reads the latest ledger `commit` entry, refuses when the registry record is not that commit, and writes `.geoarg/attestation.json`:

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | `geoarg/attestation/0.1` |
| `claim_id` | yes | claim id of the committed case |
| `record_sha256` | yes | digest of the registry record the deliverables came from |
| `rule_version` | yes | rule version at attestation time |
| `engine_sha256` | yes | engine digest at attestation time |
| `created_at` | yes | UTC timestamp |
| `environment` | yes | `geoarg`, `python`, `platform` of the attesting run |
| `deliverables[]` | yes | `{path, sha256, bytes}` for each bound file (`report.*`, `card.*`, or explicit `--include` globs) |
| `judgment[]` | no | the same shape for each `--judgment-file` |
| `note` | no | free-text note |

Changing a bound file without re-attesting makes `verify` report `deliverable changed since attestation`; changing the engine without re-attesting reports `engine changed since attestation`. An attestation is a byte-level claim about the delivered files, not a judgement that their prose is faithful.

## anchor.json

`geoarg anchor <case>` writes a checkpoint of the ledger head that a reader can keep outside the repository:

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | `geoarg/anchor/0.1` |
| `claim_id` | yes | claim id of the committed case |
| `record_sha256` | yes | digest of the registry record at anchoring time |
| `ledger_head` | yes | digest of the latest ledger entry before the anchor entry |
| `ledger_count` | yes | number of entries before the anchor entry |
| `engine_sha256` | yes | engine digest at anchoring time |
| `created_at` | yes | UTC timestamp |
| `anchor_sha256` | yes | canonical digest of the payload without this field |
| `note` | no | free-text note |

`verify` reports an anchor file that was edited, that points at a different record, or that is not recorded in the ledger. The anchor only resists wholesale ledger replacement if the file is copied out of the case directory; the repository does not provide timestamping or a transparency log.

## ledger.jsonl

`commit`, `attest`, and `anchor` append entries to `.geoarg/ledger.jsonl`: `{schema_version: geoarg/ledger/0.3, kind, claim_id, created_at, record_sha256, prev, sha256, ...}` where `kind` is `commit`, `attestation`, or `anchor`. A `commit` entry also carries `verdict`, `rule_version`, and `engine_sha256`; an `anchor` entry carries `ledger_head` and `ledger_count`; an `attestation` entry carries the attestation digest. `record_sha256` is the SHA-256 of the canonical registry record; `sha256` covers the entry body and `prev` points at the previous entry's `sha256` (0.1/0.2 legacy lines are linked through `record_sha256`). `verify` checks the chain, the latest `commit`, any attestation and anchor, and the digest of the current registry file. The ledger is still inside the case directory, so it detects a quietly rewritten history, not a fabricated commit; copy `anchor.json` outside and compare with `verify --anchor <file>`.

## impact 输出字段（1.3）

`geoarg impact <case> [--assume ...] [--add-evidence file] [--workspace] [--json]` 输出：

| 字段 | 含义 |
| --- | --- |
| `case` / `claim_id` / `rule_version` | 被分析的案例、主张与规则版本 |
| `before` / `after` | 假设前后：`verdict` 与 `hard`/`soft`/`pending` 理由 |
| `value` | `class`（`decisive`/`backing`/`redundant`/`none`）、`verdict_delta`（正数表示更接近成立）、`assumptions` |
| `prospective_evidence` | `--add-evidence` 追加的证据 id |
| `remaining` | 假设后仍然存在的 `hard`/`soft`/`pending`/`unbacked` 与未跑的 `gating` 测试 |
| `independence` | 假设前后的 `n_eff`、记录数与 `n_eff_delta` |
| `ablation.evidence` / `ablation.tests` | 留一法逐条结果：`id`、`class`（`decisive`/`backing`/`redundant`/`unused`/`untapped`）、`delta`、`verdict_without` |
| `limits` | 固定说明：不估计概率、状态是解读判断、留一法不衡量相互作用 |

`class` 的判定只看重算后的判决与理由列表，不看数据质量；`untapped` 表示该测试还没有挂到任何声明状态（如 `state: holds`、`status: passed`），所以拿掉它也不会改变判决。

## domain.yaml（1.5）

`domain.yaml` 是可选的领域包，放在案例目录或它的某个上级目录；最近的 pack 生效，`GEOARG_DOMAIN_FILE` 环境变量可指定一份 pack。pack 只能扩展下列 11 组枚举，内置值永远保留：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | 固定 `geoarg/domain/0.1` |
| `name` | string | 是 | pack 名（非空、不含空白） |
| `enums` | mapping | 是 | 键必须是 `domains`、`profiles`、`claim_kinds`、`method_types`、`entailment_kinds`、`cp_types`、`defeater_types`、`evidence_kinds`、`verification_levels`、`independence_classes`、`gap_kinds` 之一；值是字符串列表 |
| `default_profile` | mapping | 否 | `primary`（必填）、`secondary`（列表）、`rationale`；`geoarg advise` 会显示 |
| `patterns_dir` | string | 否 | 随包模式目录，默认 `patterns/`；相对 `domain.yaml` |
| `test_suggestions` | mapping | 否 | claim kind → 方法字符串列表，或 `{method, why}` 列表；方法必须在生效的 method_type 中 |
| `evidence_families` | list | 否 | 期望证据族：字符串或 `{name, independence_class, why}` |
| `grounding` | mapping | 否 | `formats`（pdf/docx/html/markdown/text 的子集）与 `notes` 字符串列表 |
| `title` / `description` | string | 否 | 仅用于阅读 |

`validate` 用合并后的枚举；`commit` 往 registry 记录写 `domain`（name、路径、sha256）；提交后改动 pack，`verify` 报 `domain pack changed since commit`。schema 侧 `_schema/domain.schema.json` 只校验形状，枚举含义仍由 `contract.validate` 决定。

1.6 起 pack 可以携带字段知识（默认 profile、随包模式、建议检验、期望证据族、接地提示），这些字段都进入 pack 摘要。
`geoarg advise <case>` 只打印检查清单（缺哪些方法与证据族、默认 profile、接地提示），不改变判决、不写记录；`check --advise`
把同样的缺口当作 WARNING 打印。随包模式用 `geoarg patterns <case>` 查看，`geoarg new` 在 pack 目录内优先使用。

## 表单编辑器（1.5）

`geoarg edit <case>` 启动只监听 `127.0.0.1` 的本地表单编辑器（无外部依赖，令牌保护，保存时原子写入三份 YAML 并立即校验）。它编辑 claim、推理、前提、条件、判废条件、蕴含、证据与检验；不新增信任层级，`commit` 门槛不变。

## 证据包（1.7）

`geoarg package <case> --out <dir>` 生成一个可移交目录，`geoarg verify-package <dir>` 独立核对它。

| 文件 | 含义 |
| --- | --- |
| `manifest.json` | `schema_version: geoarg/package/0.1`；`claim_id`、`verdict`、`rule_version`、`engine {version, sha256}`、`case_digest`、`record {path, sha256, committed_at, verdict}`、`ledger {path, sha256, head, count}`、`anchor` 或 `null`、`attestation {sha256, attestation_sha256, record_sha256, engine_sha256, deliverables[], judgment[]}`、`grounding` 或 `null`、`files[]`（每项含 `path`、`package_path`、`role`、`sha256`、`bytes`） |
| `ro-crate-metadata.json` | 最小 RO-Crate 1.1：`Dataset` 节点的 `hasPart` 列出包内文件 |
| `README.md` | 证据包说明、核对步骤与边界 |
| `files/report.html` | 按包语言生成的单文件报告（不新增证明） |
| `files/deliverables/`、`files/judgments/` | 证明绑定的产出与判断段落 |
| `files/sources/` | 仅 `--include-source` 时出现的来源文档 |

核对规则：`verify-package` 重算所有摘要；重载契约并重算判决；核对记录摘要与 verdict；核对台账自哈希链与头；核对证明的 `record_sha256` 与每个已绑定产出的摘要；核对锚点的 `record_sha256`、`anchor_sha256` 与台账头；核对接地台账摘要。版本不同只告警，摘要不一致直接失败。
