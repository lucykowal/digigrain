/* SPDX-License-Identifier: GPL-2.0-or-later */
/* digigrain: value readouts for the GRANULAR page's RATE, SPRD and ENV knobs (OS 1.53).
 *
 * The SRC page turns a parameter's word into text through 0x400657ee(id, word) (the knob-turn
 * title) and 0x4000f324(obj, id, word, out) (the value under a turning knob); page.s hooks both. Pure functions on caller-supplied memory, so the
 * same code runs on the host (tests/test_readout.py). The mappings mirror granular.c's render:
 * keep them in step (noon = knob value 64, "none" within one step of it).
 *
 *   RATE  OFF at noon; otherwise the grain rate in Hz (0.25 .. 120), "~" in front when it is
 *         the random (clockwise) side. hz16 = 4 + kk * kk / 2 with kk = |v - 64| - 1.
 *   SPRD  OFF at noon; counter-clockwise "POSnn%" (start-position jitter), clockwise "PITnn%"
 *         (random pitch, 100% = +-12 semitones). nn = engine amount (0..64) x 100 / 64.
 *   ENV   SINE at noon; counter-clockwise "GATEnn%", clockwise "DCAYnn%": the blend of the
 *         sine window with the gate or the quick decay, |shape| x 100 / 256, shape = (v - 64) x 4;
 *         the pure gate (100%) reads just "GATE".
 * At most 7 characters: that is what fits under a knob (the value replaces its caption).
 */
#define RD_SPRD 2         /* descriptor ids: page.s / tools/gen_page_sites.py */
#define RD_ENV  3
#define RD_RATE 0x6e      /* BR's descriptor, relabelled */

static char *put_str(char *p, const char *s)
{
    while (*s)
        *p++ = *s++;
    return p;
}

static char *put_uint(char *p, unsigned n, int min_digits)
{
    char t[8];
    int i = 0;
    do {
        t[i++] = (char)('0' + n % 10);
        n /= 10;
    } while (n && i < 8);
    while (i < min_digits && i < 8)
        t[i++] = '0';
    while (i)
        *p++ = t[--i];
    return p;
}

/* Writes the NUL-terminated readout for `word` (the 8.8 parameter word) of descriptor `id`.
 * Returns 1 if the id is one of ours, 0 (buffer untouched) if not. */
int rd_format(int id, int word, char *buf)
{
    int v = word >> 8, k, a, amount;
    unsigned hz16;
    char *p = buf;

    if (id != RD_RATE && id != RD_SPRD && id != RD_ENV)
        return 0;
    v = v < 0 ? 0 : v > 127 ? 127 : v;
    k = v - 64;
    a = k < 0 ? -k : k;
    if (id == RD_ENV) {
        if (k == 0) {
            p = put_str(p, "SINE");
        } else {
            unsigned pct = (unsigned)(a * 4 * 100 / 256);
            p = put_str(p, k < 0 ? "GATE" : "DCAY");
            if (pct < 100) {                  /* pure gate: just GATE */
                p = put_uint(p, pct, 1);
                *p++ = '%';
            }
        }
    } else if (a <= 1) {
        p = put_str(p, "OFF");
    } else if (id == RD_SPRD) {
        amount = (a - 1) * 64 / 62;
        amount = amount > 64 ? 64 : amount;
        p = put_str(p, k < 0 ? "POS" : "PIT");
        p = put_uint(p, (unsigned)(amount * 100 / 64), 1);
        *p++ = '%';
    } else {
        hz16 = 4 + (unsigned)((a - 1) * (a - 1)) / 2;
        if (k > 0)
            *p++ = '~';
        if (hz16 < 160) {                     /* 0.25 .. 9.94: hundredths */
            unsigned h = hz16 * 100 / 16;
            p = put_uint(p, h / 100, 1);
            *p++ = '.';
            p = put_uint(p, h % 100, 2);
        } else if (hz16 < 1600) {             /* 10.0 .. 99.9: tenths */
            unsigned t = hz16 * 10 / 16;
            p = put_uint(p, t / 10, 1);
            *p++ = '.';
            p = put_uint(p, t % 10, 1);
        } else {
            p = put_uint(p, hz16 / 16, 1);
        }
        p = put_str(p, "Hz");
    }
    *p = 0;
    return 1;
}
