/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Granular voice: fixed-point, freestanding (no libc/libm/libgcc, no 64-bit math).
 * Pure functions on caller-supplied memory, so the same code runs on the host
 * (unit tests) and on the Digitakt. */
#ifndef DIGIGRAIN_GRAIN_H
#define DIGIGRAIN_GRAIN_H

#define GR_MAX    8                 /* grains per voice */
#define GR_FRAMES 32                /* output frames per render block (48 kHz) */
#define GR_HALF   (GR_FRAMES / 2)   /* the grains run at 24 kHz: frames per block they compute */

typedef struct {
    int idx;                        /* integer frame in the sample (48 kHz source frames) */
    unsigned frac;                  /* Q16 fraction, position = idx + frac / 65536 */
    unsigned inc;                   /* Q16 source frames per 24 kHz frame (> 0): twice the pitch rate */
    unsigned wph;                   /* Q24 window phase, the grain ends at 1 << 24 */
    unsigned winc;                  /* Q24 window phase step per 24 kHz frame */
    int delay;                      /* 24 kHz frames to wait in the grain's first block */
    int active;
} grain_t;

typedef struct {
    grain_t g[GR_MAX];
    int next_in;                    /* frames until the next grain starts */
    unsigned rng;                   /* xorshift32 state, never 0 */
    int win_shape;                  /* shape the cached window below was built for */
    unsigned short win[256];        /* the live window for that shape, Q16 (blend of sine with gate or decay) */
    int last;                       /* last 24 kHz sample of the previous block (the upsampler's state) */
} gvoice_t;

typedef struct {
    int pos;                        /* grain start frame in the sample (before spread) */
    unsigned rate;                  /* Q16 source frames per output frame = grain pitch */
    int mode;                       /* 0 no new grains, 1 periodic, 2 random intervals */
    int interval;                   /* (mean) frames between grain starts, >= 1 */
    int ratio;                      /* RTIO in Q8: 64..2048 (0.25..8.00): grain length = ratio * interval */
    int spread_pos;                 /* 0..64: random start-position jitter amount (full = +-len/4) */
    int spread_tune;                /* 0..64: random pitch amount, +-(spread_tune * 12 / 64) semitones */
    int shape;                      /* ENV -256 (gate) .. 0 (sine) .. +256 (decay) */
} gparams_t;

/* Grain length in output frames: clamp((interval * ratio) >> 8, 16, 65535), independent of pitch.
 * (ratio is limited to 1..4096 and interval to 1..2^19 for this product.) */
int gr_length(const gparams_t *p);

void gr_reset(gvoice_t *v, unsigned seed);
int gr_active(const gvoice_t *v);
/* One block: the sum of windowed grains is computed at 24 kHz, clamped to the s16 range and
 * linearly upsampled to out[GR_FRAMES]. */
void gr_block(gvoice_t *v, const short *pcm, int len, const gparams_t *p, int out[GR_FRAMES]);
/* Q8 gain (<= 256) that keeps the expected summed overlap of grains at or below full scale. */
int gr_norm(const gparams_t *p);

#endif
