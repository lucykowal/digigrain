---
name: digitakt-test
description: Test a Digitakt mod in emulator or on hardware
slug: digitakt-test
---

# Digitakt Mod Testing

Verify mod correctness before flashing hardware.

## Testing Strategies

### 1. Emulator Testing (Recommended First)

**Unicorn emulation** (per-hook unit tests):
- Run individual hook handlers in isolation
- Bit-perfect M68k CPU emulation
- Fast, deterministic, no hardware needed

**Full firmware emulation** (digiemu):
- Boot custom firmware in Unicorn with all mods loaded
- Interactive: drive keys, encoders, pads
- Verify integration with core and other mods
- Test event ordering and hook interactions

### 2. Hardware Testing

1. **Build test firmware**
   ```bash
   python -m elekloader.patch --stock <stock.syx> --mod core.elemod --mod <your-mod.elemod> --out test.syx
   ```

2. **Flash to Digitakt** (via SysEx or Elektron tool)
   - Backup your current OS first
   - Factory reset recovers stock OS (bootloader untouched)

3. **Interactive validation**
   - Test all mapped keys/encoders
   - Verify settings UI (if applicable)
   - Check for crashes or hangs
   - Monitor current draw (some mods use CPU-intensive hooks)

## Pre-Test Checklist

- ✓ `mod.json` declares all subscribed events
- ✓ All `sources` files exist and compile
- ✓ No patch site conflicts (lint output clean)
- ✓ Dependencies met (core.elemod present)
- ✓ Resource allocations don't overlap (settings pages, kit slots)
- ✓ Stock bytes in `sites` match target OS exactly

## Test Plan Structure

For each hook your mod subscribes to:
1. **Unit test**: Hook handler in isolation (Unicorn)
2. **Integration test**: Hook with core mod present
3. **Composition test**: Hook with other mods (if combined)
4. **Hardware test**: Interactive verification on device

## Reference

- **Emulator**: digiemu in elektron-firmware-tool repo
- **Unicorn docs**: https://www.unicorn-engine.org/
- **Test patterns**: digi1_mods tests/ directory (reference implementations)

