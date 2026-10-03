#!/usr/bin/env python3
"""Measure the voice-block scale of the stock render in digiemu (headless).

Needs a firmware home whose +Drive holds /incoming/sine440 (a 48 kHz mono s16 sine,
peak 16384; see out/emu in this repo's notes): it loads that sample on track 1 through the
sample browser, plays it with trig key 1 and, after the voice
synth calls in the render ISR (0x40077fac), reads the per-voice mono blocks at
0x80001a18 + 128 * v (32 x int32, big endian). It prints each block's peak and
the matching source PCM peak from the sample table, so the Q31-vs-s16 scale of
a block can be read off.

    uv run --project ../digiemumac python tests/emu/scale_probe.py

Env: DIGIEMU (default ../digiemumac), FW_DIR (firmware folder), SHOTS (dir for debug PNGs).
"""
import os
import struct
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIGIEMU = os.path.abspath(os.environ.get("DIGIEMU", os.path.join(ROOT, "..", "digiemumac")))
FW = os.environ.get("FW_DIR") or os.path.join(DIGIEMU, "portable", "firmware", "dt1-1.53-9bdd44bb")
AFTER_SYNTH = 0x40077fac          # after both voice-synth calls, before filter/mix
BLOCKS = 0x80001a18               # 8 voice blocks, 128 bytes each
SMP_TAB = 0x403193a0              # 16 bytes a slot: PCM ptr, u16, length, ratio
VOICE = 0x8000edc4                # V(v) = VOICE + 94 * v

sys.path.insert(0, DIGIEMU)
syx = [f for f in os.listdir(FW) if f.endswith(".syx")][0]
os.environ.update({
    "DT2_SYX": os.path.join(FW, syx), "DT2_SECTIONS": FW + "/sections", "DT2_SNAPSHOTS": FW + "/snapshots",
    "DT2_PLUSDRIVE": FW + "/plusdrive.img", "DT2_MAIN_IMG": FW + "/sections/section_3_MAIN_OS.bin",
    "DT2_DEVICES": os.path.join(DIGIEMU, "devices")})
os.chdir(FW)
tk = types.ModuleType("tkinter")
tk.Frame = type("Frame", (), {})
tk.Tk = type("Tk", (), {})
sys.modules["tkinter"] = tk
for n in ("ttk", "messagebox", "filedialog", "font"):
    sys.modules["tkinter." + n] = types.ModuleType("tkinter." + n)
from unicorn import UC_HOOK_CODE  # noqa: E402
import emu.gui as G  # noqa: E402

SNAP = [os.path.join(d, f) for d, _, fs in os.walk(FW + "/snapshots") for f in fs if f == "gui.snap"][0]
# The factory snapshot opens on track A01 SUBAQUATIC with a sample loaded: trig key 1 plays it.
# A step is ~5 ms of emulated time.
PLAN = {600: ("press", 20), 620: ("release", 20), 700: ("encoder", 4, 1),
        800: ("press", 12), 820: ("release", 12),          # YES: the sample browser
        950: ("press", 15), 970: ("release", 15),          # DOWN: incoming
        1050: ("press", 12), 1070: ("release", 12),       # YES: open it
        1150: ("press", 15), 1170: ("release", 15),        # DOWN: sine440
        1250: ("press", 12), 1270: ("release", 12),        # YES: load it
        1700: ("press", 24), 1720: ("release", 24)}        # trig key 1
STEPS = 3200
state = {"n": 0, "rows": []}


def shot(name):
    """The 128x64 framebuffer as a 4x PNG in $SHOTS (for debugging key plans)."""
    import zlib
    fb = E.fb
    rows = b""
    for y in range(64):
        line = b"".join(bytes([0 if fb[y * 128 + x] else 255] * 3) * 4 for x in range(128))
        rows += (b"\0" + line) * 4

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    path = os.path.join(os.environ["SHOTS"], name + ".png")
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 512, 256, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def rd(uc, addr, n):
    return bytes(uc.mem_read(addr, n))


def probe(uc, addr, size, data):
    state["hits"] = state.get("hits", 0) + 1
    if state["n"] < 1700:
        return
    for v in range(8):
        blk = struct.unpack(">32i", rd(uc, BLOCKS + 128 * v, 128))
        peak = max(abs(x) for x in blk)
        if peak:
            vs = VOICE + 94 * v
            slot = rd(uc, vs + 0x5c, 1)[0]
            pos = struct.unpack(">i", rd(uc, vs + 4, 4))[0]
            on = rd(uc, vs + 0x28, 1)[0]
            ptr, _, length, ratio = struct.unpack(">IIII", rd(uc, SMP_TAB + 16 * slot, 16))
            state["rows"].append((state["n"], v, on, slot, pos, peak, ptr, length, ratio))


_spin = G.spin


def spin(m, pc, *args, **kw):
    uc = m.uc
    n = state["n"]
    if n == 0:
        uc.hook_add(UC_HOOK_CODE, probe, begin=AFTER_SYNTH, end=AFTER_SYNTH)
        state["uc"] = uc
    if os.environ.get("SHOTS") and n in (1300, 1600):
        shot("step%d" % n)
    act = PLAN.get(n)
    if act:
        E.inbox.append((act[0], act[1], act[2] if len(act) > 2 else 0))
    state["n"] += 1
    r = _spin(m, pc, *args, **kw)
    if state["n"] >= STEPS:
        E.stop_flag.set()
    return r


G.spin = spin
E = G.Emulator(SNAP, syx=os.environ["DT2_SYX"], realtime=False, audio=True)
E.run()
pcm = E.audio_take()
print("hook hits:", state.get("hits", 0), "audio peak:", max((abs(x) for x in struct.unpack("<%dh" % (len(pcm) // 2), pcm)), default=0))
print("error:", E.error, "steps:", state["n"], "block hits with signal:", len(state["rows"]))
rows = state["rows"]
for r in rows[:6] + rows[len(rows) // 2:len(rows) // 2 + 3] + rows[-3:]:
    print("step %d v%d on=%d slot=%d V+4=%d block_peak=%d (0x%x) ptr=0x%x len=%d ratio=0x%x" % (r[:5] + (r[5], r[5]) + r[6:]))
if rows:
    uc = state["uc"]
    ptr, length = rows[0][6], rows[0][7]
    pcm = struct.unpack(">%dh" % min(length, 48000), rd(uc, ptr, 2 * min(length, 48000)))
    print("source PCM first %d samples: peak %d" % (len(pcm), max(abs(x) for x in pcm)))
    print("max block peak over run: %d  => block/s16 ratio ~ %.1f (65536 = s16<<16)" % (
        max(r[5] for r in rows), max(r[5] for r in rows) / max(1, max(abs(x) for x in pcm))))
