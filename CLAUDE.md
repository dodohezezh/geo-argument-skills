# Repository conventions

For agents working in this repository.

## Layout

- `skills/geology/<skill-name>/SKILL.md` plus `references/`. One skill per directory.
- `docs/geology/<skill-name>.md` is the human page for each skill. Every skill needs one.
- `scripts/geoarg/` is the engine. `scripts/tests/` is its unittest suite.
- `schema/` holds optional JSON Schema files. They document the contract; `validate` in `contract.py` is authoritative.
- `examples/<case>/` holds a full GeoArg case and a short README. `examples/paper-demo/` ships a synthetic PDF and its committed grounding ledger so `geoarg check` passes out of the box.

## Commands

- Tests: `python -m unittest discover -s scripts/tests`
- Lint the example: `geoarg check examples/south-atlantic`
- Grounded example: `geoarg ground examples/paper-demo --pdf examples/paper-demo/paper.pdf`
- Full smoke: `geoarg judge examples/south-atlantic && geoarg independence examples/south-atlantic`

Run tests before committing. Keep the example cases clean; tests assert on their numbers (3 records, `n_eff = 1.2`, 13 decisive events) and on the grounding statuses of the demo case (3 grounded quotes, acceptance rate 1.0).

## Skill conventions

- Frontmatter has `name` and `description` only. The description decides invocation, so write triggers, not a table of contents.
- Skills here are model-invoked: no `disable-model-invocation`.
- `SKILL.md` leads with steps and completion criteria; put tables and formulas in `references/` and point to them.
- One source of truth per meaning. Do not restate the schema in prose and in the table.
- Write English in `SKILL.md` and `references/`; write Chinese in `README.md` and `docs/`.

## Prose

- No em dashes in English prose. Use commas, parentheses, or a colon. (Chinese prose uses its own punctuation.)
- Prefer counts and labels over adjectives.
- State the positive behaviour ("every condition gets a test") before the prohibition.

## Versioning

- `contract.py` `SCHEMA_VERSION` and `judge.py` `RULE_VERSION` move together. `ground.py` carries its own `GROUND_SCHEMA_VERSION`; a change to the grounding statuses or ledger shape bumps it.
- A change to judge rules, the contract schema, or the grounding gate requires a version bump and a test that covers the new behaviour.
- `verify` compares the engine digest; a code change without a version bump will surface as drift on every committed case. That is intentional.
