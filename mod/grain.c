/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "grain.h"
#include "window.h"

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

static void start(gvoice_t *v, const gparams_t *p, int len, int delay)
{
    int i, pos;
    grain_t *g = 0;
    for (i = 0; i < GR_MAX; i++)
        if (!v->g[i].active) {
            g = &v->g[i];
            break;
        }
    if (!g)
        return;                     /* all busy: skip this grain */
    pos = p->pos;
    if (p->jitter > 0)
        pos += (int)(rnd(v) % (unsigned)(2 * p->jitter + 1)) - p->jitter;
    if (pos < 0)
        pos = 0;
    if (pos > len - 2)
        pos = len - 2;
    g->idx = pos;
    g->frac = 0;
    g->inc = p->rate;
    g->wph = 0;
    g->winc = 65536u / (unsigned)p->size;
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
        if (p->spawn) {
            while (v->next_in < GR_FRAMES) {
                start(v, p, len, v->next_in < 0 ? 0 : v->next_in);
                v->next_in += p->interval;
            }
            v->next_in -= GR_FRAMES;
        }
        for (i = 0; i < GR_MAX; i++) {
            grain_t *g = &v->g[i];
            if (!g->active)
                continue;
            for (f = g->delay; f < GR_FRAMES; f++) {
                int a, b, s, w;
                unsigned t;
                if (g->idx >= len - 1 || g->wph >= 65536u) {
                    g->active = 0;
                    break;
                }
                a = pcm[g->idx];
                b = pcm[g->idx + 1];
                s = a + (((b - a) * (int)(g->frac >> 2)) >> 14);
                w = gr_win[g->wph >> 8];
                acc[f] += (s * w) >> 15;
                g->wph += g->winc;
                t = g->frac + g->inc;
                g->idx += (int)(t >> 16);
                g->frac = t & 0xffffu;
            }
            g->delay = 0;
        }
    }
    for (f = 0; f < GR_FRAMES; f++)
        out[f] = acc[f] > 32767 ? 32767 : acc[f] < -32768 ? -32768 : acc[f];
}
