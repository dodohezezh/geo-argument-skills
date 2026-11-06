# Citation checks (optional layer)

geoarg's trust chain fixes three things: the argument's internal states, the
evidence that backs them, and the bytes a reader receives. It deliberately
does **not** contact the internet in `check`, `commit` or `verify`, because a
verifiable record must be recomputable offline.

Citation checks are a separate, opt-in layer. They answer a narrower question
than the trust chain: *does this citation point at something that exists, and
does every citation-bearing evidence record at least carry a quoted passage and
a source document?*

Two commands start the audit explicitly.

## `geoarg sources <case>` (offline)

Reads the case and lists every evidence record that carries a citation:

- whether it has a quoted passage (`source_locator.quote`);
- whether the case carries a grounding ledger and source document;
- a summary count.

Flags:

- `--require-quote`: fail (exit 1) when a citation-bearing record has no
  quoted passage.
- `--require-source`: fail when the case cites literature but has no grounding
  ledger/source document.

Default mode only reports. It never changes a verdict, a commit or a verify
result, and it never touches the network.

## `geoarg references <case>` (online, cached)

Extracts resolvable identifiers from each citation (DOI, PMCID, PMID, arXiv),
queries Crossref (DOI) and Europe PMC (PMCID/PMID/DOI), and compares the
citation's year and first-author surname with the provider record. Where the
provider reports it, a retraction is surfaced too.

Statuses:

| status | meaning |
|---|---|
| `verified` | identifier resolves and year/author agree |
| `mismatch` | identifier resolves but year/author disagree |
| `not-found` | provider answered and had no record |
| `retracted` | provider reports a retraction/update |
| `unverifiable` | no provider could be reached, or the provider had no usable record |
| `no-identifier` | the citation contains no DOI/PMCID/PMID/arXiv id |

The result is written to `.geoarg/references.json` (a snapshot with a
timestamp). Later runs read the snapshot unless `--refresh` is passed;
`--offline` reads only the snapshot and never touches the network.
`--require-verified` exits 1 unless every checked citation is `verified`.

## Boundaries

- This layer is **advisory**. It is not part of the engine digest, it does not
  alter a verdict, and `commit`/`verify` do not require it.
- Existence and metadata are not truth: a real paper can still be
  misrepresented, retraction signals can lag, and books, reports, regional
  journals and translations are often only partially covered (they usually end
  up `unverifiable` or `no-identifier`).
- A snapshot proves what was checked at one time, not what is true forever.
  Re-run with `--refresh` when citations matter, and keep the snapshot with the
  case if you hand the record to someone else.
- The online command sends only identifiers and no case text. If the network is
  unavailable, `unverifiable` is an honest result, not a failure of the case.
