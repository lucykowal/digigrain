"""Host tests for mod/readout.c (RATE / SPRD / ENV value readouts): the C code (built as a shared
library) against an independent Python model of the mappings granular.c renders."""
import ctypes
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRD, ENV, RATE = 2, 3, 0x6e


def model(pid, v):
    k = v - 64
    a = abs(k)
    if pid == ENV:
        if k == 0:
            return "SINE"
        return ("GATE %d%%" if k < 0 else "DECAY %d%%") % (a * 4 * 100 // 256)
    if a <= 1:
        return "OFF"
    if pid == SPRD:
        amount = min(64, (a - 1) * 64 // 62)
        return ("POS %d%%" if k < 0 else "PIT %d%%") % (amount * 100 // 64)
    hz16 = 4 + (a - 1) * (a - 1) // 2
    if hz16 < 160:
        h = hz16 * 100 // 16
        s = "%d.%02d" % (h // 100, h % 100)
    elif hz16 < 1600:
        t = hz16 * 10 // 16
        s = "%d.%d" % (t // 10, t % 10)
    else:
        s = "%d" % (hz16 // 16)
    return ("~" if k > 0 else "") + s + "Hz"


@unittest.skipUnless(shutil.which("cc"), "no host C compiler")
class ReadoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        lib = os.path.join(cls.tmp, "libreadout.so")
        subprocess.check_call(["cc", "-O2", "-shared", "-fPIC", "-Wall", "-Werror", "-o", lib,
                               os.path.join(ROOT, "mod", "readout.c")])
        cls.lib = ctypes.CDLL(lib)
        cls.lib.rd_format.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def fmt(self, pid, word):
        buf = ctypes.create_string_buffer(b"\xaa" * 32)
        r = self.lib.rd_format(pid, word, buf)
        return r, buf.value.decode()

    def test_matches_model_for_every_knob_value(self):
        for pid in (SPRD, ENV, RATE):
            for v in range(128):
                r, s = self.fmt(pid, v << 8)
                self.assertEqual((r, s), (1, model(pid, v)), (pid, v))

    def test_known_values(self):
        self.assertEqual(self.fmt(RATE, 64 << 8)[1], "OFF")
        self.assertEqual(self.fmt(RATE, 65 << 8)[1], "OFF")
        self.assertEqual(self.fmt(RATE, 63 << 8)[1], "OFF")
        self.assertEqual(self.fmt(RATE, 62 << 8)[1], "0.25Hz")      # kk 1 -> hz16 4
        self.assertEqual(self.fmt(RATE, 36 << 8)[1], "23.0Hz")      # the machine's default
        self.assertEqual(self.fmt(RATE, 0)[1], "124Hz")        # a = 64 is one step past the stock range end
        self.assertEqual(self.fmt(RATE, 127 << 8)[1], "~120Hz")
        self.assertEqual(self.fmt(SPRD, 64 << 8)[1], "OFF")
        self.assertEqual(self.fmt(SPRD, 0)[1], "POS 100%")
        self.assertEqual(self.fmt(SPRD, 127 << 8)[1], "PIT 100%")
        self.assertEqual(self.fmt(ENV, 64 << 8)[1], "SINE")
        self.assertEqual(self.fmt(ENV, 0)[1], "GATE 100%")
        self.assertEqual(self.fmt(ENV, 127 << 8)[1], "DECAY 98%")

    def test_word_fraction_and_range_are_tolerated(self):
        self.assertEqual(self.fmt(ENV, (64 << 8) | 0xff)[1], "SINE")
        self.assertEqual(self.fmt(RATE, 0x7fff)[1], "~120Hz")
        self.assertEqual(self.fmt(RATE, -5)[1], "124Hz")
        self.assertEqual(self.fmt(ENV, 0x10000)[1], "DECAY 98%")

    def test_other_ids_untouched(self):
        buf = ctypes.create_string_buffer(b"\xaa" * 8, 8)
        self.assertEqual(self.lib.rd_format(0x70, 0x4000, buf), 0)
        self.assertEqual(buf.raw, b"\xaa" * 8)

    def test_fits_the_buffer(self):
        for pid in (SPRD, ENV, RATE):
            for v in range(128):
                self.assertLessEqual(len(self.fmt(pid, v << 8)[1]), 9)

    def test_rate_mapping_matches_engine(self):
        """granular.c's render computes hz16 the same way; keep the two in step."""
        with open(os.path.join(ROOT, "mod", "granular.c")) as f:
            src = f.read()
        self.assertIn("hz16 = 4 + ((u32)(kk * kk) >> 1);", src)
        self.assertIn("kk = (kk < 0 ? -kk : kk) - 1;", src)
        self.assertIn("*amount = ((k < 0 ? -k : k) - 1) * 64 / 62;", src)
        self.assertIn("p.shape = ((int)(w[W_ENV] >> 8) - 64) * 4;", src)


if __name__ == "__main__":
    unittest.main()
