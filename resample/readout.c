/* SPDX-License-Identifier: GPL-2.0-or-later */
/* digiresample: value readouts for the RESAMPLE page's REC/PLAY and SRC knobs (OS 1.53).
 *
 * Same hooks as digigrain (page.s): 0x400657ee(id, word) and 0x4000f324(obj, id, word, out) turn a
 * parameter's 8.8 word into text. Pure functions on caller-supplied memory, so the same code runs on the
 * host (tests/test_resample.py). Text is at most 7 characters: that is what fits under a knob.
 *
 *   D (id 1)  REC for the knob value 0, PLAY otherwise (resample.c: rs_mode)
 *   G (id 2)  the RECORDER's source names, 0..16 (clamped; resample.c: rs_src)
 */
#define RD_MODE 1         /* descriptor ids: page.s / tools/gen_resample_sites.py */
#define RD_SRC  2

static const char *const src_name[17] = {
    "IN L", "IN R", "IN LR", "MAIN L", "MAIN R", "MAIN LR", "USB L", "USB R", "USB LR",
    "TRK1", "TRK2", "TRK3", "TRK4", "TRK5", "TRK6", "TRK7", "TRK8",
};

/* Writes the NUL-terminated readout for `word` of descriptor `id`.
 * Returns 1 if the id is one of ours, 0 (buffer untouched) if not. */
int rd_format(int id, int word, char *buf)
{
    int v = word >> 8;
    const char *s;
    if (id != RD_MODE && id != RD_SRC)
        return 0;
    if (id == RD_MODE) {
        s = v ? "PLAY" : "REC";
    } else {
        v = v < 0 ? 0 : v > 16 ? 16 : v;
        s = src_name[v];
    }
    while (*s)
        *buf++ = *s++;
    *buf = 0;
    return 1;
}
