"""GeoArg: a deterministic contract engine for geological arguments.

The engine turns a structured argument (claim, premises, warrant, ceteris
paribus conditions, defeaters, entailments, evidence records, tests) into a
verdict, an independence report, and a decisive-test shortlist. It is
deterministic on purpose: the verdict must be recomputable from the contract
alone, by anyone, without the model that wrote the contract.

The grounding gate applies the same discipline to transcription: a quote
declared in a contract is checked against the source PDF before it can count
as accepted evidence.
"""

__version__ = "0.2.0"
