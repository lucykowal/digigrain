/* SPDX-License-Identifier: GPL-2.0-or-later */
/* lucys-granular: the GRANULAR machine's voice renderer (Digitakt mk1 OS 1.53).
 *
 * The machine plays as ONESHOT, so the stock voice (the "shadow") still runs: it gives us
 * note on/off, the sample slot, the playback speed (V+4's per-block advance, which includes
 * TUNE and the note) and a stock PLAY loop/one-shot lifetime; everything after the synth
 * (filter, amp, pan, level, FX) works on the block we write. synth.s calls
 * digigrain_granular_pre() before the stock synth and digigrain_granular_render() after it.
 * The latter overwrites the 32 x int32 block at 0x80001a18 + 128 * v of every GRANULAR voice.
 *
 * Controls (the SRC page's eight knobs; words of the voice's parameter block):
 *   A TUNE  playback speed -> grain pitch and length (through the shadow voice)
 *   B PLAY  grain direction: REV, REV.L = reverse; FWD.L, FWD = forward (.L: the shadow loops,
 *           so the voice sustains)
 *   C STRT  grain position in the sample (fixed; sweep it to scan)
 *   D SAMP  sample (shadow voice)
 *   E DENS  noon = 0 Hz; counter-clockwise = periodic grains, clockwise = random intervals
 *   F SHAPE noon = sine window; counter-clockwise -> gate; clockwise -> quick decay
 *   G RAND  random pitch (semitones), shape and position per grain
 * E, F and G are new parameter descriptors (page.s, tools/gen_page_sites.py) on the words of
 * the stock BR, LEN and LOOP.
 *   H LEV   level (the stock law: gain = (LEV / 100)^2)
 * The stock STRT, LEN and LOOP words would otherwise decide the shadow voice's window, so pre()
 * neutralises them for GRANULAR voices (full sample, no loop point).
 */
#include "grain.h"

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef int s32;

#define MACHINE_ID 6
#define BLOCKS     0x80001a18u            /* 8 voice blocks of 32 x s32, 128 bytes apart */
#define VOICE(v)   (0x8000edc4u + 94u * (v))
#define SMOOTHED(v) (0x80002772u + 106u * (v)) /* what the synth reads; word s at +2 s */
#define TARGET(v)  (0x80001502u + 106u * (v))  /* the knob values themselves */
#define EXPANDED(v) (0x80002b50u + 212u * (v)) /* 32-bit copy (value << 16), word s at +4 s */
#define TRIGMASK   0x80001228u            /* bit v: voice v starts this block */
#define SMP_TAB    0x403193a0u            /* 16 bytes a slot: PCM ptr, u16, length, ratio */
#define GAIN       25916                  /* measured: stock block = s16 * 25916 at LEV 100 */
#define RATE_Q16_PER_DELTA 2048           /* V+4 advance per block (32 = unity) -> Q16 rate */
#define SRC_GRAIN  2400                   /* grain length in source frames (50 ms at 1x) */

/* parameter word indices (53-word block): what each SRC-page knob edits (page.s lays them out) */
#define W_PLAY  18        /* B: PLAY */
#define W_DENS  19        /* E: DENS (descriptor 1, on BR's word) */
#define W_POS   21        /* C: STRT, used as the grain position */
#define W_SHAPE 22        /* F: SHAPE (descriptor 2, on LEN's word) */
#define W_RAND  23        /* G: RAND (descriptor 3, on LOOP's word) */
#define W_LEV   24        /* H: LEV */

extern volatile unsigned char core_track_machine[8]; /* core 2.1: each track's machine */

static gvoice_t gv[8];
static struct {
    s32 prev_pos;
    u32 rate;
    int have_prev;
    int init;
} st[8];

/* Before the stock synth: GRANULAR voices get a full-sample, no-loop-point shadow. */
void digigrain_granular_pre(void)
{
    int v;
    for (v = 0; v < 8; v++)
        if (core_track_machine[v] == MACHINE_ID) {
            volatile u16 *sm = (volatile u16 *)SMOOTHED(v);
            volatile u32 *ex = (volatile u32 *)EXPANDED(v);
            sm[W_POS] = 0;                /* the shadow's STRT, LEN and LOOP: full sample */
            sm[W_SHAPE] = 0x7f00;
            sm[W_RAND] = 0;
            ex[W_POS] = 0;
            ex[W_SHAPE] = 0x7f00u << 16;
            ex[W_RAND] = 0;
        }
}

static void render_voice(int v)
{
    u32 vs = VOICE(v);
    const volatile u16 *w = (const volatile u16 *)TARGET(v);
    volatile s32 *blk = (volatile s32 *)(BLOCKS + 128u * v);
    int on, play, dens, k, shape, lev, f, len, g, out[GR_FRAMES];
    u32 slot, ent, hz16;
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

    play = w[W_PLAY] >> 8;
    dens = w[W_DENS] >> 8;
    shape = w[W_SHAPE] >> 8;
    lev = w[W_LEV] >> 8;
    k = dens - 64;                        /* noon = 0 Hz */
    p.mode = (k > -2 && k < 2) ? 0 : k < 0 ? 1 : 2;
    k = (k < 0 ? -k : k) - 1;             /* 0 .. 62 */
    hz16 = 4 + ((u32)(k * k) >> 1);       /* 0.25 .. 120 Hz in 1/16 Hz */
    p.interval = (int)(768000u / hz16);
    p.shape = (shape - 64) * 4;           /* noon = sine; -256 gate .. +252 decay */
    p.rand = w[W_RAND] >> 8;
    p.pos = (len - 2) / 120 * (w[W_POS] >> 8);      /* STRT runs 0..120 */
    p.src_size = SRC_GRAIN;
    p.rate = st[v].rate;
    p.dir = play <= 1 ? -1 : 1;
    gr_block(&gv[v], pcm, len, &p, out);

    g = (int)((u32)GAIN * (u32)(lev * lev) / 10000u);
    g = (g * gr_norm(&p)) >> 8;
    for (f = 0; f < GR_FRAMES; f++)
        blk[f] = out[f] * g;
}

/* After the stock synth filled every voice's block. */
void digigrain_granular_render(void)
{
    int v;
    for (v = 0; v < 8; v++)
        render_voice(v);
}

/* ev_tick (30 Hz, UI task): when a track newly becomes GRANULAR and its knobs hold the stock
 * defaults of the machine it borrows its parameters from (BR 0, STRT 0, LEN 120, LOOP 0), give it
 * sensible granular defaults. The UI kit changes with the pattern, so a kit switch only
 * re-reads the machine bytes. */
#define UI_KIT      0x4199dc44u           /* pointer to the current pattern's kit */
#define SOUND(k, t) ((k) + 0x20u + 0xa2u * (t))
#define SND_MACHINE 0x7e
#define SND_PARAMS  0x14                  /* 53 words; word s at +2 s */

static u32 seen_kit;
static u8 seen_machine[8];

void digigrain_granular_tick(void *ctrl)
{
    u32 kit = *(volatile u32 *)UI_KIT;
    int t;
    (void)ctrl;
    if (!kit)
        return;
    for (t = 0; t < 8; t++) {
        u32 snd = SOUND(kit, t);
        u8 m = *(volatile u8 *)(snd + SND_MACHINE);
        if (kit == seen_kit && m == MACHINE_ID && seen_machine[t] != MACHINE_ID) {
            volatile u16 *w = (volatile u16 *)(snd + SND_PARAMS);
            if (w[W_DENS] == 0 && w[W_POS] == 0 && w[W_SHAPE] == 0x7800 && w[W_RAND] == 0) {
                w[W_PLAY] = 2 << 8;       /* FWD.L: the voice sustains */
                w[W_DENS] = 36 << 8;      /* periodic, ~24 Hz */
                w[W_SHAPE] = 64 << 8;     /* sine */
            }
        }
        seen_machine[t] = m;
    }
    seen_kit = kit;
}
