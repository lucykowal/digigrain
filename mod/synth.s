| SPDX-License-Identifier: GPL-2.0-or-later
| digigrain: wrappers around the render ISR's two voice-synth calls (OS 1.53).
| The ISR calls 0x40075184 and then 0x400757fe, each with the same five stack arguments (a2,
| 0x4199e466, d5, d7, 0x80001f18). 0x40075184 reads each voice's PLAY word (and decides a
| non-looping voice's end), so digigrain_granular_pre() (which neutralises the GRANULAR shadow's
| PLAY, STRT, LEN and LOOP words) must run before it: digigrain_synth_pre does that and then
| calls the stock routine. 0x400757fe fills the blocks of ALL eight voices at
| 0x80001a18 + 128 * v (measured: it rewrites voice 0's block too), so digigrain_synth_all calls
| it and then digigrain_granular_render(), which overwrites GRANULAR voices' blocks before the
| filter, amp and mixer stages read them. Registers d2-d7/a2-a6 are kept by the C ABI and the
| stock routines; the callers pop their own arguments, so each wrapper only pops its copies.
        .equ    SYNTH_PRE,  0x40075184
        .equ    SYNTH_ALL,  0x400757fe

        .section .run, "ax"
        .globl  digigrain_synth_pre, digigrain_synth_all
digigrain_synth_pre:
        jsr     digigrain_granular_pre
        .rept   5
        move.l  20(%sp), -(%sp)
        .endr
        jsr     SYNTH_PRE
        lea     20(%sp), %sp
        rts
digigrain_synth_all:
        .rept   5
        move.l  20(%sp), -(%sp)
        .endr
        jsr     SYNTH_ALL
        lea     20(%sp), %sp
        jsr     digigrain_granular_render
        rts
