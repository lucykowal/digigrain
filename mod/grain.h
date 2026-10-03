/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Granular voice: fixed-point, freestanding (no libc/libm/libgcc, no 64-bit math).
 * Pure functions on caller-supplied memory, so the same code runs on the host
 * (unit tests) and on the Digitakt. */
#ifndef LUCYS_GRAIN_H
#define LUCYS_GRAIN_H

#define GR_MAX    12                /* grains per voice */
#define GR_FRAMES 32                /* frames per render block */

typedef struct {
    int idx;                        /* integer frame in the sample */
    unsigned frac;                  /* Q16 fraction, position = idx + frac / 65536 */
    unsigned inc;                   /* Q16 source frames per output frame (> 0) */
    unsigned wph;                   /* Q16 window phase, grain ends at 65536 */
    unsigned winc;                  /* Q16 window phase step per output frame */
    int shape;                      /* -256 (gate) .. 0 (sine) .. +256 (decay) */
    int dir;                        /* +1 forward, -1 reverse */
    int delay;                      /* output frames to wait in the grain's first block */
    int active;
} grain_t;

typedef struct {
    grain_t g[GR_MAX];
    int next_in;                    /* frames until the next grain starts */
    unsigned rng;                   /* xorshift32 state, never 0 */
} gvoice_t;

typedef struct {
    int pos;                        /* grain start (end when reversed), in frames */
    int src_size;                   /* grain length in SOURCE frames (>= 16) */
    unsigned rate;                  /* Q16 playback speed: source frames per output frame */
    int dir;                        /* +1 forward, -1 reverse */
    int mode;                       /* 0 no new grains, 1 periodic, 2 random intervals */
    int interval;                   /* (mean) frames between grain starts (>= 1) */
    int rand;                       /* 0..127: random pitch (semitones), shape and position */
    int shape;                      /* base shape, -256 .. +256 */
} gparams_t;

void gr_reset(gvoice_t *v, unsigned seed);
int gr_active(const gvoice_t *v);
/* One block: out[i] = sum of windowed grains, clamped to the s16 range. */
void gr_block(gvoice_t *v, const short *pcm, int len, const gparams_t *p, int out[GR_FRAMES]);
/* Q8 gain (<= 256) that keeps the summed overlap of grains at or below full scale. */
int gr_norm(const gparams_t *p);

#endif
