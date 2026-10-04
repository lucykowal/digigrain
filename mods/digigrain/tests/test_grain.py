"""Host tests for mods/digigrain/src/grain.c: the C code (built as a shared library) against an
independent Python model of the same integer arithmetic, plus behaviour checks."""
import ctypes
import importlib.util
import math
import os
import random
import shutil
import subprocess
import tempfile
import unittest

MOD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR_MAX, FRAMES, HALF = 8, 32, 16
M32 = 0xffffffff
WPH_ONE = 1 << 24

_spec = importlib.util.spec_from_file_location("gen_tables", os.path.join(MOD_DIR, "tools", "gen_tables.py"))
_gt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gt)
SINE, GATE, DECAY, RATIO, AVG = _gt.tables()


class Grain(ctypes.Structure):
    _fields_ = [("idx", ctypes.c_int), ("frac", ctypes.c_uint), ("inc", ctypes.c_uint),
                ("wph", ctypes.c_uint), ("winc", ctypes.c_uint), ("delay", ctypes.c_int),
                ("active", ctypes.c_int)]


class Voice(ctypes.Structure):
    _fields_ = [("g", Grain * GR_MAX), ("next_in", ctypes.c_int), ("rng", ctypes.c_uint),
                ("win_shape", ctypes.c_int), ("win", ctypes.c_ushort * 256), ("last", ctypes.c_int)]


class Params(ctypes.Structure):
    _fields_ = [("pos", ctypes.c_int), ("rate", ctypes.c_uint), ("mode", ctypes.c_int),
                ("interval", ctypes.c_int), ("ratio", ctypes.c_int), ("spread_pos", ctypes.c_int),
                ("spread_tune", ctypes.c_int), ("shape", ctypes.c_int)]


def clampi(x, lo, hi):
    return max(lo, min(hi, x))


def length(p):
    iv = clampi(p["interval"], 1, 1 << 19)
    return clampi((iv * clampi(p["ratio"], 1, 4096)) >> 8, 16, 65535)


def avg_level(shape):
    if shape < 0:
        return AVG[0] + (((AVG[1] - AVG[0]) * -shape) >> 8)
    return AVG[0] + (((AVG[2] - AVG[0]) * shape) >> 8)


def model_norm(p):
    t = min(1024, (clampi(p["interval"], 1, 1 << 19) << 8) // length(p))
    return min(256, (t << 8) // (avg_level(clampi(p["shape"], -256, 256)) or 1))


def window(shape):
    """The Q15 live window for a shape (what build_win stores, halved)."""
    if shape == 0:
        return SINE
    return _gt.blend(SINE, GATE if shape < 0 else DECAY, abs(shape))


class Model:
    """Python mirror of gr_reset / gr_block."""

    def __init__(self, seed):
        self.g, self.next_in, self.rng, self.last = [], 0, seed or 0x9e3779b9, 0

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
        jr = (n >> 2) // 64 * clampi(p["spread_pos"], 0, 64)
        if jr > 0:
            pos += self.rnd() % (2 * jr + 1) - jr
        pos = clampi(pos, 0, n - 2)
        pr = 65536
        m = clampi(p["spread_tune"], 0, 64) * 12 // 64
        if m > 0:
            pr = RATIO[self.rnd() % (2 * m + 1) - m + 12]
        eff = max(256, ((p["rate"] >> 6) * (pr >> 6)) >> 4)
        self.g.append(dict(idx=pos, frac=0, inc=2 * eff, wph=0, winc=2 * (WPH_ONE // length(p)),
                           delay=delay >> 1))

    def block(self, pcm, p):
        n = len(pcm)
        acc = [0] * HALF
        ran = False
        if n >= 4:
            iv = clampi(p["interval"], 1, 1 << 24)
            if p["mode"] == 0:
                self.next_in = 0
            else:
                self.next_in = min(self.next_in, iv if p["mode"] == 1 else 2 * iv)
                while self.next_in < FRAMES:
                    self.start(p, n, max(self.next_in, 0))
                    self.next_in += iv if p["mode"] == 1 else self.rnd() % (2 * iv) + 1
                self.next_in -= FRAMES
            win = window(clampi(p["shape"], -256, 256))
            ran = bool(self.g)
            for g in list(self.g):
                for f in range(g["delay"], HALF):
                    if g["idx"] < 0 or g["idx"] >= n - 1 or g["wph"] >= WPH_ONE:
                        self.g.remove(g)
                        break
                    a, b = pcm[g["idx"]], pcm[g["idx"] + 1]
                    s = a + (((b - a) * (g["frac"] >> 2)) >> 14)
                    acc[f] += (s * win[g["wph"] >> 16]) >> 15
                    g["wph"] += g["winc"]
                    t = g["frac"] + g["inc"]
                    g["idx"] += t >> 16
                    g["frac"] = t & 0xffff
                g["delay"] = 0
        if not ran and not self.last:
            return [0] * FRAMES
        out, prev = [], self.last
        for x in acc:
            x = clampi(x, -32768, 32767)
            out += [(prev + x) >> 1, x]
            prev = x
        self.last = prev
        return out


@unittest.skipUnless(shutil.which("cc"), "no host C compiler")
class GrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        lib = os.path.join(cls.tmp, "libgrain.so")
        subprocess.check_call(["cc", "-O2", "-shared", "-fPIC", "-Wall", "-Werror",
                               "-I", os.path.join(MOD_DIR, "src"), "-o", lib,
                               os.path.join(MOD_DIR, "src", "grain.c")])
        cls.lib = ctypes.CDLL(lib)
        cls.lib.gr_block.argtypes = [ctypes.POINTER(Voice), ctypes.POINTER(ctypes.c_short), ctypes.c_int,
                                     ctypes.POINTER(Params), ctypes.POINTER(ctypes.c_int)]
        cls.lib.gr_reset.argtypes = [ctypes.POINTER(Voice), ctypes.c_uint]
        cls.lib.gr_active.argtypes = [ctypes.POINTER(Voice)]
        cls.lib.gr_norm.argtypes = [ctypes.POINTER(Params)]
        cls.lib.gr_length.argtypes = [ctypes.POINTER(Params)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    D = dict(pos=1000, rate=65536, mode=1, interval=1200, ratio=512, spread_pos=0, spread_tune=0, shape=0)

    def params(self, **kw):
        d = dict(self.D)
        d.update(kw)
        return d

    def new_voice(self, seed=1):
        v = Voice()
        self.lib.gr_reset(ctypes.byref(v), seed)
        return v

    def block(self, v, arr, n, p, out=None):
        o = (ctypes.c_int * FRAMES)()
        self.lib.gr_block(ctypes.byref(v), arr, n, ctypes.byref(Params(**p)), o)
        return list(o)

    def run_c(self, pcm, p, blocks, seed=1):
        arr = (ctypes.c_short * len(pcm))(*pcm)
        v = self.new_voice(seed)
        return v, [self.block(v, arr, len(pcm), p) for _ in range(blocks)]

    def run_model(self, pcm, p, blocks, seed=1):
        m = Model(seed)
        return [m.block(pcm, p) for _ in range(blocks)]

    def active(self, v):
        return self.lib.gr_active(ctypes.byref(v))

    @staticmethod
    def sine(n=48000, hz=440, amp=16384):
        return [int(amp * math.sin(2 * math.pi * hz * i / 48000)) for i in range(n)]

    # --- exactness -------------------------------------------------------------------------
    def test_matches_python_model(self):
        pcm = self.sine()
        cases = [self.params(),
                 self.params(rate=77777, pos=30000),
                 self.params(mode=2, interval=600),
                 self.params(mode=2, interval=400, spread_pos=64, spread_tune=64, shape=-100),
                 self.params(interval=700, spread_tune=40, shape=200, rate=3 * 65536, ratio=2048),
                 self.params(interval=300, shape=-256, pos=40000, spread_pos=20, ratio=64)]
        for i, p in enumerate(cases):
            _, out = self.run_c(pcm, p, 150, seed=7 + i)
            self.assertEqual(out, self.run_model(pcm, p, 150, seed=7 + i), "case %d: %s" % (i, p))

    def test_fuzz_against_model_including_edges(self):
        rng = random.Random(1234)
        for case in range(300):
            n = rng.choice([4, 40, 200, 777, 3000, 20000])
            pcm = [rng.randint(-20000, 20000) for _ in range(n)]
            p = self.params(pos=rng.choice([-5, 0, 1, n // 2, n - 3, n - 2, n + 50, rng.randint(0, n)]),
                            rate=rng.choice([0, 4096, 20000, 65536, 100000, 3 * 65536, 12 * 65536]),
                            mode=rng.choice([0, 1, 1, 2, 2]),
                            interval=rng.choice([1, 7, 50, 300, 2000, 9000, 192000, 700000]),
                            ratio=rng.choice([1, 64, 128, 256, 1000, 2048, 4096, 5000]),
                            spread_pos=rng.choice([0, 0, 1, 32, 64, 100]),
                            spread_tune=rng.choice([0, 0, 5, 32, 64, 100]),
                            shape=rng.choice([-300, -256, -90, 0, 0, 33, 256, 300]))
            seed = rng.randint(1, 2 ** 32 - 1)
            _, out = self.run_c(pcm, p, 70, seed=seed)
            self.assertEqual(out, self.run_model(pcm, p, 70, seed=seed), "case %d n=%d %s" % (case, n, p))

    def test_param_changes_mid_run_match_model(self):
        rng = random.Random(99)
        pcm = [rng.randint(-20000, 20000) for _ in range(30000)]
        arr = (ctypes.c_short * len(pcm))(*pcm)
        v, m = self.new_voice(5), Model(5)
        for b in range(400):
            if b % 25 == 0:
                p = self.params(pos=rng.randint(0, 29000), rate=rng.choice([16384, 65536, 200000]),
                                mode=rng.choice([0, 1, 2]), interval=rng.choice([30, 400, 5000, 192000]),
                                ratio=rng.choice([64, 256, 2048]), spread_pos=rng.choice([0, 40]),
                                spread_tune=rng.choice([0, 40]), shape=rng.choice([-200, 0, 150]))
            self.assertEqual(self.block(v, arr, len(pcm), p), m.block(pcm, p), "block %d" % b)

    def test_norm_and_length_match_model(self):
        for p in (self.params(), self.params(interval=100, shape=-200), self.params(ratio=2048, interval=50),
                  self.params(interval=190000, shape=250, ratio=64), self.params(interval=1, ratio=1)):
            self.assertEqual(self.lib.gr_norm(ctypes.byref(Params(**p))), model_norm(p), p)
            self.assertEqual(self.lib.gr_length(ctypes.byref(Params(**p))), length(p), p)

    # --- behaviour -------------------------------------------------------------------------
    def test_grain_length_is_ratio_times_interval_regardless_of_pitch(self):
        pcm = [10000] * 200000                       # DC: the output is the window itself
        arr = (ctypes.c_short * len(pcm))(*pcm)
        for ratio, interval in ((192, 8000), (256, 5000), (64, 20000), (128, 12000)):    # length <= interval
            expect = length(self.params(ratio=ratio, interval=interval))
            for rate in (16384, 65536, 4 * 65536):
                p = self.params(rate=rate, ratio=ratio, interval=interval, shape=-256)
                v = self.new_voice()
                flat = []
                for _ in range(expect // 32 + 3):
                    flat += self.block(v, arr, len(pcm), p)
                n = sum(1 for x in flat[:interval] if x > 100)      # before the second grain starts
                self.assertAlmostEqual(n, expect, delta=expect * 0.04 + 8,
                                       msg="ratio %d interval %d rate %d" % (ratio, interval, rate))

    def test_periodic_rtio_8_never_exceeds_eight_grains(self):
        pcm = self.sine(200000, 110)
        arr = (ctypes.c_short * len(pcm))(*pcm)
        for rate in (16384, 65536, 4 * 65536):
            for mode in (1, 2):
                v = self.new_voice(3)
                p = self.params(rate=rate, mode=mode, interval=2000, ratio=2048, spread_tune=30)
                peak = 0
                for _ in range(1500):
                    self.block(v, arr, len(pcm), p)
                    peak = max(peak, self.active(v))
                    self.assertLessEqual(peak, GR_MAX)
                self.assertGreaterEqual(peak, 6 if mode == 1 else 4, "rate %d mode %d" % (rate, mode))

    def test_cost_driver_is_independent_of_pitch(self):
        # the number of live grains depends on RTIO and the interval only, not on the playback rate
        pcm = self.sine(200000, 110)
        arr = (ctypes.c_short * len(pcm))(*pcm)
        means = []
        for rate in (16384, 65536, 4 * 65536):
            v = self.new_voice()
            p = self.params(rate=rate, interval=1000, ratio=1024)
            counts = []
            for i in range(800):
                self.block(v, arr, len(pcm), p)
                if i > 200:
                    counts.append(self.active(v))
            means.append(sum(counts) / len(counts))
        self.assertLess(max(means) - min(means), 0.6)
        self.assertAlmostEqual(means[1], 4.0, delta=0.6)

    def test_mode_none_is_silent_and_spawns_nothing(self):
        v, out = self.run_c(self.sine(), self.params(mode=0), 20)
        self.assertEqual(self.active(v), 0)
        self.assertTrue(all(x == 0 for b in out for x in b))

    def test_issue_19_faster_rate_takes_effect_within_one_interval(self):
        pcm = self.sine(200000, 200)
        arr = (ctypes.c_short * len(pcm))(*pcm)
        for mode in (1, 2):
            v = self.new_voice(11)
            slow = self.params(mode=mode, interval=192000, ratio=64)
            for _ in range(60):
                self.block(v, arr, len(pcm), slow)
            before = self.active(v)
            fast = self.params(mode=mode, interval=400, ratio=64)
            for b in range(2 * 400 // 32 + 3):                 # mode 2 waits at most 2 * interval
                self.block(v, arr, len(pcm), fast)
            self.assertGreater(self.active(v), before, "mode %d: no new grain after the rate change" % mode)

    def test_leaving_noon_starts_a_grain_in_the_first_block(self):
        pcm = self.sine()
        arr = (ctypes.c_short * len(pcm))(*pcm)
        v = self.new_voice()
        for _ in range(20):
            self.block(v, arr, len(pcm), self.params(mode=0))
        self.block(v, arr, len(pcm), self.params(mode=1, interval=100000))
        self.assertEqual(self.active(v), 1)

    def test_spread_zero_is_exact_and_spread_varies(self):
        pcm = list(range(0, 30000))
        arr = (ctypes.c_short * len(pcm))(*pcm)
        pos, starts, incs = 10000, set(), set()
        for seed in range(1, 60):
            v = self.new_voice(seed)
            self.block(v, arr, len(pcm), self.params(pos=pos, interval=100000))
            starts.add(v.g[0].idx - 32)                           # unity speed: advanced 32 frames
            incs.add(v.g[0].inc // 2)
        self.assertEqual(starts, {pos})
        self.assertEqual(incs, {65536})
        starts, incs = set(), set()
        for seed in range(1, 80):
            v = self.new_voice(seed)
            self.block(v, arr, len(pcm), self.params(pos=pos, interval=100000, spread_pos=64))
            starts.add(v.g[0].idx - 32)
        self.assertGreater(len(starts), 30)
        self.assertTrue(all(abs(s - pos) <= len(pcm) // 4 for s in starts))
        for seed in range(1, 80):
            v = self.new_voice(seed)
            self.block(v, arr, len(pcm), self.params(pos=pos, interval=100000, spread_tune=64))
            incs.add(v.g[0].inc // 2)
        self.assertGreater(len(incs), 8)
        self.assertTrue(all(32768 <= i <= 131072 for i in incs))          # +-12 semitones

    def test_rate_is_pitch(self):
        pcm = self.sine(hz=200)

        def crossings_per_sample(rate):
            _, out = self.run_c(pcm, self.params(rate=rate, interval=4800, ratio=256, shape=-256), 150)
            flat = [x for b in out for x in b]
            sounding = sum(1 for x in flat if abs(x) > 50)
            return sum(1 for a, b in zip(flat, flat[1:]) if a < 0 <= b) / sounding
        self.assertAlmostEqual(crossings_per_sample(2 * 65536) / crossings_per_sample(65536), 2.0, delta=0.25)

    def test_shape_gate_flat_and_decay_falls(self):
        pcm = [10000] * 48000
        _, gate = self.run_c(pcm, self.params(interval=2400, ratio=256, shape=-256), 80)
        _, dec = self.run_c(pcm, self.params(interval=2400, ratio=256, shape=256), 80)
        g = [x for b in gate for x in b][:2400]
        d = [x for b in dec for x in b][:2400]
        self.assertGreater(min(g[100:2300]), 9900)                       # flat top
        self.assertGreater(d[200], d[1200] * 2)                          # decays
        self.assertGreater(d[1200], d[2200])

    def test_pool_exhaustion_and_edges_are_safe(self):
        pcm = self.sine(n=64)
        p = self.params(pos=60, interval=1, rate=7 * 65536, ratio=2048, spread_pos=64, spread_tune=64, mode=2)
        v, out = self.run_c(pcm, p, 50, seed=0xdeadbeef)
        self.assertLessEqual(self.active(v), GR_MAX)
        self.assertTrue(all(-32768 <= x <= 32767 for b in out for x in b))

    def test_short_sample_is_ignored(self):
        _, out = self.run_c([5, 6, 7], self.params(), 3)
        self.assertEqual(out, [[0] * FRAMES] * 3)


if __name__ == "__main__":
    unittest.main()
