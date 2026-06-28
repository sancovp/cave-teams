"""
chain_ontology — THE chain ontology for cave-teams (one shared Link class, not a parallel SDNA).

We use the REAL `sdna.chain_ontology` when it's importable (so SDNA's own SDNAC/SDNAFlow/SDNAFlowchain
— which subclass these very classes — are ALREADY cave-teams Links and compose directly), and fall
back to the VENDORED pure copy (`_chain_ontology_vendored.py`) when SDNA isn't present (keeps cave-teams
standalone). Either way `from cave_teams.chain_ontology import Link, Chain, EvalChain, ...` is the one
canonical ontology the whole library builds on. cave-teams adds ConcurrentChain in concurrent.py.
"""

try:
    # the REAL ontology — pure stdlib, but importing the submodule runs sdna/__init__ (heaven code,
    # not a server). When present, SDNAC(Link)/SDNAFlow(Chain)/SDNAFlowchain(EvalChain) share THIS Link.
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
