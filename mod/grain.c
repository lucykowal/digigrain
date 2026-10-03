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
    g->dir = p->dir;
    g->delay = delay;
    g->active = 1;
}

void gr_block(gvoice_t *v, const short *pcm, int len, const gparams_t *p, int out[GR_FRAMES])
{
    int acc[GR_FRAMES];
    int i, f;
    for (f = 0; f < GR_FRAMES; f++)
        acc[f] = 0;
    if (len >= 4) {
        if (p->mode == 0) {
            v->next_in = 0;
        } else {
            while (v->next_in < GR_FRAMES) {
                start(v, p, len, v->next_in < 0 ? 0 : v->next_in);
                v->next_in += p->mode == 1 ? p->interval : (int)(rnd(v) % (unsigned)(2 * p->interval)) + 1;
            }
            v->next_in -= GR_FRAMES;
        }
        for (i = 0; i < GR_MAX; i++) {
            grain_t *g = &v->g[i];
            if (!g->active)
                continue;
            for (f = g->delay; f < GR_FRAMES; f++) {
                int a, b, s, w, wo, sh = g->shape;
                if (g->idx < 0 || g->idx >= len - 1 || g->wph >= 65536u) {
                    g->active = 0;
                    break;
                }
                a = pcm[g->idx];
                b = pcm[g->idx + 1];
                s = a + (((b - a) * (int)(g->frac >> 2)) >> 14);
                w = gr_win_sine[g->wph >> 8];
                if (sh < 0) {
                    wo = gr_win_gate[g->wph >> 8];
                    w += ((wo - w) * -sh) >> 8;
                } else if (sh > 0) {
                    wo = gr_win_decay[g->wph >> 8];
                    w += ((wo - w) * sh) >> 8;
                }
                acc[f] += (s * w) >> 15;
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
            g->delay = 0;
        }
    }
    for (f = 0; f < GR_FRAMES; f++)
        out[f] = acc[f] > 32767 ? 32767 : acc[f] < -32768 ? -32768 : acc[f];
}
