"""Host tests for mod/grain.c: the C code (built as a shared library) against an
independent Python model of the same integer arithmetic, plus behaviour checks."""
import ctypes
import math
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR_MAX, FRAMES = 8, 32


class Grain(ctypes.Structure):
    _fields_ = [("idx", ctypes.c_int), ("frac", ctypes.c_uint), ("inc", ctypes.c_uint),
                ("wph", ctypes.c_uint), ("winc", ctypes.c_uint), ("delay", ctypes.c_int),
                ("active", ctypes.c_int)]


class Voice(ctypes.Structure):
    _fields_ = [("g", Grain * GR_MAX), ("next_in", ctypes.c_int), ("rng", ctypes.c_uint)]


class Params(ctypes.Structure):
    _fields_ = [("pos", ctypes.c_int), ("size", ctypes.c_int), ("interval", ctypes.c_int),
                ("jitter", ctypes.c_int), ("rate", ctypes.c_uint), ("spawn", ctypes.c_int)]


WIN = [round(32767 * math.sin(math.pi * (i + 0.5) / 256) ** 2) for i in range(256)]


class Model:
    """Python mirror of gr_block with jitter = 0."""

    def __init__(self):
        self.g, self.next_in = [], 0

    def block(self, pcm, p):
        n = len(pcm)
        acc = [0] * FRAMES
        if p["spawn"]:
            while self.next_in < FRAMES:
                if len(self.g) < GR_MAX:
                    pos = min(max(p["pos"], 0), n - 2)
                    self.g.append(dict(idx=pos, frac=0, inc=p["rate"], wph=0,
                                       winc=65536 // p["size"], delay=max(self.next_in, 0)))
                self.next_in += p["interval"]
            self.next_in -= FRAMES
        for g in list(self.g):
            for f in range(g["delay"], FRAMES):
                if g["idx"] >= n - 1 or g["wph"] >= 65536:
                    self.g.remove(g)
                    break
                a, b = pcm[g["idx"]], pcm[g["idx"] + 1]
                s = a + (((b - a) * (g["frac"] >> 2)) >> 14)
                acc[f] += (s * WIN[g["wph"] >> 8]) >> 15
                g["wph"] += g["winc"]
                t = g["frac"] + g["inc"]
                g["idx"] += t >> 16
                g["frac"] = t & 0xffff
            g["delay"] = 0
        return [max(-32768, min(32767, x)) for x in acc]


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

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def run_blocks(self, pcm, p, blocks, seed=1):
        arr = (ctypes.c_short * len(pcm))(*pcm)
        v = Voice()
        self.lib.gr_reset(ctypes.byref(v), seed)
        out = []
        for _ in range(blocks):
            o = (ctypes.c_int * FRAMES)()
            self.lib.gr_block(ctypes.byref(v), arr, len(pcm), ctypes.byref(p), o)
            out.append(list(o))
        return v, out

    @staticmethod
    def sine(n=48000, hz=440, amp=16384):
        return [int(amp * math.sin(2 * math.pi * hz * i / 48000)) for i in range(n)]

    def params(self, **kw):
        d = dict(pos=1000, size=2400, interval=1200, jitter=0, rate=65536, spawn=1)
        d.update(kw)
        return Params(**d)

    def test_matches_python_model(self):
        pcm = self.sine()
        for rate in (65536, 77777, 30000, 3 * 65536):
            p = self.params(rate=rate)
            _, out = self.run_blocks(pcm, p, 150)
            m, ref = Model(), []
            for _ in range(150):
                ref.append(m.block(pcm, dict(pos=1000, size=2400, interval=1200, rate=rate, spawn=1)))
            self.assertEqual(out, ref, "rate %d" % rate)

    def test_unity_rate_and_overlap_reproduce_input_level(self):
        pcm = self.sine()
        _, out = self.run_blocks(pcm, self.params(interval=1200), 200)
        flat = [x for b in out[100:] for x in b]
        self.assertLessEqual(max(flat), 32767)
        # 2x overlap Hann sums to ~1 of the input amplitude for a coherent grain train
        self.assertGreater(max(flat), 11000)

    def test_pitch_rate_doubles_frequency(self):
        pcm = self.sine(hz=200)

        def crossings(rate):
            _, out = self.run_blocks(pcm, self.params(rate=rate, size=4800, interval=4800), 150)
            flat = [x for b in out for x in b]
            return sum(1 for a, b in zip(flat, flat[1:]) if a < 0 <= b)
        self.assertAlmostEqual(crossings(2 * 65536) / crossings(65536), 2.0, delta=0.2)

    def test_no_spawn_goes_silent(self):
        pcm = self.sine()
        p = self.params(size=480, interval=480)
        arr = (ctypes.c_short * len(pcm))(*pcm)
        v = Voice()
        self.lib.gr_reset(ctypes.byref(v), 1)
        o = (ctypes.c_int * FRAMES)()
        for _ in range(10):
            self.lib.gr_block(ctypes.byref(v), arr, len(pcm), ctypes.byref(p), o)
        p.spawn = 0
        for _ in range(40):
            self.lib.gr_block(ctypes.byref(v), arr, len(pcm), ctypes.byref(p), o)
        self.assertEqual(self.lib.gr_active(ctypes.byref(v)), 0)
        self.assertEqual(list(o), [0] * FRAMES)

    def test_pool_exhaustion_and_edges_are_safe(self):
        pcm = self.sine(n=64)
        # dense grains on a tiny sample, huge jitter, high rate: must not crash or overrun
        p = self.params(pos=60, size=5000, interval=1, jitter=500, rate=7 * 65536)
        v, out = self.run_blocks(pcm, p, 50, seed=0xdeadbeef)
        self.assertLessEqual(self.lib.gr_active(ctypes.byref(v)), GR_MAX)
        self.assertTrue(all(-32768 <= x <= 32767 for b in out for x in b))

    def test_short_sample_is_ignored(self):
        _, out = self.run_blocks([5, 6, 7], self.params(), 3)
        self.assertEqual(out, [[0] * FRAMES] * 3)


if __name__ == "__main__":
    unittest.main()
