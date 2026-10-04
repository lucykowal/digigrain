#!/usr/bin/env python3
"""Render margin of our build with N tracks on dense GRANULAR, under emu.fwcheck's timing mode (issue #2).

    uv run --project ../digiemumac python tests/emu/margin_probe.py N [--fwcheck] [--no-timing] [--out DIR]

Writes a key script that, for tracks 1..N, selects the track (TRK + trig key), switches its SRC machine to
GRANULAR (FUNC+SRC, DOWN x4, YES) and turns RATE (random grain intervals), RTIO (8:1) and SPRD fully clockwise (the heaviest settings), then plays the pattern. It reuses the booted snapshot a prior `--fwcheck` run left in out/margin (the boot is paid once), runs the
script under timing mode and prints the render margin. Timing mode takes about 8-12 minutes;
--no-timing runs fast and only saves the snap PNGs (out/margin/png-N) to check the script.

The tracks need a sample and trigs: the factory snapshot's pattern is used as is, so check the snap PNGs
(in DIR) and the audio to see how many tracks actually played."""
import argparse
import os
import subprocess
import sys

MOD_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
OUT_MOD = os.path.join(ROOT, "out", "digigrain")
EMU = os.path.join(ROOT, "..", "digiemumac")
RTIO, SPRD = "F", "C"            # RTIO to 8:1 (8 overlapping grains), SPRD to the full random pitch spread
DENS = "B"                      # the RATE knob on the GRANULAR SRC page (noon = no grains, CW = random intervals)
MACHINE_DOWNS = 4               # DOWN presses from the stock machine to GRANULAR (as scale_probe.py)


def script(n):
    lines = ["wait 1000", "snap start"]
    for t in range(1, n + 1):
        lines += ["press TRK 100", "tap %d 80 200" % t, "release TRK 200",
                  "press FUNC 100", "tap SRC 100 200", "release FUNC 200"]
        lines += ["tap DOWN 80 150"] * MACHINE_DOWNS
        lines += ["tap YES 100 400"]
        for knob in (DENS, RTIO, SPRD):             # small, spaced events: one big turn is not taken
            lines += ["turn %s +4 80" % knob] * 16
        lines += ["wait 300", "snap track-%d" % t]
    lines += ["tap PLAY", "wait 4000", "snap playing", "tap STOP", "tap STOP", "wait 500"]
    return "\n".join(lines) + "\n"


def find_work(out):
    """The newest booted build folder a `fwcheck` run left (its work/build/<id>), reused so the boot is paid once."""
    import glob
    dirs = [d for d in glob.glob(os.path.join(out, "run-*", "work", "build", "*"))
            if os.path.exists(os.path.join(d, "snapshots", "test", "gui.snap"))]
    return max(dirs, key=os.path.getmtime) if dirs else None


def run(n, out, timing):
    """Drive the script on the booted snapshot; save the snap PNGs and print the margin."""
    work = find_work(out)
    if not work:
        sys.exit("no booted build under %s: run `margin_probe.py 1 --no-timing --fwcheck` once first" % out)
    sys.path.insert(0, EMU)
    from emu import bootstrap as bs, cftiming, device as devmod, panel, ssi
    from emu.fwcompare import parse_script
    from emu.session import Session, run_script
    name = [f for f in os.listdir(work) if f.endswith(".syx")][0]
    paths = bs.FirmwarePaths(work, name, os.path.join(work, "devices") if os.path.isdir(os.path.join(work, "devices"))
                             else os.path.join(EMU, "devices"))
    os.environ.update(paths.env())
    dev, _ = devmod.identify(paths.syx, paths.overlay if os.path.isdir(paths.overlay) else paths.devices_dir)
    gui = os.path.join(work, "snapshots", "test", "gui.snap")
    s = Session(gui, paths.syx, hle=False, timing={"accel": "max"} if timing else None, strict={"stop": False},
                ddr=dev.ddr_bytes or 0x8000000)
    try:
        marks = run_script(s, parse_script(script(n)))
        for label, ms in marks:
            buf = s.screen_at(ms)
            if buf is not None:
                panel.write_png(buf, os.path.join(out, "png-%d" % n, label + ".png"))
        pcm = bytes(s.pcm)
        print("emulated %.1f s, halted: %s" % (s.ms / 1000, s.halted))
        if s.clock is not None:
            t = s.clock.report()
            prof = ssi.PROFILES.get((dev.audio or {}).get("ssi_profile"))
            period = cftiming.measured_period(s.clock, prof.tx_vector)
            ds = [cftiming.deadline_report(s.clock, v, period) for v in (prof.tx_vector, ssi.FORCE_VECTOR)]
            margins = [d["margin"] for d in ds if "margin" in d]
            print("N=%d: audio render margin %.1f%%, late renders %d, CPU busy %.0f%%" % (
                n, 100 * min(margins), sum(d.get("late", 0) for d in ds), 100 * t["busy_fraction"]))
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int, help="GRANULAR tracks (1..8)")
    ap.add_argument("--no-timing", action="store_true")
    ap.add_argument("--fwcheck", action="store_true", help="boot out/digigrain/test.syx under emu.fwcheck first (about 4 min, once)")
    ap.add_argument("--out", default=os.path.join(OUT_MOD, "margin"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if args.fwcheck:
        path = os.path.join(args.out, "margin-%d.script" % args.n)
        with open(path, "w") as f:
            f.write(script(args.n))
        subprocess.call([sys.executable, "-m", "emu.fwcheck", os.path.join(OUT_MOD, "test.syx"), "--script", path,
                         "--no-timing", "--no-boot-strict", "--out", os.path.join(args.out, "run-%d" % args.n)], cwd=EMU)
        return
    run(args.n, args.out, not args.no_timing)


if __name__ == "__main__":
    main()
