# Figures

GeoArg can render four deterministic SVG figures for a case. They are a
visual rendering of the argument's interpreted states; they are **not** new
evidence, and they never enter `engine_digest`, a verdict, a committed record
or a trust-chain check. Figures are presentation only.

The visual rules are adapted from
[nature-figure-craft](https://github.com/Alto-R/nature-figure-craft) (code MIT,
docs CC BY 4.0): pick the claim first, size the artwork for its final landing
width, keep a minimum landed type size, use a semantic palette, and check that
the palette survives a grayscale print. No code or assets are copied, and no
plotting dependency is added: the figures are written by a small built-in SVG
canvas.

## Commands

```bash
geoarg figures <case>                    # write <case>/figures/*.svg + figures.json
geoarg figures <case> --out out/ --lang zh --json
geoarg report <case> --format html       # embeds <case>/figures/*.svg inline when present
geoarg report <case> --format html --figures out/
geoarg package <case> --out pkg/ --include-figures
```

The HTML report stays a single self-contained file: each SVG is inlined
before the footer. The figures directory is ignored by the engine and by
verification; if you want a hand-off package to carry the figures, pass
`--include-figures` to `package`, which copies them under `files/figures/` and
records their SHA-256 in `manifest.json`.

## The four figures

| file | question it answers | encoding |
| --- | --- | --- |
| `argument-status.svg` | How many items of each kind are blocking, weakening, pending, or satisfied? | grouped stacked bars by premises / conditions / defeaters / entailments |
| `independence.svg` | How much does the reported `n_eff` depend on the assumed pairwise `rho`? | line of `n_eff` against `assumed_rho`, marker at the reported `mean_rho` |
| `decision-value.svg` | Which evidence lines actually carry the verdict, and which tests are worth running? | leave-one-out evidence classes on the left; test power against cost on the right |
| `evidence-coverage.svg` | Where do the evidence records sit in declared coverage / detectability space? | scatter of `coverage_fraction` against `detectability`, coloured by evidence status |

All four are labelled in English or Chinese with `--lang`. The manifest
`figures.json` records the case, claim id, verdict, language, every file's
byte count and SHA-256, and the figure limits.

## Style rules (borrowed)

- **Choose before you draw.** Each figure answers one question, not "all the
  data"; the argument-status figure is a count of interpreted states, the
  decision-value figure is a leave-one-out summary.
- **Land at 88 mm or 180 mm.** Figures are drawn directly at 88 mm (single
  column) or 180 mm (double column) in millimetre user units. Smaller or
  larger copies change the landed type size.
- **Minimum 6 pt landed type.** Every text call goes through
  `figstyle.check_font`; the figures use 6.4-9.5 pt.
- **Semantic palette.** Verdicts and reason buckets have fixed colours
  (`figstyle.VERDICT_COLORS`, `BUCKET_COLORS`); colour is never the only
  channel - segments carry counts and every panel has a text label.
- **Grayscale check.** `figstyle.grayscale_conflicts(palette)` reports pairs
  whose luminance contrast is below 1.35; `palette_report` returns the same
  check plus per-colour luminance. The tests exercise both.
- **Deterministic bytes.** No timestamps, no scripts, no external assets;
  identical inputs produce byte-identical files (the tests compare two builds).
- **Static base + visual layer.** States and numbers come from `judge`,
  `independence.report` and `impact.ablation`; the figure module re-reads
  those payloads, it does not recompute the engine differently.

## Limits

- A figure renders interpreted states; it cannot show whether the evidence is
  true.
- No probability is encoded or implied.
- Figures are not part of `engine_digest`, a verdict, or a trust-chain check.
  They can be bound by `attest` as ordinary deliverables if you want the
  package to prove which figure bytes you shipped, but binding figures does not
  strengthen the argument.
- Land using the 88 mm / 180 mm widths. If you restyle, re-check the landed
  type sizes and the grayscale palette.
