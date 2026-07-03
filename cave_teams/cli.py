"""
cli.py — `cave-teams`: the cave() metacontrol function as a CLI.

cave() is THE single shell function — every part of the native API is drivable from a plain-data
spec through it. This CLI is that function on argv: give it a spec (a JSON file, `-` for stdin, or
an inline JSON string) and the same phase flags cave() takes, get the same uniform envelope back
as JSON on stdout.

    cave-teams spec.json                          # build + run
    cave-teams spec.json --describe-only          # build + describe, don't run
    cave-teams spec.json --save --name crew       # write to .cave/quarantine/
    cave-teams --goldenize --name crew            # promote quarantine → golden (approval = this call)
    cave-teams --search research                  # search the golden library
    cave-teams '{"op":"golden","name":"crew"}' --context '{"goal":"..."}'
    cave-teams --ops                              # list the registered ops (the instruction set)
    cave-teams --scan .                           # find every .cave project under a root

Exit code: 0 on a success-ish envelope, 1 on construction_error / runtime_error / error.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def _load_spec(arg: str):
    """spec argv → dict: a path to a JSON file, '-' for stdin, or an inline JSON string."""
    if arg == "-":
        return json.loads(sys.stdin.read())
    p = Path(arg)
    if p.exists():
        return json.loads(p.read_text())
    return json.loads(arg)


def main(argv=None) -> int:
    from .cave import cave, registered_ops, registered_fns, scan_caves

    ap = argparse.ArgumentParser(
        prog="cave-teams",
        description="Drive the whole cave-teams API from one door: cave(spec) on argv.")
    ap.add_argument("spec", nargs="?", help="a spec: JSON file path, '-' (stdin), or inline JSON")
    ap.add_argument("--name", help="team name (for --save / --goldenize / the envelope)")
    ap.add_argument("--context", help="initial context as inline JSON (default {})")
    ap.add_argument("--describe-only", action="store_true", help="build + describe, do not run")
    ap.add_argument("--save", action="store_true", help="write the spec to .cave/quarantine/")
    ap.add_argument("--no-execute", action="store_true", help="build only (with --save: save only)")
    ap.add_argument("--goldenize", action="store_true",
                    help="promote .cave/quarantine/<name> → .cave/golden/ (this call IS the approval)")
    ap.add_argument("--search", metavar="QUERY", help="search the golden library")
    ap.add_argument("--ops", action="store_true", help="list registered ops + fns and exit")
    ap.add_argument("--scan", metavar="ROOT", nargs="*", help="scan roots for .cave projects and exit")
    args = ap.parse_args(argv)

    if args.ops:
        print(json.dumps({"ops": registered_ops(), "fns": registered_fns()}, indent=2))
        return 0
    if args.scan is not None:
        print(json.dumps(scan_caves(args.scan or ["."]), indent=2))
        return 0

    kwargs = dict(name=args.name,
                  context=json.loads(args.context) if args.context else None,
                  execute=not (args.no_execute or args.describe_only),
                  save=args.save, goldenize=args.goldenize,
                  describe_only=args.describe_only, search=args.search)
    spec = _load_spec(args.spec) if args.spec else None
    if spec is None and not (args.goldenize or args.search is not None):
        ap.error("a spec is required unless using --goldenize / --search / --ops / --scan")

    res = asyncio.run(cave(spec, **kwargs))
    print(json.dumps(res, indent=2, default=str))
    return 1 if str(res.get("status", "")).endswith("error") or res.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
