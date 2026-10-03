import json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "mod")
ELEKLOADER = os.environ.get("ELEKLOADER_DIR", os.path.join(ROOT, "..", "elekloader"))
STOCK = os.environ.get("ELEKLOADER_STOCK") or os.environ.get("DIGITAKT_OS") \
    or os.path.join(ROOT, "..", "Digitakt_OS1.53.syx")


class ModJson(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(MOD, "mod.json")) as f:
            self.mod = json.load(f)

    def test_required_keys(self):
        for k in ("id", "version", "title", "device", "os", "sources", "requires"):
            self.assertIn(k, self.mod)
        self.assertIn("core", self.mod["requires"])

    def test_sources_exist(self):
        for s in self.mod["sources"]:
            self.assertTrue(os.path.isfile(os.path.join(MOD, s)), s)

    def test_machine_registered(self):
        contrib = [c for c in self.mod.get("contribute", []) if c["to"] == "core_machines"]
        self.assertEqual(len(contrib), 1)
        self.assertIn("machine:6", self.mod["resources"]["names"])
        sym = contrib[0]["relocs"][0][2].split(":", 1)[1]
        with open(os.path.join(MOD, "machine.s")) as f:
            self.assertIn(sym + ":", f.read())

    def test_handlers_defined(self):
        src = ""
        for s in self.mod["sources"]:
            with open(os.path.join(MOD, s)) as f:
                src += f.read()
        for sub in self.mod.get("subscribe", []):
            self.assertIn(sub["fn"] + "(", src)


class Build(unittest.TestCase):
    def test_builds(self):
        if not os.path.isfile(STOCK):
            self.skipTest("stock OS not found: %s" % STOCK)
        env = dict(os.environ, ELEKLOADER_STOCK=STOCK,
                   PYTHONPATH=ELEKLOADER + os.pathsep + os.environ.get("PYTHONPATH", ""))
        if not (shutil.which("m68k-linux-gnu-gcc") or "ELEKLOADER_CROSS" in env):
            if shutil.which("m68k-elf-gcc"):
                env["ELEKLOADER_CROSS"] = "m68k-elf-"
            else:
                self.skipTest("no m68k cross toolchain")
        with tempfile.TemporaryDirectory() as out:
            r = subprocess.run([sys.executable, "-m", "elekloader.sdk.build", MOD, "--out", out],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(any(f.endswith(".elemod") for f in os.listdir(out)))


if __name__ == "__main__":
    unittest.main()
