"""Install the bundled skills into agent skill directories.

A wheel ships the skills as ``geoarg/_skills``. An editable checkout falls back
to the repository's ``skills/`` tree. Installation is a plain copy (or a
symlink), so ``--check`` can compare digests and report drift.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

REQUIRED_ENGINE = "1.8.0"


def bundled_root() -> Path | None:
    candidate = Path(__file__).resolve().parent / "_skills"
    return candidate if candidate.is_dir() else None


def source_root(explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if (root / "geology").is_dir():
            return root
        raise FileNotFoundError(f"{root} does not contain a geology/ directory")
    bundled = bundled_root()
    if bundled is not None:
        return bundled
    repository = Path(__file__).resolve().parents[2] / "skills"
    if (repository / "geology").is_dir():
        return repository
    raise FileNotFoundError("skills not found: reinstall geoarg or pass --source <repo>/skills")


def candidates() -> list[tuple[str, Path]]:
    home = Path.home()
    roots: list[tuple[str, Path]] = [
        ("dsh-home", home / ".dsh" / "skills"),
        ("claude-home", home / ".claude" / "skills"),
    ]
    for ancestor in (Path.cwd(), *Path.cwd().parents):
        if (ancestor / ".dsh" / "skills").is_dir():
            roots.append((f"dsh-project:{ancestor.name}", ancestor / ".dsh" / "skills"))
        if (ancestor / ".claude" / "skills").is_dir():
            roots.append((f"claude-project:{ancestor.name}", ancestor / ".claude" / "skills"))
    seen: set[Path] = set()
    unique: list[tuple[str, Path]] = []
    for name, path in roots:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append((name, path))
    return unique


def resolve_targets(dest: list[str] | None) -> list[tuple[str, Path]]:
    if dest:
        return [("dest", Path(item).expanduser().resolve()) for item in dest]
    return [(name, path) for name, path in candidates() if path.is_dir()]


def skill_dirs(source: Path) -> list[Path]:
    return sorted(path for path in (source / "geology").iterdir() if (path / "SKILL.md").is_file())


def tree_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(entry for entry in directory.rglob("*") if entry.is_file()):
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        digest.update(relative + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def plan(source: Path, targets: list[tuple[str, Path]]) -> list[dict]:
    rows = []
    for target_name, target in targets:
        for skill in skill_dirs(source):
            rows.append(
                {
                    "target": target_name,
                    "root": str(target),
                    "skill": skill.name,
                    "action": "install",
                    "source": str(skill),
                    "digest": tree_digest(skill),
                }
            )
    return rows


def apply(rows: list[dict], link: bool = False) -> list[dict]:
    reports = []
    for row in rows:
        source = Path(row["source"])
        target = Path(row["root"]) / row["skill"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
        action = "install"
        if link:
            try:
                target.symlink_to(source, target_is_directory=True)
                action = "link"
            except OSError:
                shutil.copytree(source, target)
        else:
            shutil.copytree(source, target)
        reports.append({**row, "action": action, "digest": tree_digest(target)})
    return reports


def check(source: Path, targets: list[tuple[str, Path]]) -> list[dict]:
    rows = []
    for target_name, target in targets:
        for skill in skill_dirs(source):
            installed = target / skill.name
            if not installed.is_dir():
                status = "missing"
            elif tree_digest(installed) != tree_digest(skill):
                status = "modified"
            else:
                status = "ok"
            rows.append({"target": target_name, "root": str(target), "skill": skill.name, "status": status})
    return rows


def _version_tuple(text: str) -> tuple[int, ...]:
    parts = []
    for item in text.split("."):
        digits = "".join(character for character in item if character.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def environment() -> list[dict]:
    from . import __version__

    checks: list[dict] = []
    engine_ok = _version_tuple(__version__) >= _version_tuple(REQUIRED_ENGINE)
    detail = f"{__version__} (skills require {REQUIRED_ENGINE} or newer)"
    if not engine_ok:
        detail = f"{__version__} is older than {REQUIRED_ENGINE}; upgrade before trusting the skills"
    checks.append({"name": "engine", "ok": engine_ok, "detail": detail})

    info = sys.version_info
    checks.append({"name": "python", "ok": info >= (3, 11), "detail": f"{info.major}.{info.minor}.{info.micro} (>= 3.11)"})

    for module, label in (("yaml", "PyYAML"), ("pypdf", "pypdf"), ("docx", "python-docx")):
        try:
            __import__(module)
            ok, detail = True, "importable"
        except ImportError:
            ok = False
            detail = "missing (pip install geoarg[report])" if module == "docx" else "missing (pip install geoarg)"
        checks.append({"name": label, "ok": ok, "detail": detail})

    try:
        source = source_root(None)
    except FileNotFoundError as exc:
        checks.append({"name": "skills source", "ok": False, "detail": str(exc)})
        return checks
    checks.append({"name": "skills source", "ok": True, "detail": str(source)})

    roots = resolve_targets(None)
    if not roots:
        checks.append(
            {
                "name": "installed skills",
                "ok": False,
                "detail": "no skill directory found; run geoarg install-skills --dest <dir>",
            }
        )
        return checks
    rows = check(source, roots)
    drifted = [row for row in rows if row["status"] != "ok"]
    detail = "in sync" if not drifted else f"{len(drifted)} of {len(rows)} differ; run geoarg install-skills"
    checks.append({"name": "installed skills", "ok": not drifted, "detail": detail})
    return checks
