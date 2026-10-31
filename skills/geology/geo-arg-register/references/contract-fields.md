# Contract field reference

Three files per case directory: `argument.yaml`, `evidence.yaml`, `test.yaml`. `schema_version` is `geoarg/0.1` in all three.

## argument.yaml

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | stable case id, for example `arg.south-atlantic.m0` |
| `title` | yes | human name of the claim |
| `domain` | no | geology subfield |
| `claim` | yes | the single conclusion under test |
| `claim.id` | yes | short id used in reports, for example `C1` |
| `claim.statement` | yes | one sentence, falsifiable |
| `claim.kind` | yes | `reconstruction`, `timing`, `correlation`, `mechanism`, `existence`, `classification` |
| `claim.layer` | yes | `L0` to `L4` |
| `claim.scope` | yes | where and when the claim applies |
| `premises[]` | yes | the load-bearing statements |
| `premises[].kind` | yes | `evidenced` or `derived` |
| `premises[].evidence_refs` | for evidenced | ids from evidence.yaml |
| `premises[].argument_ref` | for derived | id of another registered argument |
| `premises[].test_refs` | no | tests that check the premise |
| `premises[].independence_group` | no | coarse family hint used by audits |
| `inference.rule_id` | yes | warrant name, for example `W.rigid-plate-euler` |
| `inference.warrant` | yes | one sentence: why the premises support the claim |
| `inference.cp[]` | yes | conditions the warrant needs (ceteris paribus) |
| `cp[].cp_type` | yes | `structural`, `temporal`, `methodological`, `calibration` |
| `cp[].state` | yes | `unknown`, `holds`, `fails` |
| `cp[].test_ref` | yes | the test that decides this condition |
| `inference.defeaters[]` | yes | ways the argument breaks |
| `defeaters[].type` | yes | `undercutting` (attacks the inference) or `rebutting` (attacks the conclusion) |
| `defeaters[].severity` | yes | `fatal` or `degrading` |
| `defeaters[].state` | yes | `unknown`, `established`, `refuted` |
| `defeaters[].test_ref` | yes | the test that establishes or refutes it |
| `entailments[]` | yes | consequences that must hold if the claim holds |
| `entailments[].kind` | yes | `geometric-consistency`, `quantitative`, `blind-prediction`, `spatial-pattern`, `temporal-pattern` |
| `entailments[].risk` | yes | `low`, `medium`, `high` (how surprising the consequence is) |
| `entailments[].status` | yes | `untested`, `passed`, `failed` |
| `dependencies.shared_calibration` | no | calibration products several records depend on |
| `gaps[]` | yes | what the contract cannot express |
| `gaps[].kind` | yes | `cannot-express`, `ambiguous`, `missing-field`, `overspecified`, `other` |
| `gaps[].severity` | yes | `blocking`, `annoying`, `minor` |

## evidence.yaml

`records[]` entries:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | stable record id, for example `ev.airmag.sa-1997.m-series` |
| `kind` | yes | `observation`, `measurement`, `compilation`, `model-output`, `literature-derived` |
| `layer` | yes | `L1`, `L2`, or `L3` |
| `statement` | yes | what the record shows |
| `source` | yes | citation, dataset, version, access |
| `coverage.spatial_extent` | yes | spatial footprint |
| `coverage.coverage_fraction` | yes | 0 to 1, measured fraction of the target area |
| `coverage.detectability` | yes | 0 to 1, probability of detecting the feature if present |
| `coverage.sample_count` | no | number of independent samples or sites |
| `independence.family` | yes | evidence family, for example `G.marine-geophysics` |
| `independence.independence_class` | yes | `physical`, `method`, `data`, `shared-calibration` |
| `independence.shared_sources` | no | calibration products shared with other records |
| `verification.level` | yes | `transcription`, `measurement`, or `interpretation` |
| `status` | yes | `accepted`, `disputed`, `retracted`, `superseded` |

Coverage answers "could this evidence have found the feature if it were there?". A record without coverage numbers cannot support an absence claim.

## test.yaml

`records[]` entries:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | test id, for example `T2` |
| `name` | yes | human name |
| `checks` | yes | ids of premises, cp, defeaters, or entailments the test addresses |
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
