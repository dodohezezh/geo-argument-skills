# Security policy

## Supported versions

Security and trust-layer fixes are applied to the latest minor release
(currently `1.12.x`). Older versions are not maintained.

## What the trust layer does and does not prove

`commit`, `attest` and `anchor` make local records internally consistent and
detect later edits to inputs, engine, ledger, deliverables and checkpoints. They
are **not** digital signatures or trusted timestamps: anyone who controls the
files can rewrite the whole chain. An external checkpoint (`verify --anchor
<file>`) only helps when the copy was kept somewhere outside the repository.

## Reporting a problem

- Open a private security advisory on the repository if one is available, or
  contact the maintainers listed in `pyproject.toml`.
- Do not include credentials, private case data, or unpublished manuscripts in a
  public issue.
- A useful report includes: affected version (`geoarg --version`), platform,
  the exact command, a minimal case directory if possible, expected vs actual
  behavior, and whether the problem lets `verify` pass when it should fail.
