"""Byte-level hashing helpers shared by the trust layer.

Text files are hashed after normalising CRLF to LF so a record committed from a
Windows working tree still verifies in a clean LF checkout. Binary files (PDF,
DOCX, images) are hashed byte for byte.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_TEXT_SUFFIXES = {
    ".md", ".txt", ".yaml", ".yml", ".json", ".html", ".htm", ".csv",
    ".py", ".toml", ".cff", ".cfg", ".ini", ".gitignore", ".gitattributes",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_text_path(path: Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() in _TEXT_SUFFIXES or name in {".gitignore", ".gitattributes"}


def normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if is_text_path(path):
        data = data.replace(b"\r\n", b"\n")
    return data


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_bytes(normalized_bytes(path))
