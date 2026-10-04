#!/usr/bin/env python3
"""Write resample/mod.json (Digitakt mk1 OS 1.53).

The hook sites (synth calls, page layout, LFO destination, value readouts) are the ones digigrain
patches, with digiresample's targets; that is also why the two mods conflict. The two new parameters
take the spare descriptors 1 and 2 (see tools/gen_page_sites.py for the descriptor layout):
  id 1  REC/PLAY  slot 20 (SAMP's word)  0..0x100 (knob value 0 / 1)   default REC
  id 2  SRC       slot 23 (LOOP's word)  0..0x1000 (knob value 0..16)  default 5 (MAIN L+R)
The stock bytes come from the user's own firmware file (never committed): ELEKLOADER_STOCK or
../Digitakt_OS1.53.syx. The hook sites' stock bytes are copied from mod/mod.json."""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get("ELEKLOADER_DIR", os.path.join(ROOT, "..", "elekloader")))
from elekloader import devices, syx  # noqa: E402

BASE, STRIDE, MAIN = 0x401a9d9c, 52, 0x40000400
GROUP = 0x401c6afe                       # the stock "Sample" group string
OWNER = 7                                # not 0-3, so Randomize lists never show them for stock machines

# id: (copy-from id, slot, min, max, default, name symbol, short symbol); values are 8.8 fixed point
NEW = {
    1: (0x6d, 20, 0, 0x0100, 0x0000, "digiresample_str_mode_long", "digiresample_str_mode"),
    2: (0x72, 23, 0, 0x1000, 0x0500, "digiresample_str_src_long", "digiresample_str_src"),
}
# mod/mod.json site (by address) -> digiresample's target symbol
HOOKS = {
    "0x40077f8e": "digiresample_synth_pre",
    "0x40077fa6": "digiresample_synth_all",
    "0x400657cc": "digiresample_layout",
    "0x400a4362": "digiresample_dest_names",
    "0x40065dc8": "digiresample_dest_icon",
    "0x400657ee": "digiresample_readout",
    "0x4000f324": "digiresample_caption",
}


def main():
    path = os.environ.get("ELEKLOADER_STOCK") or os.path.join(ROOT, "..", "Digitakt_OS1.53.syx")
    st = syx.Syx.load(path)
    dev, _ = devices.identify(st.sha256)
    image = st.section(dev.main_section)

    def desc(pid):
        a = BASE + STRIDE * pid - MAIN
        return image[a:a + STRIDE]

    with open(os.path.join(ROOT, "mod", "mod.json")) as f:
        grain = json.load(f)
    mod = {k: grain[k] for k in ("device", "os", "license", "author", "requires")}
    mod.update({
        "id": "digiresample", "version": "0.0.1", "title": "Digiresample", "category": "Machines",
        "description": "Adds a RESAMPLE SRC machine (id 7): D = REC/PLAY drives the RECORDER from the "
                       "sequencer (REC records while the note is held, PLAY plays the buffer through the "
                       "stock voice: TUNE, PLAY, BR, STRT, LEN, LEV), G = the RECORDER's SRC. Conflicts "
                       "with digigrain (same page hooks).",
        "sources": ["resample.c", "readout.c", "machine.s", "synth.s", "page.s"],
        "contribute": [{"to": "core_machines", "order": 51, "data": "00000000",
                        "relocs": [[0, "abs32", "sym:digiresample_machine", 0]]}],
        "resources": {"names": ["machine:7"]},
        "sites": [],
        "subscribe": [{"event": "ev_tick", "fn": "digiresample_tick", "order": 51}],
    })
    for s in grain["sites"]:
        if s["addr"] in HOOKS:
            mod["sites"].append({"addr": s["addr"], "stock": s["stock"], "op": s["op"],
                                 "target": HOOKS[s["addr"]]})
    assert len(mod["sites"]) == len(HOOKS)
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
    with open(os.path.join(ROOT, "resample", "mod.json"), "w") as f:
        json.dump(mod, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
