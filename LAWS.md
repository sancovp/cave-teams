# cave-teams agent-composition algebra — LAWS

Carrier **A** = Links (`execute(context) -> LinkResult`). A Link is a state-transformer over the shared
context. Operators (`cave_teams.algebra`): `skip` 1 · `seq` ; · `par` ∥ · `choice` + · `gate` μ ·
`dovetail` ⋈ · `lift` ⟦·⟧ · `team`. **A is CLOSED under every operator** (a `Chain` IS a `Link`) —
agent = team = agent.

All laws below are **mechanically verified** in `test_algebra_laws.py` (the first agent proofs).

## `;` sequential — monoid (non-commutative)
- **assoc:** `(a ; b) ; c  ≡  a ; (b ; c)`
- **ident:** `1 ; a  ≡  a  ≡  a ; 1`
- **order:** `a ; b  ≢  b ; a` — the previous link's `output` feeds the next.
- **normal form:** in the DSL, `>>` flattens plain Chains on both sides, so associativity is *structural*:
  `(a >> (b >> c)).links == ((a >> b) >> c).links == [a, b, c]` (`gate`/parallel-blocks keep their boundary;
  use `team(...)` to force a nested sub-chain).

## `∥` parallel — commutative monoid
- **assoc:** `(a ∥ b) ∥ c  ≡  a ∥ (b ∥ c)`
- **comm:** `a ∥ b  ≡  b ∥ a` — concurrent; the merge folds each branch's new/changed context keys.
- **ident:** `1 ∥ a  ≡  a`

## `+` choice (guarded)
`choice([(g₁,a₁),(g₂,a₂),…], d)` runs the **first** `aᵢ` with `gᵢ(ctx)` true, else `d`. Guards are
arbitrary Python over the context — the open, Turing-complete branch.

## `μ` gate (bounded fixpoint)
`gate(body, φ)` = run `body`, then `φ`; repeat until `φ` sets `ctx[approval_key]` truthy, or `max_cycles`
(then BLOCKED). **Unrolls:** `gate(body,φ) ≡ body ; φ ; (approved ? 1 : gate(body,φ))`.
`duo(a, p, ovp) ≡ gate(a ; p, ovp)`.

## `⋈` dovetail (typed data-flow joint)
`a ⋈[D] b ≡ a ; transform(D) ; b`, where `transform(D)` = load `file_inputs` (>10k → `"read {path}"`
pointer), **validate** `expected_outputs` (missing ⇒ ERROR), then extract `input_map` (dot-notation)
into the next named inputs. **Control plane (`;`) and data plane (`D`) cleanly separated.**

## `⟦·⟧` lift (inclusion of the zoo)
`⟦obj⟧` embeds any runnable into A: a Link passes through (`⟦Link⟧ = Link`, idempotent); a heaven
agent / callable / `.send` object is wrapped (its reply → context). Homomorphic on the output channel.

## closure (the homoiconic law)
For any composition `G = op(a,b,…)`: `G ∈ A`, and `run(team(G)) ≡ run(G)`. **agent = team = agent.**
This is what makes runtime stacking sound — a team is a Link, so it composes/nests with no special case.

## Agent proofs (Phase 5) — mechanically verified in `test_agent_proofs.py`
An *agent proof* = a mechanically-checked claim about a composition's behaviour holding for all
representative inputs (an equation, a safety property, or a liveness property).
- ✅ **Termination of μ (liveness):** `gate` always halts, bounded by `max_cycles` — never hangs.
- ✅ **Gate-soundness (safety):** `gate` = SUCCESS ⟺ `φ` approved; = BLOCKED ⟺ `max_cycles` exhausted.
- ✅ **Distribution:** `a ; (b + c) ≡ (a;b) + (a;c)` when the guard reads input (not `a`'s output).

### Still open (ongoing research)
- **Distribution boundary:** the law FAILS for output-guards (the guard can't read `a`'s output in the
  `(a;b)+(a;c)` form) — characterize exactly when it holds.
- **Refinement:** `a ⊑ b` (a refines b) and monotonicity of the operators under `⊑`.
- **Compositional cost / typing:** lift the Dovetail type-checking to a static pass over an expression.
