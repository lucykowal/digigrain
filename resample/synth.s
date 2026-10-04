| SPDX-License-Identifier: GPL-2.0-or-later
| digiresample: wrappers around the render ISR's two voice-synth calls (OS 1.53); same scheme as
| digigrain's synth.s. digiresample_pre() runs before the stock synth (it points RESAMPLE voices at the
| record buffer and drives the RECORDER); digiresample_post() runs after it has filled every voice's
| block at 0x80001a18 + 128 * v (it silences voices that are recording or have nothing to play).
        .equ    SYNTH_PRE,  0x40075184
        .equ    SYNTH_ALL,  0x400757fe

        .section .run, "ax"
        .globl  digiresample_synth_pre, digiresample_synth_all
digiresample_synth_pre:
        jsr     digiresample_pre
        .rept   5
        move.l  20(%sp), -(%sp)
        .endr
        jsr     SYNTH_PRE
        lea     20(%sp), %sp
        rts
digiresample_synth_all:
        .rept   5
        move.l  20(%sp), -(%sp)
        .endr
        jsr     SYNTH_ALL
        lea     20(%sp), %sp
        jsr     digiresample_post
        rts
