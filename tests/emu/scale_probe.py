#!/usr/bin/env python3
"""Measure the voice-block scale of the stock render in digiemu (headless).

Needs a firmware home whose +Drive holds /incoming/sine440 (a 48 kHz mono s16 sine,
peak 16384; see out/emu in this repo's notes): it loads that sample on track 1 through the
sample browser, plays it with trig key 1 and, after the voice
synth calls in the render ISR (0x40077fac), reads the per-voice mono blocks at
0x80001a18 + 128 * v (32 x int32, big endian). It prints each block's peak and
the matching source PCM peak from the sample table, so the Q31-vs-s16 scale of
a block can be read off.

    uv run --project ../digiemumac python tests/emu/scale_probe.py          # stock firmware
    GRANULAR=1 FW_DIR=out/emu/home/firmware/<our build> uv run ... scale_probe.py   # our build:
        switches track 1 to GRANULAR first and reports the grain output levels and audio

Env: DIGIEMU (default ../digiemumac), FW_DIR (firmware folder), SHOTS (dir for debug PNGs),
POKE="slot:value,..." (track 1's param words; value = 0..127 knob value, or "0xHHHH" for a raw word).
Slots on GRANULAR: 17 TUNE (centre 16384), 18 ENV, 19 RATE, 21 POS (0..120), 22 RTIO (raw 8.8:
0x0040..0x0800), 23 SPRD, 24 LEV; ENV/RATE/SPRD are 0..127 with noon 64.
"""
import os
import struct
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIGIEMU = os.path.abspath(os.environ.get("DIGIEMU", os.path.join(ROOT, "..", "digiemumac")))
FW = os.environ.get("FW_DIR") or os.path.join(DIGIEMU, "portable", "firmware", "dt1-1.53-9bdd44bb")
GAIN_UNIT = 25916                # stock block = s16 x GAIN_UNIT (measured)
AFTER_SYNTH = 0x40077fac          # after both voice-synth calls, before filter/mix
BLOCKS = 0x80001a18               # 8 voice blocks, 128 bytes each
SMP_TAB = 0x403193a0              # 16 bytes a slot: PCM ptr, u16, length, ratio
VOICE = 0x8000edc4                # V(v) = VOICE + 94 * v

sys.path.insert(0, DIGIEMU)
syx = [f for f in os.listdir(FW) if f.endswith(".syx")][0]
os.environ.update({
    "DT2_SYX": os.path.join(FW, syx), "DT2_SECTIONS": FW + "/sections", "DT2_SNAPSHOTS": FW + "/snapshots",
    "DT2_PLUSDRIVE": FW + "/plusdrive.img", "DT2_MAIN_IMG": FW + "/sections/section_3_MAIN_OS.bin",
    "DT2_DEVICES": FW + "/devices" if os.path.isdir(FW + "/devices") else os.path.join(DIGIEMU, "devices")})   # custom builds carry their own device file
os.chdir(FW)
tk = types.ModuleType("tkinter")
tk.Frame = type("Frame", (), {})
tk.Tk = type("Tk", (), {})
sys.modules["tkinter"] = tk
for n in ("ttk", "messagebox", "filedialog", "font"):
    sys.modules["tkinter." + n] = types.ModuleType("tkinter." + n)
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_PC  # noqa: E402

MAP = {}
if os.environ.get("GRANULAR"):        # symbol addresses of our build, from elekloader's linker
    sys.path.insert(0, os.path.join(ROOT, "..", "elekloader"))
    from elekloader import syx as _syx, devices as _dev, elemod as _em, link as _link
    import glob
    _st = _syx.Syx.load(os.path.join(ROOT, "..", "Digitakt_OS1.53.syx"))
    _d, _r = _dev.identify(_st.sha256)
    _mods = [glob.glob(os.path.join(ROOT, "out", "core", "core-*.elemod"))[0],
             glob.glob(os.path.join(ROOT, "out", "mod", "digigrain-*.elemod"))[0]]
    MAP = _link.link([_em.load_any(m) for m in _mods], _st.section(_d.main_section)).map
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
if os.environ.get("GRANULAR"):                              # our build: switch track 1 to GRANULAR first
    PLAN.pop(1700), PLAN.pop(1720)
    PLAN.update({1450: ("press", 1), 1460: ("press", 20), 1480: ("release", 20), 1490: ("release", 1)})  # FUNC+SRC
    for i, t in enumerate((1600, 1680, 1760, 1840)[:int(os.environ.get("MACHINE_DOWNS", "4"))]):    # DOWN x4 (MACHINE_DOWNS=3: SLICE, 0: stay on ONESHOT)
        PLAN[t], PLAN[t + 20] = ("press", 15), ("release", 15)
    PLAN.update({2000: ("press", 12), 2020: ("release", 12),                                          # YES
                 2300: ("press", 24), 2320: ("release", 24)})                                         # trig key 1
# TURNS="knob:delta:count,..." (knob 1..8 = A..H) turns encoders after the machine is selected;
# every event is 6 steps after the last (the firmware wants small, spaced events)
_t = 2100
for kv in (t for t in os.environ.get("TURNS", "").split(",") if t):
    kn, dl, *cnt = kv.split(":")
    for _ in range(int(cnt[0]) if cnt else 1):
        PLAN[_t] = ("encoder", int(kn), int(dl))
        _t += 6
    _t += 30
if os.environ.get("SITE_COUNTS") or os.environ.get("ARG_TRACE"):            # spike: just look at the SRC page and turn knobs E then C
    PLAN = {}
    for i in range(3):
        PLAN[800 + 6 * i] = ("encoder", 5, 4)
        PLAN[900 + 6 * i] = ("encoder", 3, 4)
STEPS = 4400
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


SITES = [int(x, 16) for x in os.environ.get("SITE_COUNTS", "").split(",") if x]   # addresses to count (hex)
site_hits = {}
ARG_TRACE = [int(x, 16) for x in os.environ.get("ARG_TRACE", "").split(",") if x]   # log (arg1 vtable, arg2) at these entries
arg_seen = set()


def probe(uc, addr, size, data):
    state["hits"] = state.get("hits", 0) + 1
    if state["n"] < (2300 if os.environ.get("GRANULAR") else 1700):
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
            if v == 0 and 70 <= len([r for r in state["rows"] if r[1] == 0]) <= 72:
                print("blk", len([r for r in state["rows"] if r[1] == 0]), "V+4", pos, [x // GAIN_UNIT for x in blk[:12]])
            if v == 0 and peak > 1000000:
                tz = min(((x & -x).bit_length() - 1) if x else 31 for x in blk)
                state["tz"] = min(state.get("tz", 31), tz)
                state["distinct"] = max(state.get("distinct", 0), len(set(blk)))


_spin = G.spin


def spin(m, pc, *args, **kw):
    uc = m.uc
    n = state["n"]
    if n == 0:
        uc.hook_add(UC_HOOK_CODE, probe, begin=AFTER_SYNTH, end=AFTER_SYNTH)
        if MAP:
            state["calls"] = {}
            if os.environ.get("MEASURE"):     # instructions per digigrain_granular_render call, steps 2400-2440
                lo = MAP["digigrain_synth_all"]
                ret = lo + 36                  # the instruction after `jsr digigrain_granular_render` (5 arg copies 20 + jsr 6 + lea 4 + jsr 6)
                span = (0x47be0000, 0x47be4000)
                cnt = {"inside": False, "n": 0, "calls": []}
                def enter(u, a, sz, d):
                    if 2400 <= state["n"] <= 2440:
                        cnt["inside"], cnt["n"] = True, 0
                def tick(u, a, sz, d):
                    if cnt["inside"]:
                        cnt["n"] += 1
                def leave(u, a, sz, d):
                    if cnt["inside"]:
                        cnt["inside"] = False
                        cnt["calls"].append(cnt["n"])
                uc.hook_add(UC_HOOK_CODE, enter, begin=MAP["digigrain_granular_render"], end=MAP["digigrain_granular_render"])
                uc.hook_add(UC_HOOK_CODE, tick, begin=span[0], end=span[1])
                uc.hook_add(UC_HOOK_CODE, leave, begin=ret, end=ret)
                state["cnt"] = cnt
            def at_block(u, a, sz, d):
                if state["n"] >= 2300:                      # grain pitch (Q16 rate) per call, for the rate-detector check
                    sp0 = u.reg_read(UC_M68K_REG_A7)
                    pp0 = struct.unpack(">I", rd(u, sp0 + 16, 4))[0]
                    r0 = struct.unpack(">I", rd(u, pp0 + 4, 4))[0]
                    state.setdefault("rates", {})[r0] = state.setdefault("rates", {}).get(r0, 0) + 1
                if os.environ.get("TRACE_GR") and state["n"] >= 2300 and state.get("tr", 0) < 6:
                    sp = u.reg_read(UC_M68K_REG_A7)
                    vptr, pcmp, ln, pp, outp = struct.unpack(">5I", rd(u, sp + 4, 20))
                    state["tr"] = state.get("tr", 0) + 1
                    print("gr_block: len", ln, "params", struct.unpack(">8i", rd(u, pp, 32)))
            if "gr_block" in MAP:
                uc.hook_add(UC_HOOK_CODE, at_block, begin=MAP["gr_block"], end=MAP["gr_block"])
            for name in ("digigrain_synth_all", "digigrain_granular_render", "digigrain_granular_machine"):
                if name in MAP:
                    uc.hook_add(UC_HOOK_CODE, (lambda nm: lambda u, a, s, d: state["calls"].__setitem__(nm, state["calls"].get(nm, 0) + 1))(name),
                                begin=MAP[name], end=MAP[name])
        state["uc"] = uc
        def arg_hook(u, ad, sz, d):
            sp = u.reg_read(UC_M68K_REG_A7)
            a1, a2 = struct.unpack(">II", rd(u, sp + 4, 8))
            try:
                vt = struct.unpack(">I", rd(u, a1, 4))[0]
            except Exception:
                vt = None
            arg_seen.add((hex(ad), hex(a1 >> 16), hex(vt) if vt is not None else None, hex(a2)))
        from unicorn import m68k_const as _mc
        for spec in (x for x in os.environ.get("REGS", "").split(",") if x):     # REGS="addr:A3,..." print a register at an address
            addr_s, reg_s = spec.split(":")
            def reg_hook(u, ad, sz, d, reg=getattr(_mc, "UC_M68K_REG_" + reg_s), name=spec):
                cnt = state.setdefault("regcnt", {})
                if state["n"] >= 2300 and cnt.get(name, 0) < 3:
                    cnt[name] = cnt.get(name, 0) + 1
                    print("REG", name, hex(u.reg_read(reg)), "step", state["n"])
            uc.hook_add(UC_HOOK_CODE, reg_hook, begin=int(addr_s, 16), end=int(addr_s, 16))
        for spec in (x for x in os.environ.get("MEMAT", "").split(",") if x):    # MEMAT="addr:A6:54:2" print memory at reg+off
            addr_s, reg_s, off_s, len_s = spec.split(":")
            def mem_hook(u, ad, sz, d, reg=getattr(_mc, "UC_M68K_REG_" + reg_s), off=int(off_s), ln=int(len_s), name=spec):
                cnt = state.setdefault("memcnt", {})
                if state["n"] >= int(os.environ.get("MEMAT_FROM", "2300")) and cnt.get(name, 0) < 4:
                    cnt[name] = cnt.get(name, 0) + 1
                    base = u.reg_read(reg)
                    print("MEMAT", name, hex(base + off), bytes(u.mem_read(base + off, ln)).hex(), "step", state["n"])
            uc.hook_add(UC_HOOK_CODE, mem_hook, begin=int(addr_s, 16), end=int(addr_s, 16))
        from unicorn import UC_HOOK_MEM_READ as _MR
        watch_seen = state.setdefault("watch", set())
        for a_s in (x for x in os.environ.get("WATCH", "").split(",") if x):     # WATCH="addr,..." log the pcs that read these bytes
            def wr(u, access, address, size, value, d):
                if state["n"] >= 1700:
                    watch_seen.add((hex(address), hex(u.reg_read(UC_M68K_REG_PC))))
            uc.hook_add(_MR, wr, begin=int(a_s, 16), end=int(a_s, 16) + 1)
        for a in ARG_TRACE:
            uc.hook_add(UC_HOOK_CODE, arg_hook, begin=a, end=a)
        for a in SITES:
            uc.hook_add(UC_HOOK_CODE, (lambda ad: lambda u, x, sz, d: site_hits.__setitem__(ad, site_hits.get(ad, 0) + 1))(a),
                        begin=a, end=a)
    if n == 1750:
        u = state["uc"]
        for base, name in ((0x80002772, "smoothed 0x80002772+106v"), (0x80001502, "engine copy 0x80001502+106v")):
            w = struct.unpack(">53H", rd(u, base, 106))
            print(name, "v0 slots 1-8 LFO1:", w[1:9], "| 0x11-0x18 SRC:", w[17:25], "| 0x19-0x20:", w[25:33], "| 0x26-0x2d AMP:", w[38:46])
    if os.environ.get("SHOTS") and n in tuple(int(x) for x in os.environ.get('SHOT_STEPS', '').split(',') if x):
        shot("step%d" % n)
    if MAP and n in (2250, 2310, 2400):
        u = state["uc"]
        print("step", n, "core_track_machine:", list(rd(u, MAP["core_track_machine"], 8)),
              "hook counts:", state.get("calls"))
    for item in (x for x in os.environ.get("SWEEP", "").split(",") if x):        # SWEEP="slot:value@step,...": one-shot param writes at given steps
        sl_val, at_step = item.split("@")
        if n == int(at_step):
            sl_, val_ = sl_val.split(":")
            word_ = struct.pack(">H", int(val_, 0) if val_.startswith("0x") else int(val_) << 8)
            state["uc"].mem_write(0x80001502 + 2 * int(sl_), word_)
            kit_ = struct.unpack(">I", rd(state["uc"], 0x800019ac, 4))[0]
            if kit_:
                state["uc"].mem_write(kit_ + 0x20 + 0x14 + 2 * int(sl_), word_)
    if os.environ.get("POKE") and n >= int(os.environ.get("POKE_FROM", "1000")):    # POKE_FROM=2200: after the machine switch and its defaults
        for kv in os.environ["POKE"].split(","):
            sl, val = kv.split(":")
            word = struct.pack(">H", int(val, 0) if val.startswith("0x") else int(val) << 8)   # "0x0100" = raw word
            state["uc"].mem_write(0x80001502 + 2 * int(sl), word)           # the voice's copy
            kit = struct.unpack(">I", rd(state["uc"], 0x800019ac, 4))[0]
            if kit:                                                         # the kit's sound block, so a trig's reload keeps it
                state["uc"].mem_write(kit + 0x20 + 0x14 + 2 * int(sl), word)
    if os.environ.get("MEMDUMP") and n == int(os.environ.get("MEMDUMP_STEP", "600")):
        for spec in os.environ["MEMDUMP"].split(","):
            a_, l_ = (int(x, 16) for x in spec.split(":"))
            data = rd(state["uc"], a_, l_)
            for off in range(0, l_, 16):
                print("MEM %08x: %s" % (a_ + off, " ".join("%02x" % b for b in data[off:off + 16])))
    if ARG_TRACE and n == 1150:
        for t in sorted(arg_seen):
            print("ARGS", t)
    if SITES and n in (700, 790, 880, 1000, 1100):
        print("SITES step %d:" % n, {hex(k): v for k, v in sorted(site_hits.items()) if v})
        site_hits.clear()
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
for t_ in sorted(state.get("watch", ())):
    print("WATCH read", t_)
rows = state["rows"]
v0 = [r for r in rows if r[1] == 0]
if v0 and os.environ.get("GAPS"):            # longest silent stretch (blocks) of voice 0 after step GAPS_FROM
    frm = int(os.environ.get("GAPS_FROM", "2400"))
    rr = [r for r in v0 if r[0] >= frm]
    gaps = [(b_[4] - a_[4]) // 32 - 1 for a_, b_ in zip(rr, rr[1:]) if 0 <= b_[4] - a_[4] < 4000]
    print("GAPS after step %d: blocks with signal %d, silent blocks max %d (= %.0f ms), gaps > 3 blocks: %d" % (
        frm, len(rr), max(gaps or [0]), max(gaps or [0]) * 32 / 48.0, sum(1 for g_ in gaps if g_ > 3)))
if v0 and os.environ.get("LIFE"):
    pos = [r[4] for r in v0]
    wraps = sum(1 for a_, b_ in zip(pos, pos[1:]) if b_ < a_ - 1000)
    print("LIFE v0: %d blocks with signal, on=1 in %d, first step %d, last step %d, V+4 max %d, loop wraps %d, grain rates %s" % (
        len(v0), sum(1 for r in v0 if r[2]), v0[0][0], v0[-1][0], max(pos), wraps, dict(sorted(state.get("rates", {}).items()))))
print("min trailing zero bits in voice 0 block values: %s, max distinct values per block: %s" % (state.get("tz"), state.get("distinct")))
print("block peaks of voice 0 / %d (s16 units), every 6th block:" % GAIN_UNIT)
print([r[5] // GAIN_UNIT for r in rows[::6]][:80])
if os.environ.get("DUMP"):
    print("all v0 block peaks:", [(r[0], r[4], r[5] // GAIN_UNIT) for r in rows if r[1] == 0][:int(os.environ["DUMP"])])
if rows:
    uc = state["uc"]
    ptr, length = rows[0][6], rows[0][7]
    pcm_src = struct.unpack(">%dh" % min(length, 48000), rd(uc, ptr, 2 * min(length, 48000)))
    print("source PCM peak %d; max block peak / %d = %d" % (max(abs(x) for x in pcm_src), GAIN_UNIT,
                                                           max(r[5] for r in rows) // GAIN_UNIT))
if state.get("cnt") and state["cnt"]["calls"]:
    c = state["cnt"]["calls"]
    print("instructions per digigrain_granular_render call: n=%d avg %d max %d" % (len(c), sum(c) // len(c), max(c)))
if len(pcm) > 4 and os.environ.get("ZCSTAT"):          # rising zero crossings per 50 ms window of the left channel
    s16z = struct.unpack("<%dh" % (len(pcm) // 2), pcm)[0::2]
    i0 = next((i for i, x in enumerate(s16z) if abs(x) > 200), 0) + 4800
    zc = [sum(1 for a_, b_ in zip(s16z[i:i + 2400], s16z[i + 1:i + 2401]) if a_ < 0 <= b_) for i in range(i0, min(len(s16z) - 2401, i0 + 2400 * 40), 2400)]
    print("ZCSTAT per 50ms window (440 Hz = 22):", zc, "min %d max %d" % (min(zc), max(zc)))
if len(pcm) > 4:
    s16 = struct.unpack("<%dh" % (len(pcm) // 2), pcm)
    left = s16[0::2]
    start = next((i for i, x in enumerate(left) if abs(x) > 200), 0)
    seg = left[start:start + 24000]
    zc = sum(1 for a, b in zip(seg, seg[1:]) if a < 0 <= b)
    print("audio: %d frames, peak %d, first sound at %.3f s; rising zero crossings in the next 0.5 s: %d (440 Hz -> ~220)" % (
        len(left), max(abs(x) for x in left), start / 48000, zc))
