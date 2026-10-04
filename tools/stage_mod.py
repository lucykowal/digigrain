#!/usr/bin/env python3
"""Stage mods/<mod> for the elekloader SDK: copy mod.json and src/, link common/ beside them.

The SDK builds one directory. Staging lets a mod's mod.json list `common/src/x.c` in `sources` and
its C/asm say `#include "common/include/x.h"`, while the repo keeps a single copy of common/.
Prints the stage directory. Usage: stage_mod.py <mod> <out-dir> [--root DIR]"""
import argparse
import os
import shutil


def stage(root, mod, out):
    src = os.path.join(root, "mods", mod)
    if not os.path.isfile(os.path.join(src, "mod.json")):
        raise SystemExit("no such mod: %s (no mods/%s/mod.json)" % (mod, mod))
    if os.path.lexists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    shutil.copy(os.path.join(src, "mod.json"), out)
    if os.path.isdir(os.path.join(src, "src")):
        shutil.copytree(os.path.join(src, "src"), os.path.join(out, "src"))
    os.symlink(os.path.join(root, "common"), os.path.join(out, "common"))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mod")
    ap.add_argument("out")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()
    print(stage(a.root, a.mod, os.path.abspath(a.out)))
