#!/usr/bin/env python3
"""Rewrite the parameter-descriptor sites in mod/mod.json (Digitakt mk1 OS 1.53).

The firmware keeps one 52-byte descriptor per parameter id at 0x401a9d9c (13 longs: owner, slot,
min, max, default, flags, ..., long-name ptr, group ptr, short-label ptr). Ids 1-3 are unused
"Error" placeholders; this turns them into GRANULAR's DENS, SHAPE and RAND. Fields not listed here
are copied from the stock descriptor of the same slot (BR 0x6e, LEN 0x71, LOOP 0x72), so the
loader's flags/NRPN/LFO-destination numbers stay consistent. The stock bytes come from the user's
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

# id: (copy-from id, slot, min, max, default, name symbol, short symbol)
NEW = {
    1: (0x6e, 0x13, 0, 0x7f00, 0x4000, "lucys_str_dens_long", "lucys_str_dens"),
    2: (0x71, 0x16, 0, 0x7f00, 0x4000, "lucys_str_shape_long", "lucys_str_shape"),
    3: (0x72, 0x17, 0, 0x7f00, 0x0000, "lucys_str_rand_long", "lucys_str_rand"),
}
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
    mod["sites"] = [s for s in mod["sites"] if not lo <= int(s["addr"], 16) < hi]
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
