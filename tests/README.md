# Tests

- Here (`tests/`): checks that apply to every mod: `test_build.py` covers `mod.json` shape, the dependency rule
  (`tools/check_boundaries.py`), staging, `common/` reachability, the `new-mod` scaffold, and that each mod builds (skipped,
  with a reason, if the stock OS or toolchain is missing).
- `common/tests/`: host tests of shared code.
- `mods/<name>/tests/`: that mod's host tests; `mods/<name>/tests/emu/` holds its Unicorn/digiemu harnesses (install with
  `pip install -r requirements-dev.txt`).
- `make test` runs all of them (`MOD=<name>` for one mod's tests plus the shared ones).
