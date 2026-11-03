# Prior art for geoarg 1.0

geoarg registers a geological claim as a contract, computes a verdict from typed tests, grounds quotes against source PDFs, and commits the result to a hash-chained ledger. The standards below are analogues and inspirations. None is a compliance target, and none certifies that a claim is true.

## Supply-chain attestations: in-toto and SLSA

in-toto separates a layout, which authorizes steps and functionaries, from link metadata, which records the materials, command, and products of each step, and verifies products against rules ([specs](https://in-toto.io/docs/specs/)). SLSA provenance v1 separates `buildDefinition` (external parameters, resolved dependencies with digest-bearing resource descriptors) from `runDetails` (builder identity, invocation, timestamps); the `predicateType` URI carries the major version, minor changes keep it stable, and consumers must ignore unrecognized fields ([provenance](https://slsa.dev/spec/v1.0/provenance)). SLSA v1.0 also split levels into tracks (build L1 provenance exists, L2 hosted build, L3 hardened) and retired the old 1 to 4 ladder ([levels](https://slsa.dev/spec/v1.0/levels), now superseded by 1.2).

geoarg stores input and engine digests but not what the inputs were. A resolved-inputs list (PDF, test results, rule set) plus a versioned attestation type would let a reviewer reconstruct the verdict instead of trusting a hash. Ignoring unknown fields gives cheap forward compatibility.

## Transparency logs: Rekor and Certificate Transparency

Rekor is an append-only, tamper-resistant log of metadata built on a verifiable data structure; clients query inclusion proofs, and auditors monitor consistency so entries are never mutated or removed ([Rekor](https://docs.sigstore.dev/logging/overview/)). RFC 9162 specifies the underlying Merkle tree, inclusion proofs, and consistency proofs for Certificate Transparency ([RFC 9162](https://datatracker.ietf.org/doc/html/rfc9162)).

geoarg's ledger chains `prev` hashes, which detects edits inside the file. The stated limit is that a registry can be rewritten and a fresh commit clears drift. The missing mechanism is external anchoring: publish the ledger head to a log or timestamp authority the author does not control, store the receipt, and let `verify` check inclusion. The honest claim is "anchored at time T", never "unforgeable".

## Provenance models: PROV-O and C2PA

PROV-O models provenance as entities, activities, and agents, related by `wasGeneratedBy`, `used`, `wasAttributedTo`, and `wasDerivedFrom`, with qualification for finer influence ([PROV-O](https://www.w3.org/TR/2013/REC-prov-o-20130430/)). C2PA binds assertions to an asset through a signed claim and a hard-binding hash, carries earlier manifests as ingredients, distinguishes assertions the signer created from those it gathered, and explicitly does not judge whether provenance data is true, only whether it is well formed, intact, and signed by a trusted signer ([C2PA explainer 2.2](https://spec.c2pa.org/specifications/specifications/2.2/explainer/Explainer.html)).

C2PA's "manifest is not a truth claim" stance matches geoarg's split between contract and verdict. A small PROV-shaped block (claim, judge activity, evidence entities, reviewer agent) would make the card legible to other tools without adopting RDF.

## Content identity: SWHID and gitoid

A core SWHID is `swh:1:<type>:<hash>`, where a content hash is SHA1 over the git blob header plus the bytes, so the identifier names the object independently of any repository; qualifiers add `origin`, `visit`, `anchor`, `path`, and `lines` for context ([SWHID v1.0](https://www.swhid.org/specification/v1.0/5_Core_identifiers/), [qualifiers](https://www.swhid.org/specification/v1.0/6_Qualified_identifiers/)). The IANA gitoid URI scheme is the same construction with an explicit object type and hash algorithm ([gitoid](https://www.iana.org/assignments/uri-schemes/prov/gitoid)).

geoarg cites evidence by path plus a page and sentence. A quote should instead be identified by source digest, page, and quote digest, with the path kept as a human hint. That survives renames, re-downloads, and repository moves, and it makes `ground` results comparable across machines.

## Research-object packaging: RO-Crate and DataCite

An RO-Crate is a directory plus `ro-crate-metadata.json`, a JSON-LD graph whose root dataset has `@id` "./" and links files through `hasPart`; file entities carry size and format ([RO-Crate 1.1](https://www.researchobject.org/ro-crate/specification/1.1/data-entities.html)). The DataCite kernel requires an identifier, creator, title, publisher, publication year, and resource type, with related identifiers and geolocation as optional properties ([DataCite](https://schema.datacite.org/)). FAIR adds findability, accessibility, interoperability, and reuse as design goals ([FAIR](https://doi.org/10.1038/sdata.2016.18)).

bundle.yaml lists claims, not files or provenance. A case manifest that names the author, dates, engine and schema versions, files with digests, and related case ids would make a case self-describing when it is copied out of the repository or deposited for a DOI.

## Evidence certainty: GRADE, RoB 2, PRISMA

GRADE rates certainty per outcome as high, moderate, low, or very low, and requires explicit judgement about risk of bias, imprecision, inconsistency, indirectness, and publication bias, with upgrade reasons for large effects and dose response ([GRADE](https://www.gradeworkinggroup.org/)). Cochrane RoB 2 fixes five domains with signalling questions and three judgements ([RoB 2](https://www.riskofbias.info/)). PRISMA 2020 is a 27-item checklist with a flow diagram, a reporting analogue rather than an appraisal method ([PRISMA](https://www.prisma-statement.org/)).

The transferable move is to replace free-text confidence with a fixed domain list and recorded reasons, then require a sensitivity statement: what happens to the verdict if a premise or test flips. geoarg's effective sample size already exposes one sensitivity knob, but rho is a prior, not a measurement, and the card should say so.

## Argument structure: Toulmin, AIF, Carneades, ASPIC+

Toulmin's layout separates claim, grounds, warrant, backing, qualifier, and rebuttal ([Toulmin](https://doi.org/10.1017/CBO9780511840005)). AIF and its AML serialization give argumentation tools a shared abstract model of information nodes and scheme, conflict, and preference nodes ([AIF](https://doi.org/10.1017/S0269888906001044)). Carneades adds proof standards, critical questions, and burden of proof ([Carneades](https://doi.org/10.1016/j.artint.2007.04.010)). ASPIC+ formalizes strict and defeasible rules, rebutting and undercutting attacks, and preferences ([ASPIC+](https://doi.org/10.1016/j.artint.2012.10.008)).

Several ideas are already in geoarg's contract: `inference.warrant` and `rule_id` carry the warrant, `test_refs` carry backing, `defeaters` already distinguish rebutting from undercutting, and the verdict lattice is a qualifier. The gaps are per-rule critical questions and an explicit preference order; geoarg uses layers and dependencies instead.

## Reproducibility verification: CODECHECK, badging, Whole Tale, Binder

CODECHECK has an independent checker execute the computations behind an article and issue a certificate with a DOI, indexed in a public register ([CODECHECK](https://codecheck.org.uk/), [workflow](https://codecheck.org.uk/guide/community-workflow-overview)). ACM artifact badging distinguishes Available, Functional, and Reusable ([ACM](https://www.acm.org/publications/policies/artifact-review-and-badging-current)). Whole Tale packages data, code, and environment as a publishable tale, and Binder builds a runnable environment from a repository ([Whole Tale](https://wholetale.org/), [Binder](https://mybinder.readthedocs.io/en/latest/about.html)).

The useful analogue is a review run record: a second party ran `verify` on a specific commit digest, dated, with a stated result. That is cheaper than environment capture and gives the `reviewed_by` field evidence it currently lacks.

## Version discipline: JSON Schema, OpenAPI, SemVer

JSON Schema 2020-12 fixes a dialect through `$schema` and identifies schemas by `$id` ([JSON Schema](https://json-schema.org/draft/2020-12)); OpenAPI 3.1 schema objects use that same dialect ([OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.0.html)). SemVer encodes incompatible, additive, and fix changes as major, minor, and patch ([SemVer](https://semver.org/)).

geoarg's convention of moving `SCHEMA_VERSION` and `RULE_VERSION` together is sound but underspecified: what does a major bump do to committed records? A documented rule (major bump requires `migrate`, minor is additive, patch never changes verdicts) plus a short guarantees-by-level page would make the 1.0 promise checkable.

## Borrowable patterns for geoarg 1.0

1. Add an `attestation` block to every commit record: engine version, rule version, schema version, predicate URI, and a resolved-inputs list with digests.
2. Make `verify` ignore unknown fields inside the attestation but fail on any digest mismatch, following the SLSA parsing rule.
3. Add `geoarg verify --anchor`: publish the ledger head hash to an external log or timestamp service, store the receipt, and check inclusion.
4. Identify grounded quotes by source digest, page, and quote digest, keeping the path as a hint; report the triple in `ground` output.
5. Extend the case manifest with author, dates, versions, file digests, and related ids, so a case is self-describing outside the repository.
6. Replace free-text confidence in `card --for reviewer` with fixed domains (source adequacy, independence, calibration, alternatives, scope) and recorded downgrade reasons.
7. Add `geoarg judge --what-if P3=defeated` and record the result, so assumption sensitivity is a computed artifact rather than a paragraph.
8. Give each `W.*` rule a list of critical questions with required tests, and warn in `check` when a question is unanswered.
9. Replace the bare `reviewed_by` name with a review run record: commit digest, verifier, date, command, and result.
10. Publish a short guarantees-by-level page (structural, grounded, reproduced, anchored) and state which level 1.0 claims.

## Do not borrow

Full RDF serialization of PROV-O, X.509 signing and trust lists, an in-repository Merkle tree, and a blockchain add machinery without changing what a reader can check. The ACM badge program, the full PRISMA checklist as a required form, and ASPIC+ preference semantics are heavier than geoarg needs. Anchor and attestation should stay optional; an unanchored ledger that says so is more honest than a signed one that implies guarantees it does not make.
