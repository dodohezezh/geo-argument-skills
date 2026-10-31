"""Command line interface for the GeoArg contract engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import commit, verify
from .contract import ContractError, load_case, validate
from .hitting import decisive_events
from .independence import report as independence_report
from .judge import judge
from .report import render


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
        "report": "render a markdown report",
    }
    for name, help_text in specs.items():
        sub_parser = sub.add_parser(name, help=help_text)
        sub_parser.add_argument("case", help="case directory containing argument.yaml, evidence.yaml, test.yaml")
        sub_parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
        if name in ("commit", "verify"):
            sub_parser.add_argument("--registry", default=None, help="registry directory (default: <case>/.geoarg/registry)")
        if name == "report":
            sub_parser.add_argument("--out", default=None, help="write markdown to this path instead of stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        case = load_case(args.case)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "check":
        problems = validate(case)
        if args.json:
            _emit_json({"ok": not problems, "problems": problems})
        else:
            for problem in problems:
                print(f"PROBLEM: {problem}")
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

    if args.cmd == "commit":
        problems = validate(case)
        if problems:
            for problem in problems:
                print(f"PROBLEM: {problem}")
            print("refusing to commit an invalid contract", file=sys.stderr)
            return 2
        record, path = commit(case.root, args.registry)
        if args.json:
            _emit_json({"record": record, "path": str(path)})
        else:
            print(f"committed {record['verdict']} for {record['claim_id']} -> {path}")
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
        markdown = render(case)
        if args.out:
            Path(args.out).write_text(markdown, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(markdown)
        return 0

    return 0  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
