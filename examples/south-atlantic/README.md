# South Atlantic case

A worked GeoArg contract for a plate reconstruction claim: "Africa and South America at M0 can be restored by one Euler rotation." It exists to exercise the contract engine, not to settle the geology.

- `argument.yaml`: claim, premises, warrant, conditions, defeaters, entailments, gaps.
- `evidence.yaml`: three evidence records with coverage and independence annotations.
- `test.yaml`: seven tests, including one that passes but cannot discriminate (`T5`).

The citations are placeholders. Replace them with real records before using this as science; the shape of the contract is what transfers.

Run it:

```bash
geoarg check examples/south-atlantic
geoarg judge examples/south-atlantic
geoarg independence examples/south-atlantic
geoarg hit-set examples/south-atlantic
geoarg report examples/south-atlantic
```

Expected: `check` is clean; the verdict is `UNTESTED` (every test is still `planned`); `independence` reports `n_eff = 1.2 / 3`; `hit-set` lists 13 single outcomes that would retract or suspend the claim.
