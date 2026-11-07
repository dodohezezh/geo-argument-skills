"""Shared CLI helpers: console setup, JSON output, UI language, case validation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .contract import ContractError, load_case, validate


def _emit_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _configure_output() -> None:
    """Force UTF-8 on the Windows console so digests and Chinese text print."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
            if encoding != "utf8":
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):  # pragma: no cover - defensive
            pass


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


def _require_valid(case_root: str | Path, command: str):
    """Load a case and refuse to inspect it when the contract is invalid."""
    try:
        case = load_case(case_root)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None
    invalid = validate(case)
    if invalid:
        for problem in invalid:
            print(f"PROBLEM: {problem}")
        print(f"refusing to {command} an invalid contract", file=sys.stderr)
        return None
    return case


