#!/usr/bin/env python3
"""Instruction counts for mod/grain.c's gr_block, compiled for the ColdFire and run in digiemu's
(patched) Unicorn: seconds per run, exact counts.

    uv run --project ../digiemumac python tests/emu/grain_bench.py [--blocks N]

Prints the average and maximum instructions per gr_block call for a few settings (the grain
engine only: the firmware glue's overhead is a few hundred more per call, see bench.sh)."""
import argparse
import math
import os
import struct
import subprocess

from unicorn import UC_ARCH_M68K, UC_HOOK_CODE, UC_MODE_BIG_ENDIAN, Uc
from unicorn.m68k_const import UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_PC

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CROSS = os.environ.get("ELEKLOADER_CROSS", "m68k-elf-")
OUT = os.path.join(ROOT, "out", "bench")
CODE, DATA, STACK, STOP = 0x100000, 0x200000, 0x300000, 0x1000
GR_MAX = 12
VOICE_BYTES = GR_MAX * 36 + 8


def build():
    os.makedirs(OUT, exist_ok=True)
    obj, elf, binf = (os.path.join(OUT, n) for n in ("grain.o", "grain.elf", "grain.bin"))
    subprocess.check_call([CROSS + "gcc", "-mcpu=54455", "-O2", "-ffreestanding", "-fno-builtin", "-nostdlib",
                           "-fno-pic", "-fno-pie", "-fomit-frame-pointer", "-Wall", "-I", os.path.join(ROOT, "mod"),
                           "-c", os.path.join(ROOT, "mod", "grain.c"), "-o", obj])
    subprocess.check_call([CROSS + "ld", "-Ttext=0x%x" % CODE, "-e", "gr_block", "-o", elf, obj])
    subprocess.check_call([CROSS + "objcopy", "-O", "binary", elf, binf])
    syms = {}
    for line in subprocess.check_output([CROSS + "nm", elf], text=True).splitlines():
        a, _, n = line.split()
        syms[n] = int(a, 16)
    return open(binf, "rb").read(), syms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=120)
    args = ap.parse_args()
    image, syms = build()
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    uc.mem_map(CODE, 0x100000)
    uc.mem_map(DATA, 0x200000)
    uc.mem_map(0x0, 0x2000)
    uc.mem_write(CODE, image)
    uc.mem_write(STOP, b"\x4e\x71\x4e\x71")             # nop nop: the return target
    n = 48000
    pcm = [int(16384 * math.sin(2 * math.pi * 440 * i / 48000)) for i in range(n)]
    PCM, VOICE, PARAMS, OUTB = DATA, DATA + 0x20000, DATA + 0x21000, DATA + 0x22000
    uc.mem_write(PCM, struct.pack(">%dh" % n, *pcm))
    count = [0]
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: count.__setitem__(0, count[0] + 1), begin=CODE, end=CODE + len(image))

    def call_block():
        sp = STACK
        for arg in (OUTB, PARAMS, n, PCM, VOICE):            # right to left
            sp -= 4
            uc.mem_write(sp, struct.pack(">I", arg))
        sp -= 4
        uc.mem_write(sp, struct.pack(">I", STOP))
        uc.reg_write(UC_M68K_REG_A7, sp)
        count[0] = 0
        uc.emu_start(syms["gr_block"], STOP, count=5_000_000)
        return count[0]

    scenarios = [
        ("idle (no grains)", dict(mode=0)),
        ("default-ish (24 Hz, sine)", dict(mode=1, interval=2000)),
        ("dense (120 Hz, sine)", dict(mode=1, interval=400)),
        ("dense + RAND 127 + decay", dict(mode=1, interval=400, rand=127, shape=140)),
        ("dense blend (gate)", dict(mode=1, interval=400, shape=-150)),
        ("dense reverse", dict(mode=1, interval=400, dir=-1, pos=40000)),
    ]
    print("%-28s %8s %8s" % ("gr_block, instructions", "avg", "max"))
    for name, kw in scenarios:
        p = dict(pos=12000, src_size=2400, rate=65536, dir=1, mode=1, interval=400, rand=0, shape=0)
        p.update(kw)
        uc.mem_write(PARAMS, struct.pack(">8i", p["pos"], p["src_size"], p["rate"], p["dir"], p["mode"],
                                         p["interval"], p["rand"], p["shape"]))
        uc.mem_write(VOICE, b"\0" * VOICE_BYTES)
        uc.mem_write(VOICE + GR_MAX * 36 + 4, struct.pack(">I", 12345))      # rng
        counts = [call_block() for _ in range(args.blocks)]
        steady = counts[40:]
        print("%-28s %8d %8d" % (name, sum(steady) // len(steady), max(steady)))


if __name__ == "__main__":
    main()
