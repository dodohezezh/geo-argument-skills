---
name: Feature request
about: Propose a capability, a domain pack, a pattern or a documentation change
title: ""
labels: enhancement
assignees: ""
---

**Use case**

What geological argument, review or teaching workflow are you trying to support?
A concrete example is more useful than an abstract feature.

**Proposed behavior**

What should `geoarg` do? Which command (`check`, `judge`, `impact`, `workspace`,
`ground`, `commit`, `figures`, ...) and what output?

**What it must not break**

The engine is deliberately deterministic and offline: verdicts must be
recomputable from the files, the default pipeline must not call the network, and
`contract.validate` stays authoritative. Say whether the proposal changes the
engine digest (and therefore requires re-signing committed cases).

**Alternatives**

Existing commands, external tools or a documentation-only fix you considered.

**Scope**

Is this a small fix, a domain pack/pattern addition, or an engine change? Link
any related issue or case.
