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

## Quickstart

```bash
git clone <your-fork-url> geo-argument-skills
cd geo-argument-skills
pip install -e .
geoarg check examples/south-atlantic
geoarg judge examples/south-atlantic
geoarg independence examples/south-atlantic
geoarg hit-set examples/south-atlantic
geoarg ground examples/paper-demo --pdf examples/paper-demo/paper.pdf
geoarg report examples/south-atlantic
python -m unittest discover -s scripts/tests
```

No network. Only PyYAML, pypdf and python-docx.

## Commands

| Command | What it does |
| --- | --- |
| `geoarg check <case>` | structural and cross-reference validation |
| `geoarg judge <case>` | verdict and reason chain |
| `geoarg independence <case>` | `n_eff / n`, mean rho, warnings |
| `geoarg hit-set <case>` | single-event defeat paths ranked by power |
| `geoarg report <case>` | Word report by default (`<case>/report.docx`); `--format md` prints Markdown; `--lang zh` renders the report frame in Chinese; `--full` writes the complete report (default is a one-page brief) |
| `geoarg commit <case>` | hash-chained registry record |
| `geoarg verify <case>` | recompute and report drift |
| `geoarg ground <case> --pdf <paper>` | match every source quote against the PDF text layer, write a grounding ledger, report an acceptance rate |

## Grounding gate

The most common LLM error in geology is not bad inference; it is quoting a sentence that the source never contains. The gate turns that check into a string match:

1. Transcription-level evidence carries a `source_locator`: page plus the sentence as it appears in the source.
2. `geoarg ground` opens the PDF, normalizes the text layer, and searches each declared page.
3. Four statuses: `grounded` (found on the declared page), `page-mismatch` (found elsewhere), `not-found` (fabricated), `not-groundable` (no text layer).
4. `check` and `commit` reject an accepted transcription record whose quote is not grounded; the ledger digest enters the registry, so editing a quote shows up as drift in `verify`.

The acceptance rate is `grounded / drafted`. It is a different dimension from `n_eff`: one counts independent lines, the other counts quotes that exist. The gate proves the sentence is in the source. It does not prove the sentence supports the premise; that is the audit's job.

## Design principles

1. Determinism in the script, judgement in the model.
2. The contract is the interface: three YAML files, documented in [contract-fields.md](skills/geology/geo-arg-register/references/contract-fields.md).
3. Verdicts are recomputable: `commit` records input and engine hashes; `verify` reports any drift.
4. `unknown` is a legal state; the contract reports it instead of filling it with confidence.
5. Gaps are first-class: what the contract cannot express is registered, not hidden.
6. Quotes must land: transcription-level evidence carries a source locator and passes the grounding gate. An ungrounded quote may not stay `accepted`.

## Layout

```
skills/geology/            two skills
docs/geology/              Chinese usage pages
scripts/geoarg/            deterministic engine
scripts/tests/             unit tests
schema/                    JSON Schema (optional validation)
examples/south-atlantic/   teaching fixture (placeholder citations)
examples/paper-demo/       synthetic PDF with a committed grounding ledger
```

## Status and limits (v0.2)

- Does not verify the truth of a claim, only the structure and test status of the argument.
- Contracts cost effort; that is the price of a checkable argument.
- `hit-set` enumerates single-event defeat paths only.
- `n_eff` rho values are priors, not measurements; report them with the result.
- The grounding gate compares strings. A normalized miss is `not-found`; it proves the sentence exists, not that it is used correctly, and it does no OCR. Scanned PDFs come back `not-groundable`.
- The full research program (corpus, expert ratings, historical backtest) is outside this repository.

Skill layout, `SKILL.md` conventions, `docs/` page structure, and `plugin.json` follow [mattpocock/skills](https://github.com/mattpocock/skills). Content and engine are original.

## License

MIT
