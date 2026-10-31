"""GeoArg: a deterministic contract engine for geological arguments.

The engine turns a structured argument (claim, premises, warrant, ceteris
paribus conditions, defeaters, entailments, evidence records, tests) into a
verdict, an independence report, and a decisive-test shortlist. It is
deterministic on purpose: the verdict must be recomputable from the contract
alone, by anyone, without the model that wrote the contract.
"""

__version__ = "0.1.0"
