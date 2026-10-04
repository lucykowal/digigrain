# digigrain

Granular SRC machine for the Elektron Digitakt mk1 (OS 1.53): GRANULAR, machine id 6. Status and open work: GitHub issues
labelled `mod:digigrain` (start with the "Tracking" issue). User-facing parameter docs: root `README.md`. Design notes for
the engine and the machine plumbing: skills `digitakt-dsp` and `digitakt-machines`.

## Layout

- `src/grain.c|h` pure fixed-point engine; `granular.c` firmware glue; `synth.s` render hooks; `page.s` SRC page layout
  and label hooks; `readout.c` value readouts; `machine.s` machine descriptor; `tables.h` generated.
- `tools/gen_tables.py` -> `src/tables.h`; `tools/gen_page_sites.py` -> descriptor and label-hook sites in `mod.json`.
- `tests/` host tests (`test_grain.py` bit-exact vs a Python model, `test_readout.py`); `tests/emu/` digiemu probes.

## Commands (run from the repo root)

```sh
make check MOD=digigrain
python3 -m unittest discover -s mods/digigrain/tests              # host tests
uv run --project ../digiemumac python mods/digigrain/tests/emu/grain_bench.py   # ColdFire instruction counts for gr_block
SYX=$PWD/out/digigrain/test.syx mods/digigrain/tests/emu/make_probe_home.sh      # emulator home for our build, then:
GRANULAR=1 FW_DIR=out/digigrain/emu/home/firmware/<newest> uv run --project ../digiemumac python mods/digigrain/tests/emu/scale_probe.py
```
