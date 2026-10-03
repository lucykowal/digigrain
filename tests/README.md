# Tests

- `test_build.py` — stdlib smoke test: `mod.json` is well formed and the mod builds (skipped, with a reason, if the stock OS or toolchain is missing).
- `emu/` — reserved for Unicorn (ColdFire) harnesses that run individual hooks in isolation, following `../digi1_mods/tests/emu_*.py`. Install with `pip install -r requirements-dev.txt`.
