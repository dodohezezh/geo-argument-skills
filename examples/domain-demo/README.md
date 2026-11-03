# GeoArg example: an external domain pack

This case uses `domain.yaml` to widen the built-in enumerations:

- `domains` adds `quaternary-geology`
- `claim_kinds` adds `age-model`
- `method_types` adds `tephrochronology`

The engine is unchanged. `geoarg check examples/domain-demo` passes because the
nearest `domain.yaml` (this case directory) is merged before validation; move
the case elsewhere without the pack and the same contract fails with unknown
enum values. `geoarg domains examples/domain-demo` shows the effective sets.

The contract is a draft for demonstration; nothing here is committed.
