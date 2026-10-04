#!/usr/bin/env python3
"""Drive the RESAMPLE machine in digiemu (headless): record, then play back.

Needs a probe home for our build (see CLAUDE.md: SYX=out/test-resample.syx tests/emu/make_probe_home.sh) and
    DIGIEMU=<../digiemumac> FW_DIR=out/emu/home/firmware/<newest> uv run --project ../digiemumac python tests/emu/resample_probe.py
Track 1 (the factory snapshot's) is switched to RESAMPLE (the fifth machine). Nothing plays on the other
tracks and the emulator has no audio input, so a 440 Hz sine is injected into the RECORDER's capture block
(0x800032c4) right after the source switch (0x40076742, inside 0x40076650) while the recorder is armed or
recording. Phase 1: D = REC, trig key 1 held (steps REC_ON..REC_OFF). Phase 2: D = PLAY, trig key 1 held
(PLAY_ON..PLAY_OFF). It prints the recorder state, length, SRC, sample slot 0x82 and the voice's block
peak, then the audio's rising zero crossings (440 Hz -> ~220 in 0.5 s).
Env: STEPS, REC_ON/REC_OFF/PLAY_ON/PLAY_OFF (steps), SRC (G knob value, default 9), SHOTS.
"""
import glob
import math
import os
import struct
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIGIEMU = os.path.abspath(os.environ.get("DIGIEMU", os.path.join(ROOT, "..", "digiemumac")))
FW = os.environ["FW_DIR"]
REC_ON, REC_OFF = int(os.environ.get("REC_ON", "2700")), int(os.environ.get("REC_OFF", "3300"))
PLAY_ON, PLAY_OFF = int(os.environ.get("PLAY_ON", "4100")), int(os.environ.get("PLAY_OFF", "4700"))
STEPS = int(os.environ.get("STEPS", "5400"))
SRC = int(os.environ.get("SRC", "9"))
BLOCKS, VOICE, SMP_TAB = 0x80001a18, 0x8000edc4, 0x403193a0
CAPTURE, AFTER_SWITCH = 0x800032c4, 0x40076742
REC_STATE, REC_LEN, REC_SRC = 0x4199e114, 0x4199e104, 0x4197bf98

sys.path.insert(0, DIGIEMU)
syx = [f for f in os.listdir(FW) if f.endswith(".syx")][0]
os.environ.update({
    "DT2_SYX": os.path.join(FW, syx), "DT2_SECTIONS": FW + "/sections", "DT2_SNAPSHOTS": FW + "/snapshots",
    "DT2_PLUSDRIVE": FW + "/plusdrive.img", "DT2_MAIN_IMG": FW + "/sections/section_3_MAIN_OS.bin",
    "DT2_DEVICES": FW + "/devices" if os.path.isdir(FW + "/devices") else os.path.join(DIGIEMU, "devices")})
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
# step ~5 ms. Load the sine440 sample on track 1 (so the stock voice has a sample), then FUNC+SRC and DOWN x4
# to the fifth machine, YES; same keys as scale_probe.py.
PLAN = {600: ("press", 20), 620: ("release", 20), 700: ("encoder", 4, 1),
        800: ("press", 12), 820: ("release", 12), 950: ("press", 15), 970: ("release", 15),
        1050: ("press", 12), 1070: ("release", 12), 1150: ("press", 15), 1170: ("release", 15),
        1250: ("press", 12), 1270: ("release", 12),
        1450: ("press", 1), 1460: ("press", 20), 1480: ("release", 20), 1490: ("release", 1)}
for t in (1600, 1680, 1760, 1840):
    PLAN[t], PLAN[t + 20] = ("press", 15), ("release", 15)
PLAN.update({2000: ("press", 12), 2020: ("release", 12)})
PLAN[REC_ON], PLAN[REC_OFF] = ("press", 24), ("release", 24)
PLAN[PLAY_ON], PLAN[PLAY_OFF] = ("press", 24), ("release", 24)
for kv in (x for x in os.environ.get("PRESS", "").split(",") if x):      # PRESS="step:key:release_step,..." extra key holds
    st_, key_, rel_ = (int(x) for x in kv.split(":"))
    PLAN[st_], PLAN[rel_] = ("press", key_), ("release", key_)
state = {"n": 0, "phase": 0, "log": []}


def rd(uc, addr, n):
    return bytes(uc.mem_read(addr, n))


def u32(uc, a):
    return struct.unpack(">I", rd(uc, a, 4))[0]


def poke_param(uc, slot, word):
    w = struct.pack(">H", word)
    uc.mem_write(0x80001502 + 2 * slot, w)                  # the voice's engine copy
    kit = u32(uc, 0x800019ac)
    if kit:
        uc.mem_write(kit + 0x20 + 0x14 + 2 * slot, w)       # the kit's sound, so a trig's reload keeps it


def inject(uc, addr, size, data):
    if u32(uc, REC_STATE) in (1, 2):
        k = state.setdefault("k", 0)
        blk = b"".join(struct.pack(">i", int(0x20000000 * math.sin(2 * math.pi * 440 * (k + i) / 48000))) for i in range(32))
        uc.mem_write(CAPTURE, blk)
        state["k"] = k + 32


_spin = G.spin


def spin(m, pc, *args, **kw):
    uc = m.uc
    n = state["n"]
    if n == 0:
        uc.hook_add(UC_HOOK_CODE, inject, begin=AFTER_SWITCH, end=AFTER_SWITCH)
        if os.environ.get("TRACE_PRE"):                      # log TRIGMASK / KEYMASK / voice 0's on byte when digiresample_pre runs and one is set
            def pre_hook(u, ad, sz, d):
                mask, keys, on = u32(u, 0x80001228), u32(u, 0x800019f4), rd(u, VOICE + 0x28, 1)[0]
                if (mask or keys) and state["n"] >= int(os.environ.get("TRACE_FROM", "0")) and state.get("pt", 0) < 60:
                    state["pt"] = state.get("pt", 0) + 1
                    print("PRE step %d trigmask %x keys %x on %d" % (state["n"], mask, keys, on))
            uc.hook_add(UC_HOOK_CODE, pre_hook, begin=state["map"]["digiresample_pre"], end=state["map"]["digiresample_pre"])
        state["uc"] = uc
    if n in (REC_ON - 20, PLAY_ON - 20):                    # D and G before each trig (plock-like: engine copy + kit)
        poke_param(uc, 20, 0 if n == REC_ON - 20 else 0x0100)
        poke_param(uc, 23, SRC << 8)
    if n >= 2100 and n % 50 == 0:
        v = VOICE
        blk = struct.unpack(">32i", rd(uc, BLOCKS, 128))
        slot = rd(uc, v + 0x5c, 1)[0]
        ent = struct.unpack(">IIII", rd(uc, SMP_TAB + 16 * 0x82, 16))
        print("step %d state %d len %d src %d | voice0 on %d slot 0x%x peak %d | slot82 ptr 0x%x len %d | machine %s" % (
            n, u32(uc, REC_STATE), u32(uc, REC_LEN), u32(uc, REC_SRC), rd(uc, v + 0x28, 1)[0], slot,
            max(abs(x) for x in blk), ent[0], ent[2], list(rd(uc, state["core"], 8)) if state.get("core") else "?"))
    if n in tuple(int(x) for x in os.environ.get("DUMPV", "").split(",") if x):   # DUMPV="steps": voice 0's 94 bytes
        print("VOICE step %d: %s" % (n, rd(uc, VOICE, 94).hex()))
    for spec in (x for x in os.environ.get("DUMPMEM", "").split(",") if x):      # DUMPMEM="step:addr:len:file"
        st_, ad_, ln_, fn_ = spec.split(":")
        if n == int(st_):
            open(fn_, "wb").write(rd(uc, int(ad_, 16), int(ln_, 16)))
    act = PLAN.get(n)
    if act:
        E.inbox.append((act[0], act[1], act[2] if len(act) > 2 else 0))
    state["n"] += 1
    r = _spin(m, pc, *args, **kw)
    if state["n"] >= STEPS:
        E.stop_flag.set()
    return r


G.spin = spin
if os.environ.get("ELEKLOADER_DIR") or True:
    sys.path.insert(0, os.environ.get("ELEKLOADER_DIR", os.path.join(ROOT, "..", "elekloader")))
    from elekloader import syx as _syx, devices as _dev, elemod as _em, link as _link
    _st = _syx.Syx.load(os.environ.get("ELEKLOADER_STOCK", os.path.join(ROOT, "..", "Digitakt_OS1.53.syx")))
    _d, _r = _dev.identify(_st.sha256)
    _mods = [glob.glob(os.path.join(ROOT, "out", "core", "core-*.elemod"))[0],
             glob.glob(os.path.join(ROOT, "out", "resample", "digiresample-*.elemod"))[0]]
    state["map"] = _link.link([_em.load_any(m) for m in _mods], _st.section(_d.main_section)).map
    state["core"] = state["map"]["core_track_machine"]
E = G.Emulator(SNAP, syx=os.environ["DT2_SYX"], realtime=False, audio=True)
E.run()
pcm = E.audio_take()
print("error:", E.error, "steps:", state["n"])
if len(pcm) > 4:
    left = struct.unpack("<%dh" % (len(pcm) // 2), pcm)[0::2]
    print("audio: %d frames, peak %d" % (len(left), max(abs(x) for x in left)))
    for name, lo, hi in (("rec phase", REC_ON, REC_OFF), ("play phase", PLAY_ON, PLAY_OFF)):
        # steps -> samples is not exact: look for sound anywhere and count crossings in 0.5 s windows
        pass
    start = next((i for i, x in enumerate(left) if abs(x) > 200), None)
    if start is not None:
        seg = left[start:start + 24000]
        zc = [sum(1 for x, y in zip(left[i:i + 12000], left[i + 1:i + 12001]) if x < 0 <= y) for i in range(start, min(len(left) - 12001, start + 12000 * 12), 12000)]
        print("rising zero crossings per 0.25 s from the first sound (440 Hz -> ~110):", zc)
        print("first sound at %.3f s; rising zero crossings in 0.5 s: %d (440 Hz -> ~220)" % (
            start / 48000, sum(1 for a, b in zip(seg, seg[1:]) if a < 0 <= b)))
