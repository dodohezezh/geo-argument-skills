# Contributing

Thanks for looking at **geoarg**. This project is a deterministic auditor for
geological arguments: the engine checks internal consistency, while evidence and
claims stay authored records. Contributions are welcome as cases, domain packs,
patterns, documentation fixes, and engine changes that keep the engine honest.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -e ".[schema]"
geoarg --version
python -m unittest discover -s scripts/tests
```

Python 3.11+ is required. Tests are offline. Do not add network calls to the
default `check` / `commit` / `verify` paths; optional layers (`geoarg references`)
may use the network only when explicitly invoked.

## Principles

- **Verdicts are a lattice, not a score.** Do not add a confidence percentage.
- **The engine only checks what is checkable.** Quote grounding, state-to-test
  binding, reference integrity, result binding, ledger/attestation drift are
  mechanical. Independence, power and content support stay authored records.
- **`contract.validate` is authoritative.** JSON Schemas are shape checks and a
  second opinion; when they disagree, the engine wins.
- **No silent defaults in the trust chain.** A missing sidecar or an unreadable
  file must be reported, not ignored.
- **Plain language for readers.** `report` / `card` output avoids tool jargon
  and untranslated state names; machine values stay in the ledger.

## Where things live

- `scripts/geoarg/` — engine modules. The engine digest (`audit._ENGINE_FILES`)
  covers contract, judge, results, independence, hitting, ground, chain, audit,
  attest, safeio, schemas and domains. Changing any of them invalidates committed
  records and requires re-committing the fixtures/cases.
- `scripts/geoarg/_schema/` — JSON Schemas shipped in the wheel.
- `scripts/geoarg/_patterns/` — built-in argument patterns (`geoarg new`).
- `examples/` — fixtures; they must stay clean and pass `geoarg check`.
- `skills/` — the `geo-arg-register` and `geo-arg-audit` agent skills.
- `docs/` — design notes and reference material.

## Version and release policy

- Bump the version in `scripts/geoarg/__init__.py`, `pyproject.toml`,
  `.claude-plugin/plugin.json`, `scripts/geoarg/install.py` and the skills'
  preflight line.
- A change to an engine-digest file requires re-running `geoarg commit`,
  `geoarg attest` and `geoarg anchor` for the fixtures/cases you keep, and a
  CHANGELOG entry explaining why the records were re-signed.
- Release checklist: full test suite; wheel build; Desktop mirror (if maintained);
  `geoarg install-skills`; `geoarg doctor`; `geoarg verify` on the registered
  cases; commit.

## Adding a case or domain pack

- A case is three YAML files (`argument.yaml`, `evidence.yaml`, `test.yaml`) in
  one directory. See `examples/paper-demo` for a paper-based case and
  `examples/workspace-demo` for linked arguments.
- A domain pack is an optional `domain.yaml` in the case directory or an
  ancestor; it may extend the 11 extensible enum families, add patterns, test
  suggestions, evidence families and grounding notes. It cannot redefine
  built-in values.
- Run `geoarg check`, `geoarg judge`, `geoarg ground` (when quotes exist) and
  `geoarg workspace` before proposing the case.

## Submitting changes

- Open a pull request with a focused description and the commands you ran.
- For bugs, include a minimal case directory or the exact `geoarg` command,
  expected behavior and `geoarg --version` / `geoarg doctor` output.
- For security-relevant trust-layer issues, follow `SECURITY.md` instead of
  filing a public issue with sensitive material.
