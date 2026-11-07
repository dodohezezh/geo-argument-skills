"""geoarg command line: parser, dispatch table, and one handler per command."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cli_common import _configure_output, _emit_json, _require_valid, _system_language
from .cli_parser import _build_parser
from .contract import ContractError, explain, load_case, split_draft, validate


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_output()
    if args.cmd == "install-skills":
        return _cmd_install_skills(args)
    if args.cmd == "adopt":
        return _cmd_adopt(args)
    if args.cmd == "new":
        return _cmd_new(args)
    if args.cmd == "patterns":
        return _cmd_patterns(args)
    if args.cmd == "advise":
        return _cmd_advise(args)
    if args.cmd == "domains":
        return _cmd_domains(args)
    if args.cmd == "edit":
        return _cmd_edit(args)
    if args.cmd == "figures":
        return _cmd_figures(args)
    if args.cmd == "sources":
        return _cmd_sources(args)
    if args.cmd == "references":
        return _cmd_references(args)
    if args.cmd == "impact":
        return _cmd_impact(args)
    if args.cmd == "package":
        return _cmd_package(args)
    if args.cmd == "verify-package":
        return _cmd_verify_package(args)
    if args.cmd == "doctor":
        return _cmd_doctor(args)
    if args.cmd == "attest":
        return _cmd_attest(args)
    if args.cmd == "anchor":
        return _cmd_anchor(args)
    if args.cmd == "ledger":
        return _cmd_ledger(args)
    if args.cmd == "schema":
        return _cmd_schema(args)
    if args.cmd == "bundle":
        return _cmd_bundle(args)
    if args.cmd == "workspace":
        return _cmd_workspace(args)
    if args.cmd == "migrate":
        from .judge import judge
        return _cmd_migrate(args)
    try:
        case = load_case(args.case)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.cmd in ("judge", "independence", "hit-set", "report", "card"):
        invalid = validate(case)
        if invalid:
            for problem in invalid:
                print(f"PROBLEM: {problem}")
            print(f"refusing to {args.cmd} an invalid contract", file=sys.stderr)
            return 2

    if args.cmd == "check":
        from .advise import advise, advise_problems
        from .chain import chain_problems as chain_problems_for
        from .ground import GroundError, load_ledger, validate_grounding
        from .judge import judge
        problems = validate(case)
        warnings: list[str] = []
        if args.profile == "draft":
            problems, draft_warnings = split_draft(problems)
            warnings.extend(draft_warnings)
            for filename in ("argument.yaml", "evidence.yaml", "test.yaml"):
                todo_path = case.root / filename
                if todo_path.exists():
                    count = todo_path.read_text(encoding="utf-8").count("TODO")
                    if count:
                        warnings.append(f"{filename}: {count} TODO marker(s) left to fill")
        result = judge(case)
        problems.extend(f"unbacked state: {item}" for item in result["unbacked"])
        warnings.extend(flag for flag in result["flags"] if flag.startswith("derived premise"))
        try:
            grounding_problems, grounding_warnings = validate_grounding(case, load_ledger(case.root))
        except GroundError as exc:
            grounding_problems = [f"grounding ledger unreadable: {exc}"]
            grounding_warnings = []
        problems.extend(grounding_problems)
        warnings.extend(grounding_warnings)
        try:
            problems.extend(chain_problems_for(case.root))
        except Exception as exc:  # a broken workspace must be reported, not crash
            problems.append(f"argument chain: {exc}")
        if args.advise:
            try:
                advice = advise(case.root)
                warnings.extend(advise_problems(advice))
                if advice.get("pack") is None:
                    warnings.append("no domain pack found: run geoarg domains or geoarg new --pattern")
            except ContractError as exc:
                warnings.append(f"domain advice unavailable: {exc}")
        hints = explain(problems) if args.explain else []
        if args.json:
            payload = {"ok": not problems, "problems": problems, "warnings": warnings, "profile": args.profile}
            if hints:
                payload["hints"] = hints
            _emit_json(payload)
        else:
            for problem in hints if args.explain else problems:
                print(f"PROBLEM: {problem}")
            for warning in warnings:
                print(f"WARNING: {warning}")
            print(f"{'FAIL' if problems else 'OK'}  {case.claim.get('id')}  ({len(problems)} problem(s))")
        return 1 if problems else 0

    if args.cmd == "judge":
        from .judge import judge
        result = judge(case)
        if args.json:
            _emit_json(result)
        else:
            print(f"{result['verdict']}  {result['claim_id']}  ({result['rule_version']})")
            for bucket in ("hard", "soft", "pending"):
                for reason in result["reasons"][bucket]:
                    print(f"  [{bucket}] {reason}")
            for item in result["unbacked"]:
                print(f"  [unbacked] {item}")
            for flag in result["flags"]:
                print(f"  flag: {flag}")
        return 0

    if args.cmd == "independence":
        from .independence import report as independence_report
        payload = independence_report(case)
        if args.json:
            _emit_json(payload)
        else:
            print(f"n_eff = {payload['n_eff']} / {payload['n_records']} records (mean rho = {payload['mean_rho']})")
            stress = payload.get("stress") or {}
            if stress:
                print(
                    f"  stress: n_eff ranges {stress['min']} to {stress['max']} as the assumed "
                    "pairwise rho varies from 0 to 1"
                )
            for warning in payload["warnings"]:
                print(f"  warning: {warning}")
            if payload["declared_calibration_not_attached"]:
                print(f"  declared but unattached: {', '.join(payload['declared_calibration_not_attached'])}")
            for excluded in payload["excluded_records"]:
                print(f"  excluded record: {excluded['id']} ({excluded['status']})")
        return 0

    if args.cmd == "hit-set":
        from .hitting import decisive_events
        payload = decisive_events(case)
        if args.json:
            _emit_json(payload)
        else:
            print(f"base verdict: {payload['base_verdict']}")
            for event in payload["events"]:
                test = event["test"]
                if test is None:
                    test = "n/a"
                elif isinstance(test, list):
                    test = ", ".join(str(t) for t in test)
                cost = "n/a" if event.get("cost") is None else f"{event['cost']:g}"
                print(
                    f"  {test} (power={event['power']}, cost={cost}) -> "
                    f"{event['resulting_verdict']}: {event['label']}"
                )
            print(f"  note: {payload['note']}")
        return 0

    if args.cmd == "ground":
        from .ground import GroundError, ground_records, write_ledger
        source = args.source or args.pdf
        if not source:
            print("error: --source (or the legacy --pdf) is required", file=sys.stderr)
            return 2
        problems = validate(case)
        if problems:
            for problem in problems:
                print(f"PROBLEM: {problem}")
            print("refusing to ground an invalid contract", file=sys.stderr)
            return 2
        try:
            ledger = ground_records(case, source)
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
                f"source: {ledger['pdf']['path']} ({extracted['extractor']}, {extracted['pages']} pages, "
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
        if failed and not args.allow_partial:
            print(
                f"error: {failed} declared quote(s) not grounded; rerun with --allow-partial to inspect and continue",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.cmd == "commit":
        from .audit import commit
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
        from .attest import read_attestation
        from .audit import anchor, read_anchor, verify
        ok, problems, record = verify(case.root, args.registry, external_anchor=args.anchor)
        if args.anchor and record is None:
            problems = list(problems) + ["no committed record to check the external anchor against"]
            ok = False
        if args.json:
            _emit_json({"ok": ok, "problems": problems, "record": record})
        else:
            print(f"{'OK' if ok else 'MISMATCH'}  committed verdict: {record.get('verdict') if record else 'n/a'}")
            for problem in problems:
                print(f"  {problem}")
            att = read_attestation(case.root)
            if att is not None:
                print(
                    f"  attestation: {len(att.get('deliverables') or [])} deliverable(s), "
                    f"{len(att.get('judgment') or [])} judgment file(s)"
                )
            anchor_payload = read_anchor(case.root)
            if anchor_payload is not None:
                print(
                    f"  anchor: record {str(anchor_payload.get('record_sha256') or '')[:12]} "
                    f"checkpointed after ledger entry {anchor_payload.get('ledger_count')}"
                )
        return 0 if ok else 1

    if args.cmd == "card":
        from .card import render_card
        lang = _system_language() if args.lang == "auto" else args.lang
        if args.judgment and args.judgment_file:
            print("error: pass either --judgment or --judgment-file, not both", file=sys.stderr)
            return 2
        judgment = args.judgment
        if args.judgment_file:
            try:
                judgment = Path(args.judgment_file).read_text(encoding="utf-8-sig").strip()
            except OSError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
        markdown = render_card(case, lang, args.audience, judgment)
        if args.out:
            Path(args.out).write_text(markdown, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(markdown)
        return 0

    if args.cmd == "report":
        from .figures import load_figures
        from .html import render_html
        from .report import build, build_brief, render, render_docx
        lang = _system_language() if args.lang == "auto" else args.lang
        if args.judgment and args.judgment_file:
            print("error: pass either --judgment or --judgment-file, not both", file=sys.stderr)
            return 2
        judgment = args.judgment
        if args.judgment_file:
            try:
                judgment = Path(args.judgment_file).read_text(encoding="utf-8-sig").strip()
            except OSError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
        if args.format == "docx":
            target = Path(args.out) if args.out else Path(case.root) / "report.docx"
            render_docx(case, target, lang, brief=args.brief, judgment=judgment)
            print(f"wrote {target}")
        elif args.format == "html":
            target = Path(args.out) if args.out else Path(case.root) / "report.html"
            model = build_brief(case, lang, judgment) if args.brief else build(case, lang, judgment)
            if args.figures:
                figures = load_figures(Path(args.figures))
            else:
                default_figures = Path(case.root) / "figures"
                figures = load_figures(default_figures) if default_figures.is_dir() else []
            target.write_text(render_html(model, lang, figures=figures or None), encoding="utf-8")
            print(f"wrote {target}")
        else:
            markdown = render(case, lang, brief=args.brief, judgment=judgment)
            if args.out:
                Path(args.out).write_text(markdown, encoding="utf-8")
                print(f"wrote {args.out}")
            else:
                print(markdown)
        return 0

    return 0  # pragma: no cover


def _cmd_migrate(args: argparse.Namespace) -> int:
    from .migrate import migrate as migrate_case
    try:
        rows = migrate_case(args.case, dry_run=args.dry_run)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(rows)
        return 0
    for row in rows:
        if row["changed"]:
            verb = "would migrate" if args.dry_run else "migrated"
            print(f"{verb} {row['file']}: {row['old']} -> {row['new']}")
        else:
            print(f"already current  {row['file']}")
    return 0


def _cmd_bundle(args: argparse.Namespace) -> int:
    from .bundle import build_bundle, render_bundle
    payload = build_bundle(args.root)
    if args.json:
        _emit_json(payload)
        return 0 if payload["ok"] else 1
    lang = _system_language() if args.lang == "auto" else args.lang
    text = render_bundle(args.root, lang)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0 if payload["ok"] else 1


def _cmd_workspace(args: argparse.Namespace) -> int:
    from .chain import render_workspace, workspace_report
    from .html import render_workspace_html
    payload = workspace_report(args.root)
    if args.json:
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            _emit_json(payload)
        return 0 if payload["ok"] else 1
    lang = _system_language() if args.lang == "auto" else args.lang
    if args.format == "html":
        text = render_workspace_html(payload, lang)
    else:
        text = render_workspace(payload, lang)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0 if payload["ok"] else 1


def _cmd_attest(args: argparse.Namespace) -> int:
    from .attest import attest
    try:
        payload, path = attest(
            args.case,
            include=args.include,
            judgment_files=args.judgment_files,
            note=args.note,
            registry=args.registry,
        )
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json({"attestation": payload, "path": str(path)})
        return 0
    print(
        f"attested {len(payload['deliverables'])} deliverable(s) and "
        f"{len(payload['judgment'])} judgment file(s) for {payload['claim_id']} -> {path}"
    )
    for entry in payload["deliverables"]:
        print(f"  {entry['path']}  {entry['sha256'][:12]}")
    for entry in payload["judgment"]:
        print(f"  judgment: {entry['path']}  {entry['sha256'][:12]}")
    return 0


def _cmd_anchor(args: argparse.Namespace) -> int:
    from .audit import anchor
    try:
        payload, path = anchor(args.case, out=args.out, note=args.note, registry=args.registry)
    except (ContractError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json({"anchor": payload, "path": str(path)})
        return 0
    print(
        f"anchored record {payload['record_sha256'][:12]} at ledger head "
        f"{payload['ledger_head'][:12]} ({payload['ledger_count']} entries) -> {path}"
    )
    print("store this file (or its digest) outside the case directory to keep the checkpoint external")
    return 0


def _cmd_ledger(args: argparse.Namespace) -> int:
    from .audit import ledger_report
    payload = ledger_report(args.case)
    if args.json:
        _emit_json(payload)
        return 0 if payload["ok"] else 1
    for row in payload["entries"]:
        verdict = row["verdict"] or "-"
        print(
            f"{row['index']:>3}  {row['kind']:<12} {row['created_at'] or '-'}  "
            f"{row['claim_id']}  {verdict:<13} {str(row['sha256'])[:12]}"
        )
    for problem in payload["problems"]:
        print(f"PROBLEM: {problem}")
    print(
        f"ledger: {len(payload['entries'])} entries, head {str(payload['head'])[:12]}"
        if payload["entries"]
        else "ledger: empty"
    )
    return 0 if payload["ok"] else 1


def _cmd_schema(args: argparse.Namespace) -> int:
    from . import schemas

    if args.validate is not None:
        if not args.name:
            print("error: schema --validate needs a schema name", file=sys.stderr)
            return 2
        path = Path(args.validate)
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        try:
            text = path.read_text(encoding="utf-8-sig")
            if path.suffix.lower() == ".json":
                instance = json.loads(text)
            else:
                import yaml

                instance = yaml.safe_load(text)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        try:
            problems = schemas.validate_instance(instance, args.name)
        except schemas.SchemaError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            _emit_json({"ok": not problems, "schema": args.name, "path": str(path), "problems": problems})
        elif problems:
            for problem in problems:
                print(f"INVALID: {problem}")
        else:
            print(f"valid: {path} against {args.name}")
        return 0 if not problems else 1

    if args.list or not args.name:
        try:
            names = schemas.list_schemas()
        except schemas.SchemaError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            _emit_json(names)
        else:
            for name in names:
                print(name)
        return 0
    try:
        if args.json:
            _emit_json(schemas.schema_document(args.name))
        else:
            print(schemas.schema_text(args.name), end="")
    except schemas.SchemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _schema_checks() -> list[dict[str, object]]:
    from .audit import anchor
    from . import schemas

    checks: list[dict[str, object]] = []
    try:
        names = schemas.list_schemas()
        expected = ("argument", "evidence", "test", "bundle", "workspace", "attestation", "anchor", "domain")
        missing = [name for name in expected if name not in names]
        checks.append(
            {
                "name": "schemas",
                "ok": not missing,
                "detail": f"{len(names)} schema(s) shipped"
                + (f"; missing {', '.join(missing)}" if missing else ""),
            }
        )
    except schemas.SchemaError as exc:
        checks.append({"name": "schemas", "ok": False, "detail": str(exc)})
    try:
        import jsonschema

        checks.append(
            {
                "name": "jsonschema",
                "ok": True,
                "detail": f"installed ({jsonschema.__version__}); geoarg schema can validate instances",
            }
        )
    except ImportError:
        checks.append(
            {
                "name": "jsonschema",
                "ok": True,
                "detail": "not installed (optional; pip install geoarg[schema])",
            }
        )
    return checks


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

    checks = installer.environment() + _schema_checks()
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


def _cmd_adopt(args: argparse.Namespace) -> int:
    from .adopt import adopt_markdown, render_adoption
    try:
        payload = adopt_markdown(
            args.markdown,
            args.out,
            case_id=args.case_id,
            title=args.title,
            claim=args.claim,
            force=args.force,
        )
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(payload)
    else:
        print(render_adoption(payload), end="")
    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    from .domains import load_domain
    from .scaffold import new_case, render_new_case
    try:
        pack = load_domain(args.dir)
        payload = new_case(
            args.dir,
            args.pattern,
            case_id=args.case_id,
            title=args.title,
            claim=args.claim,
            force=args.force,
            pack=pack,
        )
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(payload)
    else:
        print(render_new_case(payload), end="")
    return 0


def _cmd_edit(args: argparse.Namespace) -> int:
    from .editor import run_editor

    try:
        run_editor(args.case, host=args.host, port=args.port, open_browser=not args.no_browser)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot start the editor: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_figures(args: argparse.Namespace) -> int:
    from .figures import build_figures
    case = _require_valid(args.case, "figures")
    if case is None:
        return 2
    out = Path(args.out) if args.out else Path(args.case) / "figures"
    try:
        payload = build_figures(case, out, lang=args.lang)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(payload)
    else:
        print(f"wrote {len(payload['figures'])} figure(s) to {out}")
        for item in payload["figures"]:
            print(f"  {item['file']}  {item['bytes']} bytes")
    return 0


def _cmd_sources(args: argparse.Namespace) -> int:
    from .references import render_sources, source_gap_problems, source_gaps
    try:
        payload = source_gaps(args.case)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    problems = source_gap_problems(
        payload, require_quote=args.require_quote, require_source=args.require_source
    )
    if args.json:
        payload = dict(payload)
        payload["problems"] = problems
        _emit_json(payload)
    else:
        report = render_sources(payload, args.lang)
        if args.out:
            Path(args.out).write_text(report, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(report, end="")
        for problem in problems:
            print(f"FAIL {problem}")
    return 1 if problems else 0


def _cmd_references(args: argparse.Namespace) -> int:
    from .references import reference_requirements_met, render_references, verify_references
    providers = tuple(part.strip() for part in str(args.providers).split(",") if part.strip())
    try:
        payload = verify_references(
            args.case,
            providers=providers,
            refresh=args.refresh,
            offline=args.offline,
            timeout=args.timeout,
        )
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    problems = reference_requirements_met(payload) if args.require_verified else []
    if args.json:
        payload = dict(payload)
        payload["problems"] = problems
        _emit_json(payload)
    else:
        report = render_references(payload, args.lang)
        if args.out:
            Path(args.out).write_text(report, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(report, end="")
        if args.offline:
            print("(cached snapshot, no network)")
        for problem in problems:
            print(f"FAIL {problem}")
    return 1 if problems else 0


def _cmd_patterns(args: argparse.Namespace) -> int:
    from .domains import load_domain
    from .scaffold import list_patterns, render_patterns
    try:
        pack = load_domain(args.case) if args.case else None
        rows = list_patterns(pack)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(rows)
    else:
        print(render_patterns(rows), end="")
    return 0


def _cmd_advise(args: argparse.Namespace) -> int:
    from .advise import advise, render_advise
    case = _require_valid(args.case, "advise")
    if case is None:
        return 2
    try:
        payload = advise(case)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(payload)
    else:
        print(render_advise(payload, lang=args.lang), end="")
    return 0


def _cmd_domains(args: argparse.Namespace) -> int:
    from .domains import builtin_enums, effective_enums, load_domain, render_domains
    try:
        pack = load_domain(args.case) if args.case else None
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    builtin = builtin_enums()
    effective = effective_enums(pack)
    payload = {
        "builtin": builtin,
        "pack": None
        if pack is None
        else {"name": pack["name"], "path": str(pack["path"]), "values": pack["enums"]},
        "effective": {key: sorted(values) for key, values in effective.items()},
    }
    if args.json:
        _emit_json(payload)
    else:
        print(render_domains(pack, lang=args.lang), end="")
    return 0


def _cmd_impact(args: argparse.Namespace) -> int:
    from .impact import impact_report, load_evidence_file, render_impact, render_workspace_impact, workspace_impact
    if args.workspace:
        from .chain import scan_cases

        bad: list[str] = []
        for case_root in scan_cases(args.root):
            try:
                case = load_case(case_root)
            except ContractError as exc:
                bad.append(f"{case_root.name}: {exc}")
                continue
            for problem in validate(case):
                bad.append(f"{case_root.name}: {problem}")
        if bad:
            for problem in bad:
                print(f"PROBLEM: {problem}")
            print("refusing to impact an invalid workspace", file=sys.stderr)
            return 2
    else:
        case = _require_valid(args.root, "impact")
        if case is None:
            return 2
    try:
        evidence = load_evidence_file(args.add_evidence) if args.add_evidence else None
        if args.workspace:
            if not evidence:
                raise ContractError("--workspace requires --add-evidence with prospective records")
            payload = workspace_impact(args.root, evidence)
            text = render_workspace_impact(payload)
        else:
            payload = impact_report(case, assumptions=args.assume, add_evidence=evidence)
            text = render_impact(payload, lang=args.lang)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        try:
            Path(args.out).write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {args.out}")
    elif not args.json:
        print(text, end="")
    if args.json:
        _emit_json(payload)
    return 0


def _cmd_package(args: argparse.Namespace) -> int:
    from .package import build_package, render_package
    lang = _system_language() if args.lang == "auto" else args.lang
    try:
        payload = build_package(
            args.case,
            args.out,
            lang=lang,
            force=args.force,
            include_source=args.include_source,
            include_figures=args.include_figures,
        )
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(payload)
    else:
        print(render_package(payload, lang=lang), end="")
        print(f"wrote {args.out}")
    return 0


def _cmd_verify_package(args: argparse.Namespace) -> int:
    from .package import render_verify, verify_package
    lang = _system_language() if args.lang == "auto" else args.lang
    try:
        payload = verify_package(args.package_dir)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit_json(payload)
    else:
        print(render_verify(payload, lang=lang), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
