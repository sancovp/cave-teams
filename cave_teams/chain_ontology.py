"""
chain_ontology — THE chain ontology for cave-teams (one shared Link class, not a parallel SDNA).

We use the REAL `sdna.chain_ontology` when it's importable (so SDNA's own SDNAC/SDNAFlow/SDNAFlowchain
— which subclass these very classes — are ALREADY cave-teams Links and compose directly), and fall
back to the VENDORED pure copy (`_chain_ontology_vendored.py`) when SDNA isn't present (keeps cave-teams
standalone). Either way `from cave_teams.chain_ontology import Link, Chain, EvalChain, ...` is the one
canonical ontology the whole library builds on. cave-teams adds ConcurrentChain in concurrent.py.
"""

try:
    # the CANONICAL ontology — universal-chain-ontology (zero-dep). sdna.chain_ontology RE-EXPORTS
    # these very classes, so SDNAC(Link)/SDNAFlow(Chain)/SDNAFlowchain(EvalChain) share THIS Link
    # whenever sdna is present too — one Link across the ecosystem, and importing uco directly
    # keeps `import cave_teams` from dragging sdna/heaven in as a side effect.
    from uco.core import (  # noqa: F401
        LinkStatus, LinkResult, Link, Chain, EvalChain, Compiler, LinkConfig, ConfigLink,
    )
    CHAIN_ONTOLOGY_SOURCE = "uco"
except Exception:
    try:
        # sdna re-export path (same classes as uco; heavier import — heaven code runs)
        from sdna.chain_ontology import (  # noqa: F401
            LinkStatus, LinkResult, Link, Chain, EvalChain, Compiler, LinkConfig, ConfigLink,
        )
        CHAIN_ONTOLOGY_SOURCE = "sdna"
    except Exception:
        # standalone fallback — the vendored verbatim copy (identical ontology, zero coupling)
        from ._chain_ontology_vendored import (  # noqa: F401
            LinkStatus, LinkResult, Link, Chain, EvalChain, Compiler, LinkConfig, ConfigLink,
        )
        CHAIN_ONTOLOGY_SOURCE = "vendored"

__all__ = [
    "LinkStatus", "LinkResult", "Link", "Chain", "EvalChain", "Compiler", "LinkConfig", "ConfigLink",
    "CHAIN_ONTOLOGY_SOURCE",
]
