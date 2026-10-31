# skills/geology

Two skills for checking geological arguments. Both are model-invoked: the description decides when they fire, so keep the triggers distinct.

| Skill | What it does | Reach for it when |
| --- | --- | --- |
| [geo-arg-register](./geo-arg-register/SKILL.md) | Fills a GeoArg contract for one claim | the user wants to structure, register, or check an argument |
| [geo-arg-audit](./geo-arg-audit/SKILL.md) | Audits independence and discriminating power | the user asks how strong an argument is, or which test would settle it |

Both lean on the deterministic engine in `scripts/geoarg`. Install it once with `pip install -e .` from the repository root; the skills then call `geoarg check|judge|independence|hit-set|report|commit|verify`, and `geoarg ground <case> --pdf <paper>` whenever transcription-level evidence has quotes to check.

These live in a `geology` bucket rather than `engineering` because the trigger vocabulary (warrant, defeater, ceteris paribus, coverage) is domain-specific. Add new geology skills here with the same layout: `SKILL.md`, `references/`, and a page in `docs/geology/`.
