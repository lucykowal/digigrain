/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "grain.h"
#include "tables.h"

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

static int avg_level(int shape)             /* mean window level, Q8 */
{
    if (shape < 0)
        return GR_AVG_SINE + (((GR_AVG_GATE - GR_AVG_SINE) * -shape) >> 8);
    return GR_AVG_SINE + (((GR_AVG_DECAY - GR_AVG_SINE) * shape) >> 8);
}

int gr_norm(const gparams_t *p)
{
    /* expected summed level = out_len * avg / interval; divide it out when above 1 */
    unsigned out_len = ((unsigned)p->src_size << 16) / (p->rate ? p->rate : 1);
    int t, n, a = avg_level(p->shape);
    if (out_len < 1)
        out_len = 1;
    t = (int)(((unsigned)p->interval << 8) / out_len);      /* interval / out_len, Q8 */
    if (t > 1024)
        t = 1024;
    n = (t << 8) / (a ? a : 1);
    return n > 256 ? 256 : n;
}

static void start(gvoice_t *v, const gparams_t *p, int len, int delay)
{
    int i, pos, shape, jr, m, r;
    unsigned ratio, eff, out_len;
    grain_t *g = 0;
    for (i = 0; i < GR_MAX; i++)
        if (!v->g[i].active) {
            g = &v->g[i];
            break;
        }
    if (!g)
        return;                     /* all busy: skip this grain */
    pos = p->pos;
    jr = (len >> 2) / 127 * p->rand;
    if (jr > 0)
        pos += (int)(rnd(v) % (unsigned)(2 * jr + 1)) - jr;
    if (pos < 0)
        pos = 0;
    if (pos > len - 2)
        pos = len - 2;
    ratio = 65536;
    m = p->rand * 12 / 127;
    if (m > 0)
        ratio = gr_ratio[(int)(rnd(v) % (unsigned)(2 * m + 1)) - m + 12];
    shape = p->shape;
    r = p->rand * 256 / 127;
    if (r > 0)
        shape += (int)(rnd(v) % (unsigned)(2 * r + 1)) - r;
    if (shape > 256)
        shape = 256;
    if (shape < -256)
        shape = -256;
    eff = ((p->rate >> 6) * (ratio >> 6)) >> 4;
    if (eff < 256)
        eff = 256;
    out_len = ((unsigned)p->src_size << 16) / eff;
    if (out_len < 16)
        out_len = 16;
    if (out_len > 65535)
        out_len = 65535;
    g->idx = pos;
    g->frac = 0;
    g->inc = eff;
    g->wph = 0;
    g->winc = 65536u / out_len;
    g->shape = shape;
    g->tab = p->rand == 0 ? 0 : gr_win_q + ((shape + 272) >> 5) * GR_WIN_N;   /* nearest of 17 shapes */
    g->dir = p->dir;
    g->delay = delay;
    g->active = 1;
}

/* The live window for `shape` into v->win, Q16 (the same blend the reference loop used per sample). */
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

/* Exact reference loop: checks the grain's bounds before every frame. Used near the ends of the
 * sample and of the window; the fast loops below must produce bit-identical results. `win` is the
 * voice's live table for grains without their own. */
static void run_slow(grain_t *g, const short *pcm, int len, int acc[GR_FRAMES], const unsigned short *win)
{
    const unsigned short *tab = g->tab ? g->tab : win;
    int f;
    for (f = g->delay; f < GR_FRAMES; f++) {
        int a, b, s;
        if (g->idx < 0 || g->idx >= len - 1 || g->wph >= 65536u) {
            g->active = 0;
            break;
        }
        a = pcm[g->idx];
        b = pcm[g->idx + 1];
        s = a + (((b - a) * (int)(g->frac >> 2)) >> 14);
        acc[f] += (s * (int)(tab[g->wph >> 8] >> 1)) >> 15;
        g->wph += g->winc;
        if (g->dir > 0) {
            unsigned t = g->frac + g->inc;
            g->idx += (int)(t >> 16);
            g->frac = t & 0xffffu;
        } else {
            unsigned lo = g->inc & 0xffffu;
            g->idx -= (int)(g->inc >> 16);
            if (g->frac >= lo) {
                g->frac -= lo;
            } else {
                g->frac = g->frac + 65536u - lo;
                g->idx--;
            }
        }
    }
}

/* Fast loops: n >= 1 frames, no bounds checks (the caller proved them safe). The grain's position,
 * fraction and window phase live in locals. The window tables are Q16 (twice Q15), so
 * (s * w16) >> 16 is the same value as (s * w15) >> 15 and the ColdFire does it with a swap. Kept
 * out of line so each loop gets its own registers. */
#define NOINLINE __attribute__((noinline))

/* forward, interpolated */
static NOINLINE void fwd_tab(grain_t *g, const short *pcm, int *acc, int n, const unsigned short *win)
{
    const short *p = pcm + g->idx;
    unsigned fr = g->frac, wp = g->wph, inc = g->inc, winc = g->winc;
    do {
        int a = p[0], s = a + (((p[1] - a) * (int)(fr >> 2)) >> 14);
        unsigned t = fr + inc;
        *acc++ += (s * (int)win[wp >> 8]) >> 16;
        wp += winc;
        p += t >> 16;
        fr = t & 0xffffu;
    } while (--n);
    g->idx = (int)(p - pcm);
    g->frac = fr;
    g->wph = wp;
}

/* forward at a whole number of source frames per output frame, fraction 0: no interpolation */
static NOINLINE void fwd_int(grain_t *g, const short *pcm, int *acc, int n, const unsigned short *win)
{
    const short *p = pcm + g->idx;
    unsigned wp = g->wph, winc = g->winc;
    int step = (int)(g->inc >> 16);
    do {
        *acc++ += (p[0] * (int)win[wp >> 8]) >> 16;
        wp += winc;
        p += step;
    } while (--n);
    g->idx = (int)(p - pcm);
    g->wph = wp;
}

static NOINLINE void rev_tab(grain_t *g, const short *pcm, int *acc, int n, const unsigned short *win)
{
    const short *p = pcm + g->idx;
    unsigned fr = g->frac, wp = g->wph, winc = g->winc;
    unsigned lo = g->inc & 0xffffu, hi = g->inc >> 16;
    do {
        int a = p[0], s = a + (((p[1] - a) * (int)(fr >> 2)) >> 14);
        *acc++ += (s * (int)win[wp >> 8]) >> 16;
        wp += winc;
        p -= hi;
        if (fr >= lo) {
            fr -= lo;
        } else {
            fr = fr + 65536u - lo;
            p--;
        }
    } while (--n);
    g->idx = (int)(p - pcm);
    g->frac = fr;
    g->wph = wp;
}

static NOINLINE void rev_int(grain_t *g, const short *pcm, int *acc, int n, const unsigned short *win)
{
    const short *p = pcm + g->idx;
    unsigned wp = g->wph, winc = g->winc;
    int step = (int)(g->inc >> 16);
    do {
        *acc++ += (p[0] * (int)win[wp >> 8]) >> 16;
        wp += winc;
        p -= step;
    } while (--n);
    g->idx = (int)(p - pcm);
    g->wph = wp;
}

static void run_grain(grain_t *g, const short *pcm, int len, int acc[GR_FRAMES], const unsigned short *live)
{
    int f0 = g->delay, n = GR_FRAMES - f0, deact = 0;
    unsigned room, nw;
    int safe, whole;
    const unsigned short *tab = g->tab ? g->tab : live;
    if (g->wph >= 65536u) {
        g->active = 0;
        g->delay = 0;
        return;
    }
    room = 65536u - g->wph;
    if ((unsigned)n * g->winc >= room) {      /* the window ends in this block */
        nw = (room + g->winc - 1) / g->winc;
        if (nw < (unsigned)n) {
            n = (int)nw;
            deact = 1;
        }
    }
    if (g->dir > 0)
        safe = g->idx + (int)((g->frac + (unsigned)(n - 1) * g->inc) >> 16) <= len - 2;
    else
        safe = g->idx - (int)(((unsigned)(n - 1) * g->inc) >> 16) - 1 >= 0;
    if (!safe) {
        run_slow(g, pcm, len, acc, live);     /* the exact loop handles the sample's ends */
        g->delay = 0;
        return;
    }
    whole = g->frac == 0 && (g->inc & 0xffffu) == 0;
    if (g->dir > 0)
        (whole ? fwd_int : fwd_tab)(g, pcm, acc + f0, n, tab);
    else
        (whole ? rev_int : rev_tab)(g, pcm, acc + f0, n, tab);
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
        const unsigned short *live = gr_win_sine16;
        if (p->mode == 0) {
            v->next_in = 0;
        } else {
            while (v->next_in < GR_FRAMES) {
                start(v, p, len, v->next_in < 0 ? 0 : v->next_in);
                v->next_in += p->mode == 1 ? p->interval : (int)(rnd(v) % (unsigned)(2 * p->interval)) + 1;
            }
            v->next_in -= GR_FRAMES;
        }
        if (p->shape != 0) {                  /* grains without a table follow the shape knob live */
            if (v->win_shape != p->shape)
                build_win(v, p->shape);
            live = v->win;
        }
        for (i = 0; i < GR_MAX; i++)
            if (v->g[i].active) {
                run_grain(&v->g[i], pcm, len, acc, live);
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
