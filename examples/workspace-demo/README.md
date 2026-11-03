# Workspace demo: two linked arguments

This fixture shows the 0.9 argument-chain and workspace features with the
1.0 trust layer.

- `basement-age` argues that the basement is older than 2.6 Ga from a U-Pb
  zircon measurement.
- `cover-age` argues that the overlying cover is younger than 2.6 Ga. Its
  first premise is `derived` and points at `basement-age` through
  `argument_ref`; the workspace file maps that id to a case directory.
- `workspace.yaml` registers both argument ids, so the chain resolves without
  absolute paths.

Try it from the repository root:

```powershell
geoarg check examples/workspace-demo/basement-age
geoarg check examples/workspace-demo/cover-age
geoarg judge examples/workspace-demo/cover-age
geoarg workspace examples/workspace-demo
```

The cover argument reports `UNTESTED` and the workspace shows one resolved
chain entry. Nothing here is committed or attested; add `commit`, `attest`,
and `anchor` if you want the full trust trail for a real case.
