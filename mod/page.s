| SPDX-License-Identifier: GPL-2.0-or-later
| digigrain: the SRC page layout for the GRANULAR machine (OS 1.53).
| 0x400657cc(machine) returns the page's layout entry: 11 longs {title string, subtitle string,
| eight parameter ids (one per knob, A..H), 10}. The stock function gives every machine past 3
| SLICE's entry. This hook returns ours for machine 6 and runs the stock code for anything else
| (the stock function's first instructions are redone: moveq #3,d1; move.l 4(sp),d0).
        .equ    LAYOUT_ON,  0x400657d2          | stock: after those two instructions
        .equ    STR_A,      0x429a11dc          | SLICE's entry's two std::string objects
        .equ    STR_B,      0x429a11fc
        .equ    MACHINE,    6

        .section .run, "ax"
        .globl  digigrain_layout
digigrain_layout:
        moveq   #3, %d1                         | the replaced instructions
        move.l  4(%sp), %d0
        moveq   #MACHINE, %d1
        cmp.l   %d0, %d1
        bne.s   1f
        move.l  #digigrain_layout_entry, %d0
        rts
1:      moveq   #3, %d1
        jmp     LAYOUT_ON

        .balign 4
digigrain_layout_entry:
        .long   STR_A, STR_B
        .long   0x6c, 0x6e, 2, 0x6f, 0x70, 1, 3, 0x73   | TUNE RATE SPRD SAMP POS RTIO ENV LEV
        .long   0x0a

| Label hooks. The SRC page draws a knob's caption through the short-label accessor 0x4000fe8a(obj, id)
| and the title shown while a knob turns through the long-name accessor 0x4000feac(obj, id); both return
| the string pointer in d0. RATE and POS ride on the stock BR (0x6e) and STRT (0x70) descriptors, so on a
| GRANULAR track (obj -> sound -> machine byte 6, the walk digislicer's dsl_prange does) these hooks
| answer with our strings; for everything else they redo the two replaced instructions
| (move.l 8(sp),d1 ; cmpi.l #164,d1) and run the stock code (which needs the cmpi flags for its scs).
        .equ    PARAM_VT,   0x4017eb58          | the page's parameter object
        .equ    SNDREF_VT,  0x40181330          | the object at its +16
        .equ    SHORT_ON,   0x4000fe94          | stock: after the replaced instructions
        .equ    LONG_ON,    0x4000feb6
        .equ    ID_RATE,    0x6e
        .equ    ID_POS,     0x70

        .macro  LABEL_HOOK name, resume, str_rate, str_pos
        .globl  \name
\name:
        move.l  8(%sp), %d1                     | the descriptor id
        moveq   #ID_RATE, %d0
        cmp.l   %d0, %d1
        beq.s   1f
        moveq   #ID_POS, %d0
        cmp.l   %d0, %d1
        bne.s   9f
1:      movea.l 4(%sp), %a0                     | the parameter object
        move.l  (%a0), %d0
        cmpi.l  #PARAM_VT, %d0
        bne.s   9f
        movea.l 16(%a0), %a0
        move.l  (%a0), %d0
        cmpi.l  #SNDREF_VT, %d0
        bne.s   9f
        movea.l 16(%a0), %a0                    | its sound
        moveq   #0, %d0
        move.b  126(%a0), %d0                   | the sound's machine
        cmpi.l  #MACHINE, %d0
        bne.s   9f
        moveq   #ID_RATE, %d0
        cmp.l   %d0, %d1
        bne.s   2f
        move.l  #\str_rate, %d0
        rts
2:      move.l  #\str_pos, %d0
        rts
9:      cmpi.l  #164, %d1                       | the replaced instructions
        jmp     \resume
        .endm

        LABEL_HOOK digigrain_label_short, SHORT_ON, digigrain_str_rate, digigrain_str_pos
        LABEL_HOOK digigrain_label_long, LONG_ON, digigrain_str_rate_long, digigrain_str_pos_long

| Strings: RATE and POS for the hooks above; RTIO, SPRD and ENV are the long name and short label of
| descriptors 1-3 (tools/gen_page_sites.py).
        .globl  digigrain_str_rtio_long, digigrain_str_rtio, digigrain_str_sprd_long, digigrain_str_sprd
        .globl  digigrain_str_env_long, digigrain_str_env
digigrain_str_rate:        .asciz  "RATE"
digigrain_str_rate_long:   .asciz  "Grain Rate"
digigrain_str_pos:         .asciz  "POS"
digigrain_str_pos_long:    .asciz  "Grain Position"
digigrain_str_rtio_long:   .asciz  "Grain Ratio"
digigrain_str_rtio:        .asciz  "RTIO"
digigrain_str_sprd_long:   .asciz  "Grain Spread"
digigrain_str_sprd:        .asciz  "SPRD"
digigrain_str_env_long:    .asciz  "Grain Envelope"
digigrain_str_env:         .asciz  "ENV"
        .balign 2

| Value readouts. The SRC page's knob overlay (and its other value displays) call 0x400657ee(id, word)
| with the parameter's 8.8 word; it runs the id's formatter into the firmware's readout buffer and
| returns that buffer in d0. For SPRD (2) and ENV (3), which only we use, and for RATE (0x6e, BR's id) while
| the active track is GRANULAR, rd_format (readout.c) fills the buffer instead; everything else redoes the
| two replaced instructions (move.l 4(sp),d1 ; cmpi.l #164,d1) and runs the stock code.
        .equ    READOUT_ON, 0x400657f8          | stock: after those two instructions
        .equ    READOUT_BUF, 0x4197ce98         | the buffer the stock function returns
        .equ    ACTIVE_TRACK, 0x4197b6b4        | long: the selected track 0..7
        .equ    UI_KIT,     0x4199dc44          | pointer to the current kit
        .equ    ID_SPRD,    2
        .equ    ID_ENV,     3

        .globl  digigrain_readout
digigrain_readout:
        move.l  4(%sp), %d1                     | the replaced instructions
        cmpi.l  #164, %d1
        moveq   #ID_SPRD, %d0
        cmp.l   %d0, %d1
        beq.s   2f
        moveq   #ID_ENV, %d0
        cmp.l   %d0, %d1
        beq.s   2f
        moveq   #ID_RATE, %d0
        cmp.l   %d0, %d1
        bne.s   9f
        move.l  ACTIVE_TRACK, %d0               | RATE: only on a GRANULAR track
        moveq   #7, %d1
        cmp.l   %d0, %d1
        bcs.s   8f                              | track > 7 (unsigned)
        movea.l UI_KIT, %a0
        move.l  %a0, %d1
        beq.s   8f
        move.l  #162, %d1                       | the sound at kit + 0x20 + 0xa2 * track
        mulu.l  %d1, %d0
        adda.l  %d0, %a0
        moveq   #0, %d0
        move.b  0x20+126(%a0), %d0              | its machine byte
        moveq   #MACHINE, %d1
        cmp.l   %d0, %d1
        bne.s   8f
2:      pea     READOUT_BUF                     | rd_format(id, word, buf)
        move.l  12(%sp), %d1
        move.l  %d1, -(%sp)
        move.l  12(%sp), %d1
        move.l  %d1, -(%sp)
        jsr     rd_format
        lea     12(%sp), %sp
        move.l  #READOUT_BUF, %d0
        rts
8:      move.l  4(%sp), %d1                     | the id again
9:      cmpi.l  #164, %d1                       | the replaced instructions' flags
        jmp     READOUT_ON
