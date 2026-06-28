# Rule 00 — The Only Source of Truth + Build Constraints

## The law

The ONLY source of truth for the cave-teams build is the maintainer's **`THE-ONLY-SOURCE-OF-TRUTH.md`** (kept locally) — it contains ONLY the maintainer's verbatim words. Build to that file. **Never write your own words into it** (the single exception: a line labelled `QUESTION CLAUDE ASKED`).

These rules (`01`, `02`, and their diagrams) are the **derived spec** — a synthesis of the file, grounded in cave's real API (every box cites a real cave call). If a diagram ever contradicts the file, **the file wins** — fix the diagram.

## The constraints (from the file, in force)

- cave-teams **is USED BY / JOINS WITH cave**. It **MAKES** things (teams, topologies, a cave server). It does **not** require a cave already running — **it makes one**.
- **Standalone = depends on `cave` + `chain-ontology` ONLY.** No heaven / sdna / our-other-stuff in the core. Nothing pre-running.
- **Never reimplement what cave / SDNA / heaven already have.** The original sin was a "standalone" reimplementation of cave's actor model / inbox / runner. Use cave's.
- **THE MAIN THING: state machines / conditions on MESSAGES.** The algebra / topologies / DSL are a *generator over* that substrate — not the core.
- **No Claude / `claude -p` baked into the core.** `claude -p` + MiniMax are an *example instance*; cave runs **any** agent runtime.
- The currently-published artifacts (PyPI `cave-teams 0.1.1`, `github.com/sancovp/cave-teams`) are the WRONG reimplementation → yank / rebuild.

## How to work

- **REFACTOR, don't delete.** The original conflated an example instance with every abstraction. Neatly *separate* the abstractions. Some pieces collapse into cave (once it's confirmed cave does them); the rest stay, refactored. We don't pre-delete on a guess.
- **Keep these diagrams current** in the same commit as any architectural change (rule 26). The diagrams are front-end / back-end parity: every node maps to a real cave/chain-ontology symbol or a real cave-teams module.

## Canonical references

- cave: the **`cave-harness`** package (import name `cave`).
- chain-ontology: the **`universal-chain-ontology`** package (also re-exported as `sdna.chain_ontology`).
