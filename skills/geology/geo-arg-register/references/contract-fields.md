# Contract field reference

Three files per case directory: `argument.yaml`, `evidence.yaml`, `test.yaml`. `schema_version` is `geoarg/0.2` in all three. `schema/*.json` documents the same contract; `validate` in `contract.py` is authoritative when the two disagree.

## argument.yaml

| Field | Required | Meaning |
| --- | --- | --- |
| `schema_version` | yes | `geoarg/0.2` |
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
| `premises[].status` | yes | `untested`, `supported`, `defeated`, `undetermined` (declarative; the judge recomputes evidenced premises from evidence status and leaves derived ones `undetermined` in v0.1) |
| `premises[].evidence_refs` | for evidenced | ids from `evidence.yaml` |
| `premises[].argument_ref` | for derived | id of another registered argument |
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
| `entailments[]` | yes | consequences that must hold if the claim holds |
| `entailments[].id` | yes | `E1`, `E2`, ... |
| `entailments[].statement` | yes | the consequence |
| `entailments[].kind` | yes | `geometric-consistency`, `quantitative`, `blind-prediction`, `spatial-pattern`, `temporal-pattern` |
| `entailments[].risk` | yes | `low`, `medium`, `high` (how surprising the consequence is) |
| `entailments[].status` | yes | `untested`, `supported`, `defeated`, `undetermined` |
| `entailments[].test_ref` | expected | without a test the entailment cannot become a decisive event |
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

## evidence.yaml

`records[]` entries:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | stable record id, for example `ev.airmag.sa-1997.m-series` |
| `kind` | yes | `observation`, `measurement`, `compilation`, `model-output`, `literature-derived` |
| `layer` | yes | `L1`, `L2`, or `L3` |
| `statement` | yes | what the record shows |
| `source` | yes | citation, dataset, version, access |
| `source.citation` | expected | human citation string |
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

Coverage answers "could this evidence have found the feature if it were there?". A record without coverage numbers cannot support an absence claim. Only records referenced by an evidenced premise count toward `n_eff`; calibration names declared in `dependencies` but attached to no counted record are reported as unattached.

## Transcription gate

A transcription-level record must carry a `source_locator`. `geoarg ground <case> --pdf <paper>` checks every declared quote against the PDF text layer and writes `.geoarg/ground/<claim>.json`. Only a `grounded` quote may stay `accepted`; an accepted transcription-level quote without a grounded ledger entry fails `geoarg check`.

| Ledger status | Meaning | What to do |
| --- | --- | --- |
| `grounded` | quote found on the declared page | keep |
| `page-mismatch` | quote found on another page | fix the citation, do not delete the quote |
| `not-found` | quote found nowhere in the PDF | the draft was fabricated; mark the record `disputed` |
| `not-groundable` | the PDF has no usable text layer | OCR first, or keep the record at interpretation level |
| `no-locator` | no `source_locator` declared | add one or lower the verification level |

The ledger also records `acceptance_rate = grounded / drafted`. The gate proves that a string occurs in the source, not that the interpretation built on it is right.

## test.yaml

`records[]` entries:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | test id, for example `T2` |
| `name` | expected | human name |
| `checks` | expected | ids of premises, cp, defeaters, or entailments the test addresses |
| `method.type` | yes | `geometric-consistency`, `statistical`, `blind-prediction`, `field-check`, `numerical-model`, `literature-review` |
| `method.description` | yes | what is measured and how |
| `method.threshold` | yes | the pass/fail bound |
| `blind.is_blind` | yes | whether the test uses held-out data |
| `blind.held_out` | no | what was held out |
| `blind.preregistered` | no | whether the prediction was fixed before seeing the result |
| `discriminating_power` | yes | `none`, `low`, `medium`, `high` |
| `status` | yes | `planned`, `running`, `passed`, `failed`, `not-run` |
| `result` | no | value, passed, notes, computed_at |
| `cost` | no | approximate person-weeks |

`discriminating_power` answers "would the competing hypothesis predict something different?". A test both hypotheses pass has power `none`, even if it passes.
