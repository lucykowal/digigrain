#!/usr/bin/env python3
"""Rewrite the parameter-descriptor sites in mod/mod.json (Digitakt mk1 OS 1.53).

The firmware keeps one 52-byte descriptor per parameter id at 0x401a9d9c (13 longs: owner, slot,
min, max, default, flags, ..., long-name ptr, group ptr, short-label ptr). Ids 1-3 are unused
"Error" placeholders; this turns them into GRANULAR's RTIO, SPRD and ENV. Fields not listed here
are copied from the stock descriptor of the same slot (LEN 0x71, LOOP 0x72, PLAY 0x6d), so the
loader's flags/NRPN/LFO-destination numbers stay consistent (their list/icon formatting lives in
per-id RAM objects, which ids 1-3 do not have). It also writes the two label-accessor hook sites
(0x4000fe8a short label, 0x4000feac long name; see mod/page.s). The stock bytes come from the user's
own firmware file (never committed): ELEKLOADER_STOCK or ../Digitakt_OS1.53.syx."""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get("ELEKLOADER_DIR", os.path.join(ROOT, "..", "elekloader")))
from elekloader import devices, syx  # noqa: E402

BASE, STRIDE, MAIN = 0x401a9d9c, 52, 0x40000400
GROUP = 0x401c6afe                       # the stock "Sample" group string

# id: (copy-from id, slot, min, max, default, name symbol, short symbol); values are 8.8 fixed point
NEW = {
    1: (0x71, 22, 0x0040, 0x0800, 0x0100, "digigrain_str_rtio_long", "digigrain_str_rtio"),     # RTIO 0.25..8.00
    2: (0x72, 23, 0, 0x7f00, 0x4000, "digigrain_str_sprd_long", "digigrain_str_sprd"),          # SPRD 0..127
    3: (0x6d, 18, 0, 0x7f00, 0x4000, "digigrain_str_env_long", "digigrain_str_env"),            # ENV 0..127
}
# the label accessors: (address, target); stock = their first two instructions (10 bytes)
HOOKS = [(0x4000fe8a, "digigrain_label_short"), (0x4000feac, "digigrain_label_long"),
         (0x400657ee, "digigrain_readout")]   # the last: id -> readout text (mod/page.s, mod/readout.c)
OWNER = 6                                # not 0-3, so Randomize lists never show them for stock machines


def main():
    path = os.environ.get("ELEKLOADER_STOCK") or os.path.join(ROOT, "..", "Digitakt_OS1.53.syx")
    st = syx.Syx.load(path)
    dev, _ = devices.identify(st.sha256)
    image = st.section(dev.main_section)

    def desc(pid):
        a = BASE + STRIDE * pid - MAIN
        return image[a:a + STRIDE]

    path_json = os.path.join(ROOT, "mod", "mod.json")
    with open(path_json) as f:
        mod = json.load(f)
    lo, hi = BASE + STRIDE * 1, BASE + STRIDE * 4
    hook_addrs = {a for a, _ in HOOKS}
    mod["sites"] = [s for s in mod["sites"]
                    if not lo <= int(s["addr"], 16) < hi and int(s["addr"], 16) not in hook_addrs]
    for a, target in HOOKS:
        mod["sites"].append({"addr": "0x%x" % a, "stock": image[a - MAIN:a - MAIN + 10].hex(),
                             "op": "jmp", "target": target})
    for pid, (src, slot, mn, mx, df, name, short) in NEW.items():
        base = BASE + STRIDE * pid
        stock = desc(pid)
        f = list(struct.unpack(">13I", desc(src)))
        f[0], f[1], f[2], f[3], f[4] = OWNER, slot, mn, mx, df
        mod["sites"] += [
            {"addr": "0x%x" % base, "stock": stock[:40].hex(), "op": "bytes",
             "new": struct.pack(">10I", *f[:10]).hex()},
            {"addr": "0x%x" % (base + 40), "stock": stock[40:44].hex(), "op": "ptr", "target": name},
            {"addr": "0x%x" % (base + 44), "stock": stock[44:48].hex(), "op": "bytes",
             "new": struct.pack(">I", GROUP).hex()},
            {"addr": "0x%x" % (base + 48), "stock": stock[48:52].hex(), "op": "ptr", "target": short},
        ]
    with open(path_json, "w") as f:
        json.dump(mod, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
