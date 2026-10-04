#!/usr/bin/env python3
"""Enforce the dependency rule: mods -> common, never mod -> mod.

For every mods/<name>/ (or just the named ones) it checks that
  - `requires` in mod.json is only the platform mod ("core"): no mod depends on another mod;
  - every `sources` entry stays in the mod's own src/ or in common/src/ (after normalising);
  - every quoted #include / .include in the mod's src/ that resolves to a file stays in the mod or common/;
  - no source text names another mod's directory (`mods/<other>`).
Usage: check_boundaries.py [--root DIR] [mod ...]. Exits 1 and lists violations."""
import argparse
import json
import os
import re
import sys

ALLOWED_REQUIRES = {"core"}
INC = re.compile(r'^\s*(?:#\s*include\s*"([^"]+)"|\.include\s+"([^"]+)")', re.M)


def inside(path, base):
    path, base = os.path.realpath(path), os.path.realpath(base)
    return path == base or path.startswith(base + os.sep)


def resolve(root, name, rel):
    """Where a path written in mod `name` points once staged: `common/...` is the repo's common/,
    anything else is relative to mods/<name>/."""
    base = root if rel.replace("\\", "/").startswith("common/") else os.path.join(root, "mods", name)
    return os.path.normpath(os.path.join(base, rel))


def check_mod(root, name):
    errs = []
    mdir = os.path.join(root, "mods", name)
    common = os.path.join(root, "common")
    try:
        with open(os.path.join(mdir, "mod.json")) as f:
            mod = json.load(f)
    except (OSError, ValueError) as e:
        return ["%s: cannot read mod.json: %s" % (name, e)]
    for r in mod.get("requires", []):
        if r not in ALLOWED_REQUIRES:
            errs.append("%s: requires %r; mods may only require %s" % (name, r, sorted(ALLOWED_REQUIRES)))
    own_src, com_src = os.path.join(mdir, "src"), os.path.join(common, "src")
    for s in mod.get("sources", []):
        p = resolve(root, name, s)
        if not (inside(p, own_src) or inside(p, com_src)):
            errs.append("%s: source %r is outside src/ and common/src/" % (name, s))
    others = [d for d in os.listdir(os.path.join(root, "mods")) if d != name]
    for dp, _, files in os.walk(own_src):
        for fn in files:
            if not fn.endswith((".c", ".h", ".s", ".S", ".inc")):
                continue
            path = os.path.join(dp, fn)
            rel = os.path.relpath(path, root)
            with open(path, errors="replace") as f:
                text = f.read()
            for m in INC.finditer(text):
                inc = m.group(1) or m.group(2)
                cands = [os.path.join(dp, inc), resolve(root, name, inc)]
                hit = next((c for c in cands if os.path.exists(c)), None)
                if hit is None:
                    continue  # system header or generated file: not our business
                if not (inside(hit, mdir) or inside(hit, common)):
                    errs.append("%s: includes %r, which leaves the mod and common/" % (rel, inc))
            for o in others:
                if re.search(r"mods/%s\b" % re.escape(o), text):
                    errs.append("%s: refers to another mod (mods/%s)" % (rel, o))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("mods", nargs="*")
    a = ap.parse_args(argv)
    mods = a.mods or sorted(d for d in os.listdir(os.path.join(a.root, "mods"))
                            if os.path.isfile(os.path.join(a.root, "mods", d, "mod.json")))
    errs = [e for m in mods for e in check_mod(a.root, m)]
    for e in errs:
        print("boundary:", e, file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
