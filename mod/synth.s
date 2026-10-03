| SPDX-License-Identifier: GPL-2.0-or-later
| lucys-granular: wrappers around the render ISR's voice-synth calls (OS 1.53).
| The ISR calls 0x40075184 (voice 0) and 0x400757fe (voices 1-7) with five
| stack arguments (a2, 0x4199e466, d5, d7, 0x80001f18). Each wrapper repeats the
| arguments, calls the stock routine, then calls lucys_granular_render(v0), which may
| overwrite granular voices' blocks at 0x80001a18 + 128*v before the filter, amp and mixer
| stages read them. Registers d2-d7/a2-a6 are kept by the C ABI and the stock routine.
        .equ    SYNTH_V0,   0x40075184
        .equ    SYNTH_V17,  0x400757fe

        .section .run, "ax"
        .globl  lucys_synth_v0, lucys_synth_v17
lucys_synth_v0:
        .rept   5
        move.l  20(%sp), -(%sp)
        .endr
        jsr     SYNTH_V0
        lea     20(%sp), %sp
        clr.l   -(%sp)                  | lucys_granular_render(0)
        jsr     lucys_granular_render
        addq.l  #4, %sp
        rts
lucys_synth_v17:
        .rept   5
        move.l  20(%sp), -(%sp)
        .endr
        jsr     SYNTH_V17
        lea     20(%sp), %sp
        moveq   #1, %d0                 | lucys_granular_render(1)
        move.l  %d0, -(%sp)
        jsr     lucys_granular_render
        addq.l  #4, %sp
        rts
