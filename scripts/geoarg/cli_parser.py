"""Argument parser construction for the geoarg command line."""
from __future__ import annotations

import argparse

from . import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geoarg",
        description="Deterministic contract engine for geological arguments.",
    )
    parser.add_argument("--version", action="version", version=f"geoarg {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    specs = {
        "check": "structural and cross-reference validation",
        "judge": "compute the verdict from the contract",
        "independence": "effective evidence count and independence warnings",
        "hit-set": "the tests that would retract the claim now",
        "commit": "write a hash-chained registry record",
        "verify": "recompute a committed record and report mismatches",
        "report": "write the report (full Word report by default; --brief for a one-page brief)",
        "card": "write a conclusion page adapted to one reader (researcher or reviewer)",
        "migrate": "rewrite the schema_version lines to the current schema",
    }
    for name, help_text in specs.items():
        sub_parser = sub.add_parser(name, help=help_text)
        sub_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
        sub_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
        if name in ("commit", "verify"):
            sub_parser.add_argument("--registry", default=None, help="registry directory (default: <case>/.geoarg/registry)")
        if name == "verify":
            sub_parser.add_argument(
                "--anchor",
                default=None,
                help="external checkpoint file to check against this ledger (the copy you kept outside the case)",
            )
        if name == "migrate":
            sub_parser.add_argument("--dry-run", action="store_true", help="print the planned rewrite without touching files")
        if name == "report":
            sub_parser.add_argument("--format", choices=("docx", "md", "html"), default="docx", help="output format (default: docx; html is a self-contained page)")
            sub_parser.add_argument(
                "--lang",
                choices=("en", "zh", "auto"),
                default="en",
                help="report language (default: en; auto uses the machine system language)",
            )
            sub_parser.add_argument("--brief", action="store_true", help="write the one-page brief instead of the full report")
            sub_parser.add_argument(
                "--out",
                default=None,
                help="output path (default: <case>/report.docx for docx, <case>/report.html for html, stdout for md)",
            )
            sub_parser.add_argument(
                "--figures",
                default=None,
                help="directory of generated SVG figures to embed into the HTML report (default: <case>/figures when present)",
            )
            sub_parser.add_argument(
                "--judgment",
                default=None,
                help="commentary paragraph authored by the model (2 to 4 sentences); opens the report",
            )
            sub_parser.add_argument(
                "--judgment-file",
                default=None,
                help="path to a Markdown file holding the commentary paragraph",
            )
        if name == "check":
            sub_parser.add_argument(
                "--profile",
                choices=("strict", "draft"),
                default="strict",
                help="validation profile (draft downgrades completeness gaps to warnings)",
            )
            sub_parser.add_argument("--explain", action="store_true", help="print a fix hint for every problem")
            sub_parser.add_argument(
                "--advise",
                action="store_true",
                help="also print domain-pack suggestions (missing test methods and evidence families)",
            )
        if name == "card":
            sub_parser.add_argument(
                "--for",
                dest="audience",
                required=True,
                choices=("researcher", "reviewer"),
                help="who the card is for: researcher (self-check) or reviewer (assessment)",
            )
            sub_parser.add_argument(
                "--lang",
                choices=("en", "zh", "auto"),
                default="en",
                help="card language (default: en; auto uses the machine system language)",
            )
            sub_parser.add_argument("--out", default=None, help="output path (default: stdout)")
            sub_parser.add_argument(
                "--judgment",
                default=None,
                help="commentary paragraph authored by the model (2 to 4 sentences); opens the card",
            )
            sub_parser.add_argument(
                "--judgment-file",
                default=None,
                help="path to a Markdown file holding the commentary paragraph",
            )

    adopt_parser = sub.add_parser("adopt", help="turn a Markdown outline into a draft contract")
    adopt_parser.add_argument("markdown", help="Markdown file with Claim / Premises / Evidence / Tests sections")
    adopt_parser.add_argument("--out", required=True, help="directory to write the draft case into")
    adopt_parser.add_argument("--id", dest="case_id", default=None, help="case id (default: the output directory name)")
    adopt_parser.add_argument("--title", default=None, help="case title (default: the first claim line)")
    adopt_parser.add_argument("--claim", default=None, help="claim statement (overrides the Markdown claim)")
    adopt_parser.add_argument("--force", action="store_true", help="overwrite an existing contract in the output directory")
    adopt_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    new_parser = sub.add_parser("new", help="scaffold a case from a shipped argument pattern")
    new_parser.add_argument("dir", help="directory to create the case in")
    new_parser.add_argument("--pattern", required=True, help="pattern name (see: geoarg patterns)")
    new_parser.add_argument("--id", dest="case_id", default=None, help="case id (default: the directory name)")
    new_parser.add_argument("--title", default=None, help="case title (default: the pattern title)")
    new_parser.add_argument("--claim", default=None, help="claim statement (default: a TODO placeholder)")
    new_parser.add_argument("--force", action="store_true", help="overwrite an existing contract in the directory")
    new_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    patterns_parser = sub.add_parser("patterns", help="list shipped and pack-provided argument patterns")
    patterns_parser.add_argument("case", nargs="?", default=None, help="case directory (optional; adds its domain pack patterns)")
    patterns_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    advise_parser = sub.add_parser("advise", help="field advice from the nearest domain pack")
    advise_parser.add_argument("case", help="case directory")
    advise_parser.add_argument("--lang", choices=("en", "zh"), default="en", help="output language (default: en)")
    advise_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    domains_parser = sub.add_parser(
        "domains", help="list built-in enums, and the domain pack that applies to a case"
    )
    domains_parser.add_argument("case", nargs="?", default=None, help="case directory (optional)")
    domains_parser.add_argument("--lang", choices=("en", "zh"), default="en", help="output language (default: en)")
    domains_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    edit_parser = sub.add_parser("edit", help="open a local form editor for a case (served on 127.0.0.1)")
    edit_parser.add_argument("case", help="case directory to edit")
    edit_parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    edit_parser.add_argument("--port", type=int, default=8765, help="port (0 picks a free port; default: 8765)")
    edit_parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")

    figures_parser = sub.add_parser(
        "figures", help="write deterministic SVG figures (argument status, independence, decision value, evidence coverage)"
    )
    figures_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    figures_parser.add_argument("--out", default=None, help="output directory (default: <case>/figures)")
    figures_parser.add_argument("--lang", choices=("en", "zh"), default="en", help="figure language (default: en)")
    figures_parser.add_argument("--json", action="store_true", help="emit the manifest JSON instead of a summary")

    sources_parser = sub.add_parser(
        "sources", help="optional: which citations carry a quoted passage and a grounding source"
    )
    sources_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    sources_parser.add_argument("--require-quote", action="store_true", help="fail when a citation-bearing evidence record has no source_locator.quote")
    sources_parser.add_argument("--require-source", action="store_true", help="fail when the case cites literature but has no grounding ledger/source")
    sources_parser.add_argument("--lang", choices=("en", "zh"), default="en", help="report language (default: en)")
    sources_parser.add_argument("--out", default=None, help="write the report to this path instead of stdout")
    sources_parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")

    references_parser = sub.add_parser(
        "references", help="optional: verify DOI/PMCID/PMID/arXiv identifiers against Crossref and Europe PMC"
    )
    references_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    references_parser.add_argument("--providers", default="crossref,europepmc", help="comma-separated providers (default: crossref,europepmc)")
    references_parser.add_argument("--refresh", action="store_true", help="ignore the cached snapshot and query the providers again")
    references_parser.add_argument("--offline", action="store_true", help="read only the cached snapshot; never touch the network")
    references_parser.add_argument("--timeout", type=float, default=8.0, help="per-request timeout in seconds (default: 8)")
    references_parser.add_argument("--require-verified", action="store_true", help="fail unless every checked citation is verified")
    references_parser.add_argument("--lang", choices=("en", "zh"), default="en", help="report language (default: en)")
    references_parser.add_argument("--out", default=None, help="write the report to this path instead of stdout")
    references_parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")

    impact_parser = sub.add_parser("impact", help="decision value: ablation, what-if and prospective evidence")
    impact_parser.add_argument("root", help="case directory (or a workspace directory with --workspace)")
    impact_parser.add_argument(
        "--assume",
        action="append",
        default=[],
        help="assumption kind:id=value (repeatable), e.g. test:T1=passed or cp:CP1=holds",
    )
    impact_parser.add_argument(
        "--add-evidence",
        dest="add_evidence",
        default=None,
        help="YAML file with prospective evidence records (a list, or {records: [...]})",
    )
    impact_parser.add_argument(
        "--workspace",
        action="store_true",
        help="treat root as a workspace and apply the prospective evidence to every case",
    )
    impact_parser.add_argument("--lang", choices=("en", "zh"), default="en", help="report language (default: en)")
    impact_parser.add_argument("--out", default=None, help="write the Markdown report to this path")
    impact_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    package_parser = sub.add_parser(
        "package", help="write a portable evidence package (contract, trust chain, deliverables, HTML report)"
    )
    package_parser.add_argument("case", help="case directory (must be committed and attested)")
    package_parser.add_argument("--out", required=True, help="directory to write the package into")
    package_parser.add_argument("--lang", choices=("en", "zh", "auto"), default="en", help="README and report language (default: en)")
    package_parser.add_argument("--force", action="store_true", help="replace a non-empty output directory")
    package_parser.add_argument(
        "--include-source",
        dest="include_source",
        action="store_true",
        help="also copy the grounded source document into the package",
    )
    package_parser.add_argument(
        "--include-figures",
        dest="include_figures",
        action="store_true",
        help="also copy generated figures (SVG + figures.json) into the package",
    )
    package_parser.add_argument("--json", action="store_true", help="emit the manifest JSON instead of a summary")

    verify_package_parser = sub.add_parser(
        "verify-package", help="check a package's digests and trust-chain cross-references"
    )
    verify_package_parser.add_argument("package_dir", help="package directory (contains manifest.json)")
    verify_package_parser.add_argument("--lang", choices=("en", "zh", "auto"), default="en", help="output language (default: en)")
    verify_package_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    bundle_parser = sub.add_parser("bundle", help="aggregate several cases into one paper bundle")
    bundle_parser.add_argument("root", help="directory holding bundle.yaml and the case directories")
    bundle_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    bundle_parser.add_argument("--out", default=None, help="write the Markdown bundle report to this path")
    bundle_parser.add_argument(
        "--lang",
        choices=("en", "zh", "auto"),
        default="en",
        help="bundle report language (default: en; auto uses the machine system language)",
    )

    workspace_parser = sub.add_parser("workspace", help="audit a workspace: every case, argument chains, shared evidence, drift")
    workspace_parser.add_argument("root", help="workspace directory (contains workspace.yaml and/or case directories)")
    workspace_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    workspace_parser.add_argument("--format", choices=("md", "html"), default="md", help="report format (default: md; html is a self-contained page)")
    workspace_parser.add_argument("--out", default=None, help="write the workspace report to this path (Markdown, HTML, or JSON with --json)")
    workspace_parser.add_argument(
        "--lang",
        choices=("en", "zh", "auto"),
        default="en",
        help="workspace report language (default: en; auto uses the machine system language)",
    )

    install_parser = sub.add_parser("install-skills", help="install the bundled skills into agent skill directories")
    install_parser.add_argument("--source", default=None, help="skills directory to install from (default: the skills shipped with geoarg)")
    install_parser.add_argument(
        "--dest",
        action="append",
        default=None,
        help="target skills directory (repeatable; default: every existing ~/.dsh/skills, ~/.claude/skills, ./.dsh/skills, ./.claude/skills)",
    )
    install_parser.add_argument("--check", action="store_true", help="compare installed copies and report drift instead of writing")
    install_parser.add_argument("--link", action="store_true", help="symlink instead of copying (falls back to copying)")
    install_parser.add_argument("--dry-run", action="store_true", help="print the planned actions")
    install_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    doctor_parser = sub.add_parser("doctor", help="self-check the engine, its dependencies, and installed skills")
    doctor_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    ground_parser = sub.add_parser("ground", help="verify transcribed quotes against a source document")
    ground_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    ground_parser.add_argument("--pdf", default=None, help="path to the source PDF (legacy alias of --source)")
    ground_parser.add_argument("--source", default=None, help="path to the source document (PDF, DOCX, HTML, Markdown, or text)")
    ground_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="exit zero even when some declared quotes are not grounded (the old default)",
    )
    ground_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    attest_parser = sub.add_parser("attest", help="bind the committed record to the rendered report/cards and judgment")
    attest_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    attest_parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="glob for a deliverable to bind (repeatable; default: report.* and card.*)",
    )
    attest_parser.add_argument(
        "--judgment-file",
        dest="judgment_files",
        action="append",
        default=None,
        help="judgment file to bind (repeatable)",
    )
    attest_parser.add_argument("--note", default=None, help="free text recorded with the attestation")
    attest_parser.add_argument("--registry", default=None, help="registry directory (default: <case>/.geoarg/registry)")
    attest_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    anchor_parser = sub.add_parser("anchor", help="write an external-checkpoint file over the current ledger head")
    anchor_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    anchor_parser.add_argument("--out", default=None, help="checkpoint path (default: <case>/.geoarg/anchor.json)")
    anchor_parser.add_argument("--note", default=None, help="free text recorded with the checkpoint")
    anchor_parser.add_argument("--registry", default=None, help="registry directory (default: <case>/.geoarg/registry)")
    anchor_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    ledger_parser = sub.add_parser("ledger", help="show the hash-chained ledger entries")
    ledger_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    ledger_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    schema_parser = sub.add_parser("schema", help="list the bundled JSON Schemas, print one, or validate a file")
    schema_parser.add_argument("name", nargs="?", default=None, help="schema name to print (argument, evidence, test, bundle, workspace, attestation, anchor, domain)")
    schema_parser.add_argument("--list", action="store_true", help="list the bundled schema names")
    schema_parser.add_argument("--validate", default=None, metavar="FILE", help="validate a JSON or YAML file against the named schema")
    schema_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")

    return parser


