/* SPDX-License-Identifier: GPL-2.0-or-later */
/* lucys-granular: the GRANULAR machine's voice renderer (Digitakt mk1 OS 1.53).
 *
 * The machine plays as ONESHOT, so the stock voice (the "shadow") still runs: it
 * gives us note on/off, the sample slot, the playhead V+4 and the pitch (its
 * per-block advance), and everything after the synth (filter, amp, pan, level,
 * FX) works on the block we write. After each stock synth call, synth.s calls
 * lucys_granular_render(), which overwrites the 32 x int32 block at
 * 0x80001a18 + 128 * v of every GRANULAR voice with grains.
 *
 * Knobs reuse ONESHOT's SRC page (TUNE PLAY BR SAMP / STRT LEN LOOP LEV):
 *   STRT = grain position in the sample   LEN = grain size   BR = density
 *   TUNE = pitch (through the shadow voice)   LEV = level
 */
#include "grain.h"

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef int s32;

#define MACHINE_ID 6
#define BLOCKS     0x80001a18u            /* 8 voice blocks of 32 x s32, 128 bytes apart */
#define VOICE(v)   (0x8000edc4u + 94u * (v))
#define PARAMS(v)  (0x80002772u + 106u * (v)) /* smoothed words; word s at +2 s */
#define TRIGMASK   0x80001228u            /* bit v: voice v starts this block */
#define SMP_TAB    0x403193a0u            /* 16 bytes a slot: PCM ptr, u16, length, ratio */
#define GAIN       25916                  /* measured: stock block = s16 * 25916 at LEV 100 */
#define RATE_Q16_PER_DELTA 2048           /* V+4 advance per block (32 = unity) -> Q16 rate */

extern volatile unsigned char core_track_machine[8]; /* core 2.1: each track's machine */

static gvoice_t gv[8];
static struct {
    s32 prev_pos;
    u32 rate;
    int have_prev;
    int init;
} st[8];

static void render_voice(int v)
{
    u32 vs = VOICE(v);
    const volatile u16 *w = (const volatile u16 *)PARAMS(v);
    volatile s32 *blk = (volatile s32 *)(BLOCKS + 128u * v);
    int on, strt, lenp, dens, lev, size, interval, norm, g, f, len, out[GR_FRAMES];
    u32 slot, ent;
    const short *pcm;
    gparams_t p;
    s32 pos;

    if (core_track_machine[v] != MACHINE_ID) {
        st[v].init = 0;
        return;
    }
    on = *(volatile u8 *)(vs + 0x28);
    if (!st[v].init || ((*(volatile u32 *)TRIGMASK >> v) & 1)) {
        gr_reset(&gv[v], 0x1234567u + (u32)v * 0x9e3779b9u);
        st[v].have_prev = 0;
        st[v].rate = 65536;
        st[v].init = 1;
    }
    pos = *(volatile s32 *)(vs + 4);
    if (on) {
        if (st[v].have_prev) {
            s32 d = pos - st[v].prev_pos;
            if (d < 0)
                d = -d;
            if (d >= 2 && d <= 512)
                st[v].rate = (u32)d * RATE_Q16_PER_DELTA;
        }
        st[v].prev_pos = pos;
        st[v].have_prev = 1;
    }
    slot = *(volatile u8 *)(vs + 0x5c);
    if (slot > 130)
        return;
    ent = SMP_TAB + 16u * slot;
    pcm = (const short *)*(volatile u32 *)ent;
    len = *(volatile s32 *)(ent + 8);
    if (!pcm || len < 4 || (!on && !gr_active(&gv[v])))
        return;                           /* leave the stock block as it is */

    strt = w[21] >> 8;
    lenp = w[22] >> 8;
    dens = w[19] >> 8;
    lev = w[24] >> 8;
    size = 240 + ((lenp * lenp * 19) >> 4);       /* 5 ms .. ~400 ms */
    interval = 48000 / (1 + (dens >> 1));          /* 1 .. 64 grains a second */
    p.pos = (len - 2) / 127 * strt;
    p.size = size;
    p.interval = interval;
    p.jitter = size >> 2;
    p.rate = st[v].rate;
    p.spawn = on;
    gr_block(&gv[v], pcm, len, &p, out);

    norm = 512 * interval / size;                  /* Hann overlap: sum ~ 2 / overlap */
    if (norm > 256)
        norm = 256;
    g = (GAIN * lev / 100 * norm) >> 8;
    for (f = 0; f < GR_FRAMES; f++)
        blk[f] = out[f] * g;
}

/* Called after the stock synth filled every voice's block. */
void lucys_granular_render(void)
{
    int v;
    for (v = 0; v < 8; v++)
        render_voice(v);
}
