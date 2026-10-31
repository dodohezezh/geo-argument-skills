"""Command line interface for the GeoArg contract engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import commit, verify
from .contract import ContractError, load_case, validate
from .ground import GroundError, ground_records, load_ledger, validate_grounding, write_ledger
from .hitting import decisive_events
from .independence import report as independence_report
from .judge import judge
from .report import render, render_docx


def _emit_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


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
        "report": "write the report (one-page brief in Word by default)",
    }
    for name, help_text in specs.items():
        sub_parser = sub.add_parser(name, help=help_text)
        sub_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
        sub_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
        if name in ("commit", "verify"):
            sub_parser.add_argument("--registry", default=None, help="registry directory (default: <case>/.geoarg/registry)")
        if name == "report":
            sub_parser.add_argument("--format", choices=("docx", "md"), default="docx", help="output format (default: docx)")
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
                help="output path (default: <case>/report.docx for docx, stdout for md)",
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

    ground_parser = sub.add_parser("ground", help="verify transcribed quotes against a source PDF")
    ground_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
    ground_parser.add_argument("--pdf", required=True, help="path to the source PDF")
    ground_parser.add_argument("--strict", action="store_true", help="exit non-zero if any declared quote is not grounded")
    ground_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    return parser


def _system_language() -> str:
    """Return the machine's UI language as a report language code ("zh" or "en")."""
    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "zh" if (lang_id & 0x3FF) == 0x04 else "en"
    except Exception:  # pragma: no cover - non-Windows fallback
        pass
    import locale

    try:
        code = (locale.getlocale()[0] or "").lower()
    except (TypeError, ValueError):
        code = ""
    return "zh" if code.startswith("zh") or "chinese" in code else "en"


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "install-skills":
        return _cmd_install_skills(args)
    if args.cmd == "doctor":
        return _cmd_doctor(args)
    try:
        case = load_case(args.case)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "check":
        problems = validate(case)
        warnings: list[str] = []
        try:
            grounding_problems, warnings = validate_grounding(case, load_ledger(case.root))
        except GroundError as exc:
            grounding_problems = [f"grounding ledger unreadable: {exc}"]
        problems.extend(grounding_problems)
        if args.json:
            _emit_json({"ok": not problems, "problems": problems, "warnings": warnings})
        else:
            for problem in problems:
                print(f"PROBLEM: {problem}")
            for warning in warnings:
                print(f"WARNING: {warning}")
            print(f"{'FAIL' if problems else 'OK'}  {case.claim.get('id')}  ({len(problems)} problem(s))")
        return 1 if problems else 0

    if args.cmd == "judge":
        result = judge(case)
        if args.json:
            _emit_json(result)
        else:
            print(f"{result['verdict']}  {result['claim_id']}  ({result['rule_version']})")
            for bucket in ("hard", "soft", "pending"):
                for reason in result["reasons"][bucket]:
                    print(f"  [{bucket}] {reason}")
            for flag in result["flags"]:
                print(f"  flag: {flag}")
        return 0

    if args.cmd == "independence":
        payload = independence_report(case)
        if args.json:
            _emit_json(payload)
        else:
            print(f"n_eff = {payload['n_eff']} / {payload['n_records']} records (mean rho = {payload['mean_rho']})")
            for warning in payload["warnings"]:
                print(f"  warning: {warning}")
            if payload["declared_calibration_not_attached"]:
                print(f"  declared but unattached: {payload['declared_calibration_not_attached']}")
        return 0

    if args.cmd == "hit-set":
        payload = decisive_events(case)
        if args.json:
            _emit_json(payload)
        else:
            print(f"base verdict: {payload['base_verdict']}")
            for event in payload["events"]:
                test = event["test"]
                if isinstance(test, list):
                    test = ", ".join(str(t) for t in test)
                print(f"  {test} (power={event['power']}) -> {event['resulting_verdict']}: {event['label']}")
            print(f"  note: {payload['note']}")
        return 0

    if args.cmd == "ground":
        problems = validate(case)
        if problems:
            for problem in problems:
                print(f"PROBLEM: {problem}")
            print("refusing to ground an invalid contract", file=sys.stderr)
            return 2
        try:
            ledger = ground_records(case, args.pdf)
        except GroundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        path = write_ledger(case, ledger)
        if args.json:
            _emit_json({"ledger": ledger, "path": str(path)})
        else:
            extracted = ledger["extracted"]
            text_layer = "yes" if extracted["text_layer"] else "no"
            print(
                f"pdf: {ledger['pdf']['path']} ({extracted['extractor']}, {extracted['pages']} pages, "
                f"{extracted['chars']} chars, text layer: {text_layer})"
            )
            rate = ledger["acceptance_rate"]
            rate_text = "n/a" if rate is None else f"{rate:.3f}"
            print(f"acceptance rate: {rate_text} ({ledger['grounded']}/{ledger['drafted']} drafted quotes grounded)")
            for rid, entry in ledger["records"].items():
                if entry["status"] == "no-locator":
                    print(f"  {entry['status']:<14} {rid}")
                    continue
                found = entry.get("found_page")
                declared = entry.get("page")
                suffix = f" (declared page {declared})" if entry["status"] == "page-mismatch" else ""
                print(f"  {entry['status']:<14} {rid}  page {found or declared}{suffix}")
            print(f"ledger: {path}")
        failed = ledger["drafted"] - ledger["grounded"]
        return 1 if args.strict and failed else 0

    if args.cmd == "commit":
        problems = validate(case)
        if problems:
            for problem in problems:
                print(f"PROBLEM: {problem}")
            print("refusing to commit an invalid contract", file=sys.stderr)
            return 2
        try:
            record, path = commit(case.root, args.registry)
        except ContractError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            _emit_json({"record": record, "path": str(path)})
        else:
            print(f"committed {record['verdict']} for {record['claim_id']} -> {path}")
            grounding = record.get("grounding")
            if grounding:
                print(f"grounding: acceptance rate {grounding['acceptance_rate']} ({grounding['grounded']}/{grounding['drafted']})")
        return 0

    if args.cmd == "verify":
        ok, problems, record = verify(case.root, args.registry)
        if args.json:
            _emit_json({"ok": ok, "problems": problems, "record": record})
        else:
            print(f"{'OK' if ok else 'MISMATCH'}  committed verdict: {record.get('verdict') if record else 'n/a'}")
            for problem in problems:
                print(f"  {problem}")
        return 0 if ok else 1

    if args.cmd == "report":
        if args.format == "docx":
            target = Path(args.out) if args.out else Path(case.root) / "report.docx"
            lang = _system_language() if args.lang == "auto" else args.lang
            render_docx(case, target, lang, brief=args.brief)
            print(f"wrote {target}")
        else:
            lang = _system_language() if args.lang == "auto" else args.lang
            markdown = render(case, lang, brief=args.brief)
            if args.out:
                Path(args.out).write_text(markdown, encoding="utf-8")
                print(f"wrote {args.out}")
            else:
                print(markdown)
        return 0

    return 0  # pragma: no cover


def _cmd_install_skills(args: argparse.Namespace) -> int:
    from . import install as installer

    try:
        source = installer.source_root(args.source)
        targets = installer.resolve_targets(args.dest)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not targets:
        print("error: no skill directory found. Checked:", file=sys.stderr)
        for name, path in installer.candidates():
            print(f"  {name}: {path}", file=sys.stderr)
        print("Install into a specific directory with --dest <dir>.", file=sys.stderr)
        return 2
    if args.check:
        rows = installer.check(source, targets)
        if args.json:
            _emit_json(rows)
        else:
            for row in rows:
                print(f"{row['status']:<9} {row['root']}  {row['skill']}")
        drifted = [row for row in rows if row["status"] != "ok"]
        if not args.json:
            print("skills in sync" if not drifted else f"{len(drifted)} of {len(rows)} skill(s) differ")
        return 0 if not drifted else 1
    rows = installer.plan(source, targets)
    if args.dry_run:
        for row in rows:
            print(f"would {row['action']}: {row['root']}  {row['skill']}")
        return 0
    reports = installer.apply(rows, link=args.link)
    if args.json:
        _emit_json(reports)
    else:
        for row in reports:
            print(f"{row['action']:<7} {row['root']}  {row['skill']}  {row['digest'][:12]}")
        print(f"installed {len(reports)} skill copy(-ies) from {source}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from . import install as installer

    checks = installer.environment()
    if args.json:
        _emit_json(checks)
    else:
        for check in checks:
            mark = "ok  " if check["ok"] else "FAIL"
            print(f"{mark} {check['name']}: {check['detail']}")
    failed = [check for check in checks if not check["ok"]]
    if not args.json:
        print("doctor: all checks passed" if not failed else f"doctor: {len(failed)} check(s) failed")
    return 0 if not failed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
