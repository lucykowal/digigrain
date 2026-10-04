# common

Code shared by more than one mod. Empty until a second mod needs something the first one already has.

- `include/` headers, `src/` C/asm, `tests/` host tests (run by `make test`).
- **Libraries, not mods:** nothing here may include or name anything under `mods/`.
- **Opt-in:** a mod lists `common/src/x.c` in its `mod.json` `sources` and writes `#include "common/include/x.h"`.
  The build stages `common/` beside the mod (`tools/stage_mod.py`), so nothing is picked up implicitly.
- **Extract on second use.** Copy first; when a second mod needs the same code, move it here in its own `refactor(common)`
  commit and switch both mods over. Candidates: hook-bus ABI headers, firmware address constants, fixed-point/EMAC helpers.
- Changing anything here needs `make check` green for every mod. Keep it stable; add, do not repurpose.
- `.o` files are named after the source basename: keep names here unique (no `util.c`) and distinct from mod sources.
- Prefix globals with `common_` (the symbols share one address space with every loaded mod).
