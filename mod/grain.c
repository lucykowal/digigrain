/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "grain.h"
#include "tables.h"

#define WPH_ONE (1u << 24)          /* window phase of the end of a grain */

static unsigned rnd(gvoice_t *v)
{
    unsigned x = v->rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    v->rng = x;
    return x;
}

void gr_reset(gvoice_t *v, unsigned seed)
{
    int i;
    for (i = 0; i < GR_MAX; i++)
        v->g[i].active = 0;
    v->next_in = 0;
    v->rng = seed ? seed : 0x9e3779b9u;
    v->win_shape = 1000;            /* no table built yet (shapes are -256..256) */
}

int gr_active(const gvoice_t *v)
{
    int i, n = 0;
    for (i = 0; i < GR_MAX; i++)
        n += v->g[i].active;
    return n;
}

static int clampi(int x, int lo, int hi)
{
    return x < lo ? lo : x > hi ? hi : x;
}

int gr_length(const gparams_t *p)
{
    unsigned iv = (unsigned)clampi(p->interval, 1, 1 << 19);
    unsigned len = (iv * (unsigned)clampi(p->ratio, 1, 4096)) >> 8;
    return len < 16 ? 16 : len > 65535 ? 65535 : (int)len;
}

static int avg_level(int shape)             /* mean window level, Q8 */
{
    if (shape < 0)
        return GR_AVG_SINE + (((GR_AVG_GATE - GR_AVG_SINE) * -shape) >> 8);
    return GR_AVG_SINE + (((GR_AVG_DECAY - GR_AVG_SINE) * shape) >> 8);
}

int gr_norm(const gparams_t *p)
{
    /* expected summed level = length * avg / interval; divide it out when above 1 */
    int t, n, a = avg_level(clampi(p->shape, -256, 256));
    t = (int)(((unsigned)clampi(p->interval, 1, 1 << 19) << 8) / (unsigned)gr_length(p));   /* interval / length, Q8 */
    if (t > 1024)
        t = 1024;
    n = (t << 8) / (a ? a : 1);
    return n > 256 ? 256 : n;
}

static void start(gvoice_t *v, const gparams_t *p, int len, int delay)
{
    int i, pos, jr, m;
    unsigned pr, eff, out_len;
    grain_t *g = 0;
    for (i = 0; i < GR_MAX; i++)
        if (!v->g[i].active) {
            g = &v->g[i];
            break;
        }
    if (!g)
        return;                     /* all busy: skip this grain */
    pos = p->pos;
    jr = (len >> 2) / 64 * clampi(p->spread_pos, 0, 64);
    if (jr > 0)
        pos += (int)(rnd(v) % (unsigned)(2 * jr + 1)) - jr;
    pos = clampi(pos, 0, len - 2);
    pr = 65536;
    m = clampi(p->spread_tune, 0, 64) * 12 / 64;
    if (m > 0)
        pr = gr_ratio[(int)(rnd(v) % (unsigned)(2 * m + 1)) - m + 12];
    eff = ((p->rate >> 6) * (pr >> 6)) >> 4;
    if (eff < 256)
        eff = 256;
    out_len = (unsigned)gr_length(p);
    g->idx = pos;
    g->frac = 0;
    g->inc = eff;
    g->wph = 0;
    g->winc = WPH_ONE / out_len;
    g->delay = delay;
    g->active = 1;
}

/* The live window for `shape` into v->win, Q16 (twice the Q15 blend of sine with gate or decay). */
static void build_win(gvoice_t *v, int shape)
{
    int i, sh = shape < 0 ? -shape : shape;
    const short *alt = shape < 0 ? gr_win_gate : gr_win_decay;
    for (i = 0; i < GR_WIN_N; i++) {
        int w = gr_win_sine[i];
        if (shape)
            w += ((alt[i] - w) * sh) >> 8;
        v->win[i] = (unsigned short)(2 * w);
    }
    v->win_shape = shape;
}

/* Exact reference loop: checks the grain's bounds before every frame. Used near the end of the
 * sample and of the window; the fast loops below must produce bit-identical results. */
static void run_slow(grain_t *g, const short *pcm, int len, int acc[GR_FRAMES], const unsigned short *win)
{
    int f;
    for (f = g->delay; f < GR_FRAMES; f++) {
        int a, b, s;
        unsigned t;
        if (g->idx < 0 || g->idx >= len - 1 || g->wph >= WPH_ONE) {
            g->active = 0;
            break;
        }
        a = pcm[g->idx];
        b = pcm[g->idx + 1];
        s = a + (((b - a) * (int)(g->frac >> 2)) >> 14);
        acc[f] += (s * (int)(win[g->wph >> 16] >> 1)) >> 15;
        g->wph += g->winc;
        t = g->frac + g->inc;
        g->idx += (int)(t >> 16);
        g->frac = t & 0xffffu;
    }
}

/* Fast loops: n >= 1 frames, no bounds checks (the caller proved them safe). The grain's position,
 * fraction and window phase live in locals. The window tables are Q16 (twice Q15), so
 * (s * w16) >> 16 is the same value as (s * w15) >> 15 and the ColdFire does it with a swap. Kept
 * out of line so each loop gets its own registers. */
#define NOINLINE __attribute__((noinline))

/* interpolated */
static NOINLINE void fwd_tab(grain_t *g, const short *pcm, int *acc, int n, const unsigned short *win)
{
    const short *p = pcm + g->idx;
    unsigned fr = g->frac, wp = g->wph, inc = g->inc, winc = g->winc;
    do {
        int a = p[0], s = a + (((p[1] - a) * (int)(fr >> 2)) >> 14);
        unsigned t = fr + inc;
        *acc++ += (s * (int)win[wp >> 16]) >> 16;
        wp += winc;
        p += t >> 16;
        fr = t & 0xffffu;
    } while (--n);
    g->idx = (int)(p - pcm);
    g->frac = fr;
    g->wph = wp;
}

/* a whole number of source frames per output frame, fraction 0: no interpolation */
static NOINLINE void fwd_int(grain_t *g, const short *pcm, int *acc, int n, const unsigned short *win)
{
    const short *p = pcm + g->idx;
    unsigned wp = g->wph, winc = g->winc;
    int step = (int)(g->inc >> 16);
    do {
        *acc++ += (p[0] * (int)win[wp >> 16]) >> 16;
        wp += winc;
        p += step;
    } while (--n);
    g->idx = (int)(p - pcm);
    g->wph = wp;
}

static void run_grain(grain_t *g, const short *pcm, int len, int acc[GR_FRAMES], const unsigned short *win)
{
    int f0 = g->delay, n = GR_FRAMES - f0, deact = 0;
    unsigned room, nw;
    if (g->wph >= WPH_ONE) {
        g->active = 0;
        g->delay = 0;
        return;
    }
    room = WPH_ONE - g->wph;
    if ((unsigned)n * g->winc >= room) {      /* the window ends in this block */
        nw = (room + g->winc - 1) / g->winc;
        if (nw < (unsigned)n) {
            n = (int)nw;
            deact = 1;
        }
    }
    if (g->idx + (int)((g->frac + (unsigned)(n - 1) * g->inc) >> 16) > len - 2) {
        run_slow(g, pcm, len, acc, win);      /* the exact loop handles the sample's end */
        g->delay = 0;
        return;
    }
    if (g->frac == 0 && (g->inc & 0xffffu) == 0)
        fwd_int(g, pcm, acc + f0, n, win);
    else
        fwd_tab(g, pcm, acc + f0, n, win);
    if (deact)
        g->active = 0;
    g->delay = 0;
}

void gr_block(gvoice_t *v, const short *pcm, int len, const gparams_t *p, int out[GR_FRAMES])
{
    int acc[GR_FRAMES];
    int i, f, ran = 0;
    for (f = 0; f < GR_FRAMES; f++)
        acc[f] = 0;
    if (len >= 4) {
        const unsigned short *win = gr_win_sine16;
        int iv = clampi(p->interval, 1, 1 << 24);
        if (p->mode == 0) {
            v->next_in = 0;
        } else {
            int cap = p->mode == 1 ? iv : 2 * iv;       /* a faster rate takes effect within one interval */
            if (v->next_in > cap)
                v->next_in = cap;
            while (v->next_in < GR_FRAMES) {
                start(v, p, len, v->next_in < 0 ? 0 : v->next_in);
                v->next_in += p->mode == 1 ? iv : (int)(rnd(v) % (unsigned)(2 * iv)) + 1;
            }
            v->next_in -= GR_FRAMES;
        }
        if (p->shape != 0) {
            int shape = clampi(p->shape, -256, 256);
            if (v->win_shape != shape)
                build_win(v, shape);
            win = v->win;
        }
        for (i = 0; i < GR_MAX; i++)
            if (v->g[i].active) {
                run_grain(&v->g[i], pcm, len, acc, win);
                ran = 1;
            }
    }
    if (!ran) {
        for (f = 0; f < GR_FRAMES; f++)
            out[f] = 0;
        return;
    }
    for (f = 0; f < GR_FRAMES; f++)
        out[f] = acc[f] > 32767 ? 32767 : acc[f] < -32768 ? -32768 : acc[f];
}
