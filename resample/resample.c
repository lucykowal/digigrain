/* SPDX-License-Identifier: GPL-2.0-or-later */
/* digiresample: the RESAMPLE machine's voice glue (Digitakt mk1 OS 1.53).
 *
 * RESAMPLE plays as ONESHOT. Its voice (the "shadow") is pointed at sample slot 0x82, the RECORDER's
 * audition slot, which this file keeps describing the record buffer (s16 mono 48 kHz at 0x4237DF90),
 * so TUNE, PLAY, BR, STRT, LEN, filter, amp, LEV and the FX all work as on ONESHOT. The two new knobs:
 *   D REC/PLAY (word 20; knob value 0 = REC, 1 = PLAY)
 *       REC  a trig starts the RECORDER (the Fn+YES of the RECORDER page): whatever the buffer held is
 *            thrown away. It records while the note is held; the note off stops it. The voice itself is
 *            silent.
 *       PLAY the voice plays the record buffer. Not LFO-modulatable: read from the engine copy at the trig.
 *   G SRC (word 23; 0..16 = the RECORDER's SRC list: IN L .. TRK8)
 *       The recorder's source (0x4197bf98, read by the capture switch each block). Follows the LFO and
 *       parameter locks. Last trig wins: only the most recently trigged RESAMPLE voice writes it.
 * All RESAMPLE tracks share the one RECORDER. Static analysis only so far: nothing here has run in
 * digiemu (see the issue "Verify RESAMPLE").
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef int s32;

#define MACHINE_ID 7
#define BLOCKS     0x80001a18u            /* 8 voice blocks of 32 x s32, 128 bytes apart */
#define VOICE(v)   (0x8000edc4u + 94u * (v))
#define V_ON       0x28                   /* voice playing */
#define V_SLOT     0x5c                   /* sample slot the synth reads */
#define V_PTR      0x00                   /* the voice's copy of the slot's PCM pointer (latched at the trig) */
#define V_LEN      0x14                   /* ... of its length in samples */
#define V_RATIO    0x18                   /* ... of its ratio (Q30) */
#define SMP_TAB    0x403193a0u            /* 16 bytes a slot: PCM ptr, u16, length, ratio */
#define SMOOTHED(v) (0x80002772u + 106u * (v)) /* what the synth reads; word s at +2 s */
#define ENGINE(v)  (0x80001502u + 106u * (v))  /* the knob values, plocks applied, no LFO */
#define TRIGMASK   0x80001228u            /* bit v: voice v starts this block */
#define KEYMASK    0x800019f4u            /* bit t: trig key t+1 is held (measured: 1 for key 1, 2 for key 2) */

#define EXPANDED(v) (0x80002b50u + 212u * (v)) /* 32-bit copy (value << 16), word s at +4 s */
#define W_PLAY     18                     /* B: PLAY (the shadow's direction/loop word) */
#define PLAY_LOOP  0x0200                 /* FWD.L */
#define W_REC      20                     /* D: REC/PLAY, on SAMP's word */
#define W_SRC      23                     /* G: SRC, on LOOP's word */
#define SRC_MAX    16
#define REC_SRC    0x4197bf98u            /* the recorder's SRC setting (audio side) */
#define REC_STATE  0x4199e114u            /* 0 idle, 1 armed, 2 recording, 3 normalizing, 4 done */
#define REC_LEN    0x4199e104u            /* frames written */
#define REC_PLANE  0x4237df90u            /* s16 plane */
#define SLOT_REC   0x82                   /* the RECORDER's audition slot */

static int (*const rec_start)(void) = (int (*)(void))0x400768ceu;   /* states 0, 1, 4 -> 2 */
static int (*const rec_stop)(void) = (int (*)(void))0x40076918u;    /* 2 -> 3 (normalize) -> 4 */
static int (*const rec_discard)(void) = (int (*)(void))0x4007693cu; /* 1, 2, 4 -> 0 */
static void (*const slot_reset)(int) = (void (*)(int))0x40074fd0u;
static void (*const slot_set)(int, u32, u32, u32) = (void (*)(int, u32, u32, u32))0x400763b4u;

extern volatile unsigned char core_track_machine[8]; /* core 2.1: each track's machine */

enum { M_REC = 0, M_PLAY = 1 };

static struct {
    u8 mode;                  /* latched at the trig */
    u8 prev_on;
    u8 recording;             /* this voice started the running recording */
    u8 shadowed;              /* pre() forced PLAY to FWD.L for this block */
    u8 keyed;                 /* the note was started by a trig key still counted in KEYMASK */
} st[8];
static u16 saved_sm[8];
static u32 saved_ex[8];
static int owner = -1;        /* the voice that last trigged: it owns the SRC */
static u32 slot_len;          /* frames the slot 0x82 entry describes (0 = none) */

/* Pure decode of the D knob word (8.8, 0..0x100): 0 = REC, anything else PLAY. */
int rs_mode(u32 word)
{
    return (word >> 8) ? M_PLAY : M_REC;
}

/* Pure decode of the G knob word to a recorder source, clamped. */
int rs_src(u32 word)
{
    u32 s = word >> 8;
    return s > SRC_MAX ? SRC_MAX : (int)s;
}

static u32 rec_state(void)
{
    return *(volatile u32 *)REC_STATE;
}

static void set_src(int v)
{
    *(volatile u32 *)REC_SRC = (u32)rs_src(*(volatile u16 *)(SMOOTHED(v) + 2 * W_SRC));
}

/* Keep slot 0x82 describing the finished recording (state 4). */
static void sync_slot(void)
{
    u32 state = rec_state();
    u32 len = *(volatile u32 *)REC_LEN;
    if (state == 4 && len >= 4 && len != slot_len) {
        slot_reset(SLOT_REC);
        slot_set(SLOT_REC, REC_PLANE, 2 * len, 48000);
        slot_len = len;
    }
    if (state == 0 || state == 2)
        slot_len = 0;         /* a new take: the entry is stale */
}

static void trig(int v)
{
    int w;
    u32 state = rec_state();
    st[v].mode = (u8)rs_mode(*(volatile u16 *)(ENGINE(v) + 2 * W_REC));
    st[v].recording = 0;
    st[v].keyed = (u8)((*(volatile u32 *)KEYMASK >> v) & 1);
    owner = v;
    if (st[v].mode == M_REC) {
        if (state == 2)
            rec_discard();                     /* restart: throw the running take away */
        if (rec_state() != 3) {                /* not while the stock code normalizes */
            set_src(v);
            rec_start();
            st[v].recording = rec_state() == 2;
        }
        for (w = 0; w < 8; w++)
            if (w != v)
                st[w].recording = 0;           /* only the newest trig owns the take */
    } else if (state == 2) {
        rec_stop();                            /* last trig wins: finish the take, then play it */
        for (w = 0; w < 8; w++)
            st[w].recording = 0;
    }
}

/* Before the stock synth: trigs, recorder control and the slot of PLAY voices. */
void digiresample_pre(void)
{
    u32 mask = *(volatile u32 *)TRIGMASK;
    int v;
    sync_slot();
    for (v = 0; v < 8; v++) {
        u32 vs;
        int on;
        if (core_track_machine[v] != MACHINE_ID) {
            st[v].prev_on = st[v].recording = 0;
            if (owner == v)
                owner = -1;
            continue;
        }
        vs = VOICE(v);
        on = *(volatile u8 *)(vs + V_ON) != 0;
        if (((mask >> v) & 1) || (on && !st[v].prev_on))
            trig(v);
        st[v].prev_on = (u8)on;
        /* The note is over when the voice ends, or (a live note) when its trig key is let go: the stock voice
         * carries on through its amp envelope's release, and has no gate flag we know of for sequenced notes. */
        if (!on || (st[v].keyed && !((*(volatile u32 *)KEYMASK >> v) & 1))) {
            if (st[v].recording && rec_state() == 2)
                rec_stop();                    /* the note off ends the take */
            st[v].recording = 0;
        }
        if (owner == v && on)                  /* SRC follows the LFO / plocks of the last trig */
            set_src(v);
        if (on) {
            u32 ent = SMP_TAB + 16u * SLOT_REC;
            *(volatile u8 *)(vs + V_SLOT) = SLOT_REC;
            /* the stock trig latched slot D's sample (word 20 holds 0/1 here): point the voice at the record buffer */
            *(volatile u32 *)(vs + V_PTR) = *(volatile u32 *)ent;
            *(volatile u32 *)(vs + V_LEN) = *(volatile u32 *)(ent + 8);
            *(volatile u32 *)(vs + V_RATIO) = *(volatile u32 *)(ent + 12);
        }
        if (st[v].mode == M_REC && on) {       /* a REC voice must outlive the stub sample: loop it */
            volatile u16 *sm = (volatile u16 *)SMOOTHED(v);
            volatile u32 *ex = (volatile u32 *)EXPANDED(v);
            saved_sm[v] = sm[W_PLAY];
            saved_ex[v] = ex[W_PLAY];
            sm[W_PLAY] = PLAY_LOOP;
            ex[W_PLAY] = (u32)PLAY_LOOP << 16;
            st[v].shadowed = 1;
        }
    }
}

/* After the synth: voices that record, or have no finished take to play, are silent. */
void digiresample_post(void)
{
    int v, f;
    for (v = 0; v < 8; v++) {
        if (core_track_machine[v] != MACHINE_ID)
            continue;
        if (st[v].shadowed) {                  /* the stock smoothing slews from the previous word: give it back */
            ((volatile u16 *)SMOOTHED(v))[W_PLAY] = saved_sm[v];
            ((volatile u32 *)EXPANDED(v))[W_PLAY] = saved_ex[v];
            st[v].shadowed = 0;
        }
        if (st[v].mode == M_REC || rec_state() != 4 || !slot_len) {
            volatile s32 *blk = (volatile s32 *)(BLOCKS + 128u * v);
            for (f = 0; f < 32; f++)
                blk[f] = 0;
        }
    }
}

/* ev_tick (30 Hz, UI task): a track newly becoming RESAMPLE with the knobs the stock switch leaves
 * (the ONESHOT defaults: PLAY 3, BR 0, STRT 0, LEN 120, LOOP 0) gets D = REC and G = MAIN L+R. */
#define UI_KIT      0x4199dc44u           /* pointer to the current pattern's kit */
#define SOUND(k, t) ((k) + 0x20u + 0xa2u * (t))
#define SND_MACHINE 0x7e
#define SND_PARAMS  0x14                  /* 53 words; word s at +2 s */

static u32 seen_kit;
static u8 seen_machine[8];

void digiresample_tick(void *ctrl)
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
            if (w[18] == 0x0300 && w[19] == 0 && w[21] == 0 && w[22] == 0x7800 && w[W_SRC] == 0) {
                w[W_REC] = 0;
                w[W_SRC] = 5 << 8;        /* MAIN L+R */
            }
        }
        seen_machine[t] = m;
    }
    seen_kit = kit;
}
