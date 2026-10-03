---
name: digitakt-debug
description: Debug and lint Digitakt mods
slug: digitakt-debug
---

# Digitakt Mod Debugging & Linting

Verify mod correctness and diagnose build/runtime issues.

## Linting

**Run after build**:
```bash
python -m elekloader.lint <mod.elemod> --stock <Digitakt_OS1.53.syx> --with core.elemod --json
```

**Output**: JSON report of warnings and errors.

**Common linting errors**:

| Error | Cause | Fix |
|-------|-------|-----|
| "stock bytes don't match" | Firmware version mismatch | Update to correct stock OS file |
| "relocation out of range" | Code placed too far from reference | Check linker map, adjust section sizes |
| "undefined symbol" | Missing function/data | Check mod.json sources, verify all .c/.s files listed |
| "patch overlap" | Two mods claiming same firmware byte | Check resources, ensure no conflicts |
| "undefined resource" | Referenced but not claimed | Add to `resources` in mod.json |

## Build Diagnostics

**Check compilation output**:
```bash
python -m elekloader.sdk.build <moddir> --stock <os.syx> --verbose
```

**Look for**:
- Undefined symbols (missing sources or headers)
- Type mismatches in firmware function calls
- Relocation errors (absolute addresses used instead of relocatable references)

## Runtime Debugging

### Emulator Testing (Recommended)

**Unit test in Unicorn**:
- Run hook handler in isolation
- Step through with M68k debugger
- Inspect registers and memory

**Full firmware emulation**:
- Boot test.syx in digiemu
- Interactive: drive UI, check for crashes
- Monitor console output (if available)

### Hardware Testing

1. **Flash test firmware**: (See digitakt-test.md)

2. **Observe behavior**:
   - Hook into `ev_draw` to display debug info
   - Store state in kit slots (readable via SysEx or hardware UI)
   - Use LED/LCD to signal state

3. **Identify crash signatures**:
   - Bootloader LED pattern indicates crash
   - Factory reset recovers OS (bootloader untouched)

## Common Issues & Fixes

| Symptom | Likely Cause | Debug Steps |
|---------|--------------|-------------|
| Firmware won't boot | Patch conflict or overlap | Check linting output, verify stock bytes |
| Hook handler not called | Event not subscribed in mod.json | Verify `subscribe` array, rebuild |
| Settings page appears but corrupted | Settings struct size mismatch | Check sizeof() in code vs. mod.json declaration |
| Settings values don't persist | Not using kit slots correctly | Verify read/write calls, check slot numbers |
| Audio clicks/pops | Real-time hook doing allocation | Move work outside ev_tick, pre-allocate buffers |
| UI lag | ev_draw taking too long | Profile hook time, optimize hot paths |
| Mod works in emulator, crashes on hardware | Uninitialized memory or stack overflow | Add bounds checking, reduce stack usage |

## Validation Checklist

Before flashing hardware:

- ✓ Build succeeds without warnings
- ✓ `elekloader.lint` output clean (no errors)
- ✓ Test firmware boots in emulator
- ✓ All event handlers fire correctly
- ✓ Settings UI displays without corruption
- ✓ Kit storage read/write works
- ✓ No audio glitches in test patterns
- ✓ Encoders/keys respond correctly

## Advanced Debugging

### Linker Map

Extract symbol placement from built .elemod:

```bash
python -m elekloader.sdk.build <moddir> --stock <os.syx> --verbose --keep-artifacts
# Inspect .build/linker.map
```

### Object Dumps

Inspect compiled objects:

```bash
m68k-linux-gnu-objdump -h <file.o>   # Section layout
m68k-linux-gnu-objdump -S <file.o>   # Disassembly with source
```

### Patch Verification

Confirm patch is applied correctly:

```bash
xxd -s 0x12345 -l 16 test.syx | diff - expected.hex
```

## Reference

- **Linting docs**: elekloader `docs/LINTING.md`
- **Debugging patterns**: digi1_mods `tests/` directory
- **Emulator**: digiemu in elektron-firmware-tool repo

