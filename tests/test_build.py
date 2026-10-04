"""Repo-level tests that apply to every mod under mods/: mod.json is well formed, sources exist, the
dependency rule holds, and each mod builds (staged with common/, as scripts/build.sh does)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_boundaries  # noqa: E402
import stage_mod  # noqa: E402

ELEKLOADER = os.environ.get("ELEKLOADER_DIR", os.path.join(ROOT, "..", "elekloader"))
STOCK = os.environ.get("ELEKLOADER_STOCK") or os.environ.get("DIGITAKT_OS") \
    or os.path.join(ROOT, "..", "Digitakt_OS1.53.syx")


def mods():
    d = os.path.join(ROOT, "mods")
    return sorted(m for m in os.listdir(d) if os.path.isfile(os.path.join(d, m, "mod.json")))


class ModJson(unittest.TestCase):
    def test_every_mod(self):
        self.assertTrue(mods(), "no mods under mods/")
        for name in mods():
            with self.subTest(mod=name):
                with open(os.path.join(ROOT, "mods", name, "mod.json")) as f:
                    mod = json.load(f)
                self.assertEqual(mod["id"], name, "mod id must equal its directory name")
                for k in ("id", "version", "title", "device", "os", "sources", "requires"):
                    self.assertIn(k, mod)
                self.assertIn("core", mod["requires"])
                for s in mod["sources"]:
                    self.assertTrue(os.path.isfile(check_boundaries.resolve(ROOT, name, s)), s)
                src = ""
                for s in mod["sources"]:
                    with open(check_boundaries.resolve(ROOT, name, s)) as f:
                        src += f.read()
                for sub in mod.get("subscribe", []):
                    self.assertIn(sub["fn"] + "(", src)


class Boundaries(unittest.TestCase):
    def test_repo_is_clean(self):
        self.assertEqual(check_boundaries.main(["--root", ROOT]), 0)

    def make_tree(self, tmp, **files):
        for rel, text in files.items():
            p = os.path.join(tmp, rel.replace("__", "/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(text)

    def errs(self, tmp, name):
        return check_boundaries.check_mod(tmp, name)

    def tree(self, tmp, a_src="", a_json=None, b_src="void b(void){}\n"):
        a_json = a_json or {"id": "a", "sources": ["src/a.c"], "requires": ["core"]}
        os.makedirs(os.path.join(tmp, "common", "include"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "common", "src"), exist_ok=True)
        self.make_tree(tmp, mods__a__src__a_c=a_src, mods__b__src__b_c=b_src)
        for n, j in (("a", a_json), ("b", {"id": "b", "sources": ["src/b.c"], "requires": ["core"]})):
            with open(os.path.join(tmp, "mods", n, "mod.json"), "w") as f:
                json.dump(j, f)
        os.rename(os.path.join(tmp, "mods", "a", "src", "a_c"), os.path.join(tmp, "mods", "a", "src", "a.c"))
        os.rename(os.path.join(tmp, "mods", "b", "src", "b_c"), os.path.join(tmp, "mods", "b", "src", "b.c"))

    def test_clean_with_common_include(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_tree(tmp, common__include__x_h="#define X 1\n")
            self.tree(tmp, a_src='#include "common/include/x.h"\n')
            self.assertEqual(self.errs(tmp, "a"), [])

    def test_mod_requiring_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.tree(tmp, a_json={"id": "a", "sources": ["src/a.c"], "requires": ["core", "b"]})
            self.assertTrue(any("requires 'b'" in e for e in self.errs(tmp, "a")))

    def test_include_of_other_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.tree(tmp, a_src='#include "../../b/src/b.c"\n')
            self.assertTrue(self.errs(tmp, "a"))

    def test_source_of_other_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.tree(tmp, a_json={"id": "a", "sources": ["src/a.c", "../b/src/b.c"], "requires": ["core"]})
            self.assertTrue(any("outside src/" in e for e in self.errs(tmp, "a")))

    def test_mentions_other_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.tree(tmp, a_src="/* see mods/b/src/b.c */\n")
            self.assertTrue(any("another mod" in e for e in self.errs(tmp, "a")))


class Stage(unittest.TestCase):
    def test_stage_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = stage_mod.stage(ROOT, mods()[0], os.path.join(tmp, "stage"))
            self.assertTrue(os.path.isfile(os.path.join(out, "mod.json")))
            self.assertTrue(os.path.isdir(os.path.join(out, "src")))
            self.assertEqual(os.path.realpath(os.path.join(out, "common")), os.path.realpath(os.path.join(ROOT, "common")))


class Build(unittest.TestCase):
    def env(self):
        if not os.path.isfile(STOCK):
            self.skipTest("stock OS not found: %s" % STOCK)
        env = dict(os.environ, ELEKLOADER_STOCK=STOCK,
                   PYTHONPATH=ELEKLOADER + os.pathsep + os.environ.get("PYTHONPATH", ""))
        if not (shutil.which("m68k-linux-gnu-gcc") or "ELEKLOADER_CROSS" in env):
            if shutil.which("m68k-elf-gcc"):
                env["ELEKLOADER_CROSS"] = "m68k-elf-"
            else:
                self.skipTest("no m68k cross toolchain")
        return env

    def test_every_mod_builds(self):
        env = self.env()
        for name in mods():
            with self.subTest(mod=name), tempfile.TemporaryDirectory() as tmp:
                st = stage_mod.stage(ROOT, name, os.path.join(tmp, "stage"))
                out = os.path.join(tmp, "out")
                r = subprocess.run([sys.executable, "-m", "elekloader.sdk.build", st, "--out", out],
                                   env=env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertTrue(any(f.endswith(".elemod") for f in os.listdir(out)))

    def test_common_is_reachable_from_a_mod(self):
        """A mod can compile a common/src file that includes a common/include header."""
        env = self.env()
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(os.path.join(ROOT, "templates", "mod"), os.path.join(tmp, "root", "mods", "probe"))
            root = os.path.join(tmp, "root")
            os.makedirs(os.path.join(root, "common", "include"))
            os.makedirs(os.path.join(root, "common", "src"))
            with open(os.path.join(root, "common", "include", "k.h"), "w") as f:
                f.write("int probe_k(void);\n")
            with open(os.path.join(root, "common", "src", "k.c"), "w") as f:
                f.write('#include "common/include/k.h"\nint probe_k(void) { return 7; }\n')
            mdir = os.path.join(root, "mods", "probe")
            os.rename(os.path.join(mdir, "src", "@NAME@.c"), os.path.join(mdir, "src", "probe.c"))
            with open(os.path.join(mdir, "src", "probe.c"), "w") as f:
                f.write('#include "common/include/k.h"\nvoid probe_tick(void *c) { (void)c; probe_k(); }\n')
            with open(os.path.join(mdir, "mod.json"), "w") as f:
                json.dump({"id": "probe", "version": "0.0.1", "title": "probe", "category": "Examples",
                           "license": "GPL-2.0-or-later", "description": "probe", "device": "digitakt-mk1",
                           "os": "1.53", "sources": ["src/probe.c", "common/src/k.c"], "requires": ["core"],
                           "subscribe": [{"event": "ev_tick", "fn": "probe_tick", "order": 50}]}, f)
            self.assertEqual(check_boundaries.main(["--root", root]), 0)
            st = stage_mod.stage(root, "probe", os.path.join(tmp, "stage"))
            r = subprocess.run([sys.executable, "-m", "elekloader.sdk.build", st, "--out", os.path.join(tmp, "out")],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Template(unittest.TestCase):
    def test_new_mod_scaffold_builds_and_passes_boundaries(self):
        env = Build.env(self)
        with tempfile.TemporaryDirectory() as tmp:
            for d in ("scripts", "templates", "tools"):
                shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d))
            os.makedirs(os.path.join(tmp, "mods"))
            os.makedirs(os.path.join(tmp, "common"))
            r = subprocess.run([os.path.join(tmp, "scripts", "new-mod.sh"), "my-mod"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(check_boundaries.main(["--root", tmp]), 0)
            st = stage_mod.stage(tmp, "my-mod", os.path.join(tmp, "stage"))
            r = subprocess.run([sys.executable, "-m", "elekloader.sdk.build", st, "--out", os.path.join(tmp, "out")],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
