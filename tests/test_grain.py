"""Host tests for mod/grain.c: the C code (built as a shared library) against an
independent Python model of the same integer arithmetic, plus behaviour checks."""
import ctypes
import importlib.util
import math
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR_MAX, FRAMES = 12, 32
M32 = 0xffffffff

_spec = importlib.util.spec_from_file_location("gen_tables", os.path.join(ROOT, "tools", "gen_tables.py"))
_gt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gt)
SINE, GATE, DECAY, RATIO, AVG = _gt.tables()


class Grain(ctypes.Structure):
    _fields_ = [("idx", ctypes.c_int), ("frac", ctypes.c_uint), ("inc", ctypes.c_uint),
                ("wph", ctypes.c_uint), ("winc", ctypes.c_uint), ("shape", ctypes.c_int),
                ("dir", ctypes.c_int), ("delay", ctypes.c_int), ("active", ctypes.c_int)]


class Voice(ctypes.Structure):
    _fields_ = [("g", Grain * GR_MAX), ("next_in", ctypes.c_int), ("rng", ctypes.c_uint)]


class Params(ctypes.Structure):
    _fields_ = [("pos", ctypes.c_int), ("src_size", ctypes.c_int), ("rate", ctypes.c_uint),
                ("dir", ctypes.c_int), ("mode", ctypes.c_int), ("interval", ctypes.c_int),
                ("rand", ctypes.c_int), ("shape", ctypes.c_int)]


def cdiv(a, b):
    return a // b            # operands are non-negative where it matters


class Model:
    """Python mirror of gr_reset / gr_block."""

    def __init__(self, seed):
        self.g, self.next_in, self.rng = [], 0, seed or 0x9e3779b9

    def rnd(self):
        x = self.rng
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.rng = x
        return x

    def start(self, p, n, delay):
        if len(self.g) >= GR_MAX:
            return
        pos = p["pos"]
        jr = (n >> 2) // 127 * p["rand"]
        if jr > 0:
            pos += self.rnd() % (2 * jr + 1) - jr
        pos = max(0, min(pos, n - 2))
        ratio = 65536
        m = p["rand"] * 12 // 127
        if m > 0:
            ratio = RATIO[self.rnd() % (2 * m + 1) - m + 12]
        shape = p["shape"]
        r = p["rand"] * 256 // 127
        if r > 0:
            shape += self.rnd() % (2 * r + 1) - r
        shape = max(-256, min(256, shape))
        eff = max(256, (((p["rate"] >> 6) * (ratio >> 6)) >> 4))
        out_len = max(16, min(65535, (p["src_size"] << 16) // eff))
        self.g.append(dict(idx=pos, frac=0, inc=eff, wph=0, winc=65536 // out_len, shape=shape,
                           dir=p["dir"], delay=delay))

    def block(self, pcm, p):
        n = len(pcm)
        acc = [0] * FRAMES
        if p["mode"] == 0:
            self.next_in = 0
        else:
            while self.next_in < FRAMES:
                self.start(p, n, max(self.next_in, 0))
                self.next_in += p["interval"] if p["mode"] == 1 else self.rnd() % (2 * p["interval"]) + 1
            self.next_in -= FRAMES
        for g in list(self.g):
            for f in range(g["delay"], FRAMES):
                if g["idx"] < 0 or g["idx"] >= n - 1 or g["wph"] >= 65536:
                    self.g.remove(g)
                    break
                a, b = pcm[g["idx"]], pcm[g["idx"] + 1]
                s = a + (((b - a) * (g["frac"] >> 2)) >> 14)
                w = SINE[g["wph"] >> 8]
                sh = g["shape"]
                if sh < 0:
                    w += ((GATE[g["wph"] >> 8] - w) * -sh) >> 8
                elif sh > 0:
                    w += ((DECAY[g["wph"] >> 8] - w) * sh) >> 8
                acc[f] += (s * w) >> 15
                g["wph"] += g["winc"]
                if g["dir"] > 0:
                    t = g["frac"] + g["inc"]
                    g["idx"] += t >> 16
                    g["frac"] = t & 0xffff
                else:
                    lo = g["inc"] & 0xffff
                    g["idx"] -= g["inc"] >> 16
                    if g["frac"] >= lo:
                        g["frac"] -= lo
                    else:
                        g["frac"] = g["frac"] + 65536 - lo
                        g["idx"] -= 1
            g["delay"] = 0
        return [max(-32768, min(32767, x)) for x in acc]


def avg_level(shape):
    if shape < 0:
        return AVG[0] + (((AVG[1] - AVG[0]) * -shape) >> 8)
    return AVG[0] + (((AVG[2] - AVG[0]) * shape) >> 8)


def model_norm(p):
    out_len = max(1, (p["src_size"] << 16) // (p["rate"] or 1))
    t = min(1024, (p["interval"] << 8) // out_len)
    return min(256, (t << 8) // (avg_level(p["shape"]) or 1))


@unittest.skipUnless(shutil.which("cc"), "no host C compiler")
class GrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        lib = os.path.join(cls.tmp, "libgrain.so")
        subprocess.check_call(["cc", "-O2", "-shared", "-fPIC", "-Wall", "-Werror",
                               "-I", os.path.join(ROOT, "mod"), "-o", lib,
                               os.path.join(ROOT, "mod", "grain.c")])
        cls.lib = ctypes.CDLL(lib)
        cls.lib.gr_block.argtypes = [ctypes.POINTER(Voice), ctypes.POINTER(ctypes.c_short), ctypes.c_int,
                                     ctypes.POINTER(Params), ctypes.POINTER(ctypes.c_int)]
        cls.lib.gr_reset.argtypes = [ctypes.POINTER(Voice), ctypes.c_uint]
        cls.lib.gr_active.argtypes = [ctypes.POINTER(Voice)]
        cls.lib.gr_norm.argtypes = [ctypes.POINTER(Params)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    D = dict(pos=1000, src_size=2400, rate=65536, dir=1, mode=1, interval=1200, rand=0, shape=0)

    def params(self, **kw):
        d = dict(self.D)
        d.update(kw)
        return d

    def run_c(self, pcm, p, blocks, seed=1):
        arr = (ctypes.c_short * len(pcm))(*pcm)
        v, cp, out = Voice(), Params(**p), []
        self.lib.gr_reset(ctypes.byref(v), seed)
        for _ in range(blocks):
            o = (ctypes.c_int * FRAMES)()
            self.lib.gr_block(ctypes.byref(v), arr, len(pcm), ctypes.byref(cp), o)
            out.append(list(o))
        return v, out

    def run_model(self, pcm, p, blocks, seed=1):
        m = Model(seed)
        return [m.block(pcm, p) for _ in range(blocks)]

    @staticmethod
    def sine(n=48000, hz=440, amp=16384):
        return [int(amp * math.sin(2 * math.pi * hz * i / 48000)) for i in range(n)]

    def test_matches_python_model(self):
        pcm = self.sine()
        cases = [self.params(),
                 self.params(rate=77777, dir=-1, pos=30000),
                 self.params(mode=2, interval=600, rand=0),
                 self.params(mode=2, interval=400, rand=127, shape=-100),
                 self.params(mode=1, interval=700, rand=60, shape=200, rate=3 * 65536),
                 self.params(mode=1, interval=300, shape=-256, dir=-1, pos=40000, rand=20)]
        for i, p in enumerate(cases):
            _, out = self.run_c(pcm, p, 150, seed=7 + i)
            self.assertEqual(out, self.run_model(pcm, p, 150, seed=7 + i), "case %d: %s" % (i, p))

    def test_norm_matches_model(self):
        for p in (self.params(), self.params(interval=100, shape=-200), self.params(rate=20000, interval=50),
                  self.params(interval=190000, shape=250)):
            self.assertEqual(self.lib.gr_norm(ctypes.byref(Params(**p))), model_norm(p), p)

    def test_mode_none_is_silent_and_spawns_nothing(self):
        v, out = self.run_c(self.sine(), self.params(mode=0), 20)
        self.assertEqual(self.lib.gr_active(ctypes.byref(v)), 0)
        self.assertTrue(all(x == 0 for b in out for x in b))

    def test_speed_scales_pitch(self):
        pcm = self.sine(hz=200)

        def crossings_per_sample(rate):
            _, out = self.run_c(pcm, self.params(rate=rate, interval=4800, shape=-256), 150)
            flat = [x for b in out for x in b]
            sounding = sum(1 for x in flat if abs(x) > 50)
            return sum(1 for a, b in zip(flat, flat[1:]) if a < 0 <= b) / sounding
        self.assertAlmostEqual(crossings_per_sample(2 * 65536) / crossings_per_sample(65536), 2.0, delta=0.25)

    def test_grain_length_in_output_follows_speed(self):
        pcm = [10000] * 48000                        # DC: output is the window itself
        for rate, expect in ((65536, 2400), (2 * 65536, 1200), (65536 // 2, 4800)):
            _, out = self.run_c(pcm, self.params(rate=rate, interval=48000, mode=1, shape=-256), 1 + expect // 32 + 8)
            flat = [x for b in out for x in b]
            n = sum(1 for x in flat if x > 100)
            self.assertAlmostEqual(n, expect, delta=expect * 0.07, msg="rate %d" % rate)

    def test_reverse_reads_backwards(self):
        pcm = list(range(0, 30000, 1))               # a ramp: forward grains rise, reverse fall
        _, fwd = self.run_c(pcm, self.params(dir=1, pos=5000, interval=48000, shape=-256, mode=1), 12)
        _, rev = self.run_c(pcm, self.params(dir=-1, pos=25000, interval=48000, shape=-256, mode=1), 12)
        f = [x for b in fwd for x in b]
        r = [x for b in rev for x in b]
        self.assertGreater(f[200], f[100])
        self.assertLess(r[200], r[100])

    def test_shape_gate_flat_and_decay_falls(self):
        pcm = [10000] * 48000
        _, gate = self.run_c(pcm, self.params(interval=48000, shape=-256), 100)
        _, dec = self.run_c(pcm, self.params(interval=48000, shape=256), 100)
        g = [x for b in gate for x in b][:2400]
        d = [x for b in dec for x in b][:2400]
        self.assertGreater(min(g[100:2300]), 9900)                       # flat top
        self.assertGreater(d[200], d[1200] * 2)                          # decays
        self.assertGreater(d[1200], d[2200])

    def test_random_mode_keeps_the_mean_overlap(self):
        # mean grains alive = grain length / mean interval = 2400 / 1000 = 2.4
        pcm = [1] * 48000
        v = Voice()
        arr = (ctypes.c_short * len(pcm))(*pcm)
        cp = Params(**self.params(mode=2, interval=1000))
        self.lib.gr_reset(ctypes.byref(v), 3)
        o = (ctypes.c_int * FRAMES)()
        counts = []
        for i in range(1500):
            self.lib.gr_block(ctypes.byref(v), arr, len(pcm), ctypes.byref(cp), o)
            if i > 100:
                counts.append(self.lib.gr_active(ctypes.byref(v)))
        self.assertAlmostEqual(sum(counts) / len(counts), 2.4, delta=0.6)

    def test_pool_exhaustion_and_edges_are_safe(self):
        pcm = self.sine(n=64)
        p = self.params(pos=60, src_size=5000, interval=1, rate=7 * 65536, rand=127, mode=2)
        v, out = self.run_c(pcm, p, 50, seed=0xdeadbeef)
        self.assertLessEqual(self.lib.gr_active(ctypes.byref(v)), GR_MAX)
        self.assertTrue(all(-32768 <= x <= 32767 for b in out for x in b))

    def test_short_sample_is_ignored(self):
        _, out = self.run_c([5, 6, 7], self.params(), 3)
        self.assertEqual(out, [[0] * FRAMES] * 3)


if __name__ == "__main__":
    unittest.main()
