| SPDX-License-Identifier: GPL-2.0-or-later
| lucys-granular: wrapper around the render ISR's voice-synth call (OS 1.53).
| The ISR calls 0x400757fe with five stack arguments (a2, 0x4199e466, d5, d7,
| 0x80001f18); it fills the blocks of ALL eight voices at 0x80001a18 + 128 * v (measured: it
| rewrites voice 0's block too, so the call before it, 0x40075184, must not be used). The
| wrapper calls lucys_granular_pre() (neutralises the shadow voice's STRT/LEN/LOOP words),
| repeats the arguments, calls the stock routine, then calls lucys_granular_render(), which
| overwrites GRANULAR voices' blocks before the filter, amp and mixer stages read them.
| Registers d2-d7/a2-a6 are kept by the C ABI and the stock routine.
        .equ    SYNTH_ALL,  0x400757fe

        .section .run, "ax"
        .globl  lucys_synth_all
lucys_synth_all:
        jsr     lucys_granular_pre
        .rept   5
        move.l  20(%sp), -(%sp)
        .endr
        jsr     SYNTH_ALL
        lea     20(%sp), %sp
        jsr     lucys_granular_render
        rts
