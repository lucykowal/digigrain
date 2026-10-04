"""Host tests for resample/ (RESAMPLE machine): the readout text of the REC/PLAY and SRC knobs, and the
pure knob decodes in resample.c, both built as a shared library. The recorder/voice glue needs the firmware
(emulator; see the issue "Verify RESAMPLE")."""
import ctypes
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODE, SRC = 1, 2
NAMES = ["IN L", "IN R", "IN LR", "MAIN L", "MAIN R", "MAIN LR", "USB L", "USB R", "USB LR",
         "TRK1", "TRK2", "TRK3", "TRK4", "TRK5", "TRK6", "TRK7", "TRK8"]


@unittest.skipUnless(shutil.which("cc"), "no host C compiler")
class ResampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        stub = os.path.join(cls.tmp, "stub.c")
        with open(stub, "w") as f:
            f.write("volatile unsigned char core_track_machine[8];\n")
        lib = os.path.join(cls.tmp, "rs.so")
        subprocess.check_call(["cc", "-shared", "-fPIC", "-Wall", "-Wno-int-to-pointer-cast", "-o", lib, stub,
                               os.path.join(ROOT, "resample", "readout.c"),
                               os.path.join(ROOT, "resample", "resample.c")])
        cls.lib = ctypes.CDLL(lib)
        cls.lib.rd_format.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
        cls.lib.rs_mode.argtypes = [ctypes.c_uint]
        cls.lib.rs_src.argtypes = [ctypes.c_uint]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def fmt(self, pid, word):
        buf = ctypes.create_string_buffer(16)
        ok = self.lib.rd_format(pid, word, buf)
        return ok, buf.value.decode()

    def test_mode_text(self):
        self.assertEqual(self.fmt(MODE, 0), (1, "REC"))
        self.assertEqual(self.fmt(MODE, 0x0100), (1, "PLAY"))

    def test_source_names_fit_under_a_knob(self):
        for v, name in enumerate(NAMES):
            ok, s = self.fmt(SRC, v << 8)
            self.assertEqual((ok, s), (1, name))
            self.assertLessEqual(len(s), 7)

    def test_source_is_clamped(self):
        self.assertEqual(self.fmt(SRC, 127 << 8)[1], "TRK8")
        self.assertEqual(self.fmt(SRC, -256)[1], "IN L")

    def test_other_ids_untouched(self):
        buf = ctypes.create_string_buffer(b"x", 16)
        for pid in (0, 3, 0x6e):
            self.assertEqual(self.lib.rd_format(pid, 0, buf), 0)
        self.assertEqual(buf.value, b"x")

    def test_knob_decodes(self):
        self.assertEqual([self.lib.rs_mode(w) for w in (0, 0x80, 0xff, 0x100)], [0, 0, 0, 1])
        self.assertEqual([self.lib.rs_src(v << 8) for v in (0, 5, 16, 17, 127)], [0, 5, 16, 16, 16])


if __name__ == "__main__":
    unittest.main()
