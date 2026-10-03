/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Granular voice: fixed-point, freestanding (no libc/libm/libgcc, no 64-bit math).
 * Pure functions on caller-supplied memory, so the same code runs on the host
 * (unit tests) and on the Digitakt. */
#ifndef LUCYS_GRAIN_H
#define LUCYS_GRAIN_H

#define GR_MAX    8                 /* grains per voice */
#define GR_FRAMES 32                /* frames per render block */

typedef struct {
    int idx;                        /* integer frame in the sample */
    unsigned frac;                  /* Q16 fraction */
    unsigned inc;                   /* Q16 frames per output frame (> 0) */
    unsigned wph;                   /* Q16 window phase, grain ends at 65536 */
    unsigned winc;                  /* Q16 window phase step per frame */
    int delay;                      /* output frames to wait in the first block */
    int active;
} grain_t;

typedef struct {
    grain_t g[GR_MAX];
    int next_in;                    /* frames until the next grain starts */
    unsigned rng;                   /* xorshift32 state, never 0 */
} gvoice_t;

typedef struct {
    int pos;                        /* grain start centre, in frames */
    int size;                       /* grain length in output frames (>= 16) */
    int interval;                   /* frames between grain starts (>= 1) */
    int jitter;                     /* start position jitter, +- frames */
    unsigned rate;                  /* Q16 source frames per output frame */
    int spawn;                      /* nonzero: may start new grains */
} gparams_t;

void gr_reset(gvoice_t *v, unsigned seed);
int gr_active(const gvoice_t *v);
/* One block: out[i] = sum of windowed grains, clamped to the s16 range. */
void gr_block(gvoice_t *v, const short *pcm, int len, const gparams_t *p, int out[GR_FRAMES]);

#endif
