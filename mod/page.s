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

| Value readouts. Two firmware routines turn a parameter's 8.8 word into text:
|   0x400657ee(id, word)                  -> the page's knob-turn title ("Grain Rate=..."); fills the
|                                            firmware's readout buffer and returns it in d0
|   0x4000f324(obj, id, word, char *out)  -> the value under a knob while it turns (a 16-byte stack buffer)
| Both look up the id's formatter (RAM, none for ids 1-3: the "%.2f" default). For SPRD (2) and ENV (3),
| which only we use, and for RATE (0x6e, BR's id) while the active track is GRANULAR, rd_format
| (readout.c) writes the text instead; everything else redoes the replaced instructions and runs the
| stock code.
        .equ    READOUT_ON, 0x400657f8          | 0x400657ee: after move.l 4(sp),d1 ; cmpi.l #164,d1
        .equ    READOUT_BUF, 0x4197ce98         | the buffer 0x400657ee returns
        .equ    CAPTION_ON, 0x4000f32c          | 0x4000f324: after lea -20(sp),sp ; movem.l d2-d4/a2-a3,(sp)
        .equ    ACTIVE_TRACK, 0x4197b6b4        | long: the selected track 0..7
        .equ    UI_KIT,     0x4199dc44          | pointer to the current kit
        .equ    SOUND_SIZE, 162                 | kit + 0x20 + 162 * track = a track's sound
        .equ    ID_SPRD,    2
        .equ    ID_ENV,     3

| d1 = descriptor id -> d0 = 1 if our readout applies, else 0. Clobbers d0, d1, a0.
digigrain_rd_want:
        moveq   #ID_SPRD, %d0
        cmp.l   %d0, %d1
        beq.s   1f
        moveq   #ID_ENV, %d0
        cmp.l   %d0, %d1
        beq.s   1f
        moveq   #ID_RATE, %d0
        cmp.l   %d0, %d1
        bne.s   0f
        move.l  ACTIVE_TRACK, %d0               | RATE: only on a GRANULAR track
        moveq   #7, %d1
        cmp.l   %d0, %d1
        bcs.s   0f                              | track > 7 (unsigned)
        movea.l UI_KIT, %a0
        move.l  %a0, %d1
        beq.s   0f
        move.l  #SOUND_SIZE, %d1
        mulu.l  %d1, %d0
        adda.l  %d0, %a0
        moveq   #0, %d0
        move.b  0x20+126(%a0), %d0              | its machine byte
        moveq   #MACHINE, %d1
        cmp.l   %d0, %d1
        bne.s   0f
1:      moveq   #1, %d0
        rts
0:      moveq   #0, %d0
        rts

        .globl  digigrain_readout
digigrain_readout:                              | 0x400657ee(id, word)
        move.l  4(%sp), %d1
        jsr     digigrain_rd_want
        tst.l   %d0
        beq.s   9f
        pea     READOUT_BUF                     | rd_format(id, word, buf)
        move.l  12(%sp), %d1                    | word
        move.l  %d1, -(%sp)
        move.l  12(%sp), %d1                    | id
        move.l  %d1, -(%sp)
        jsr     rd_format
        lea     12(%sp), %sp
        move.l  #READOUT_BUF, %d0
        rts
9:      move.l  4(%sp), %d1                     | the replaced instructions
        cmpi.l  #164, %d1
        jmp     READOUT_ON

        .globl  digigrain_caption
digigrain_caption:                              | 0x4000f324(obj, id, word, out)
        move.l  8(%sp), %d1
        jsr     digigrain_rd_want
        tst.l   %d0
        beq.s   9f
        move.l  16(%sp), %d1                    | rd_format(id, word, out)
        move.l  %d1, -(%sp)
        move.l  16(%sp), %d1                    | word
        move.l  %d1, -(%sp)
        move.l  16(%sp), %d1                    | id
        move.l  %d1, -(%sp)
        jsr     rd_format
        lea     12(%sp), %sp
        rts
9:      lea     -20(%sp), %sp                   | the replaced instructions
        movem.l %d2-%d4/%a2-%a3, (%sp)
        jmp     CAPTION_ON

| LFO DEST list and icon. The firmware names a destination from the descriptor of the parameter id found for
| it (the list holds the ids of the stock machine GRANULAR borrows its parameters from: ONESHOT's 0x6c-0x73),
| so a GRANULAR track would see PLAY, BR, STRT, LEN and LOOP. Two readers need a say, both reading
| descriptor + id * 52 from 0x401a9d9c: the list/text formatter 0x400a42ec (long name +0x28, short +0x30;
| table in a3, id * 52 in d0, id in d2) and the DEST knob's icon 0x40065d3e (group +0x2c, short label
| +0x30; table in d6, id * 52 in d0, id in d3). Each hook sits over the instruction(s) that load the
| table. When the active track (UI kit, 0x4197b6b4) is GRANULAR and the id is PLAY, BR, STRT, LEN or
| LOOP, it points the table at our small one (digigrain_dest_tab) and the id (and id * 52) at the index
| there; everything else runs the stock code.
        .equ    DEST_ON,    0x400a436e          | stock: after the two lea
        .equ    ICON_ON,    0x40065dce          | stock: after the move.l that loads the table
        .equ    DESC_TAB,   0x401a9d9c
        .equ    ACTIVE_TRK, 0x4197b6b4          | the current track (long, 0-7 audio tracks)
        .equ    UI_KIT,     0x4199dc44

        .macro  GRANULAR_ONLY fail              | falls through only if the active track is GRANULAR (uses d1, a0, a1)
        move.l  ACTIVE_TRK, %d1
        cmpi.l  #7, %d1
        bhi.w   \fail
        add.l   %d1, %d1                        | a1 = 0xa2 * track (162 = 128 + 32 + 2)
        move.l  %d1, %a1
        lsl.l   #4, %d1
        adda.l  %d1, %a1
        lsl.l   #2, %d1
        adda.l  %d1, %a1
        move.l  UI_KIT, %a0
        cmpa.l  #0, %a0
        beq.w   \fail
        lea     0x20(%a0,%a1.l), %a0            | the track's sound
        move.b  0x7e(%a0), %d1                  | its machine
        cmpi.b  #MACHINE, %d1
        bne.w   \fail
        .endm

        .macro  NAMES_ID id, idx
        moveq   #\id, %d1
        cmp.l   %d1, %d2
        bne.s   8f
        moveq   #\idx, %d2
        move.l  #\idx * 52, %d0
        lea     digigrain_dest_tab, %a3
        jmp     DEST_ON
8:
        .endm

        .macro  ICON_ID id, idx
        moveq   #\id, %d1
        cmp.l   %d1, %d3
        bne.s   8f
        moveq   #\idx, %d3
        move.l  #\idx * 52, %d0
        move.l  #digigrain_dest_tab, %d6
        jmp     ICON_ON
8:
        .endm

        .globl  digigrain_dest_names, digigrain_dest_icon
digigrain_dest_names:
        lea     DESC_TAB, %a3                   | the replaced instructions
        lea     0x401062dc, %a2
        GRANULAR_ONLY 9f
        NAMES_ID 0x6d, 0                        | PLAY -> ENV
        NAMES_ID 0x6e, 1                        | BR   -> RATE
        NAMES_ID 0x70, 2                        | STRT -> POS
        NAMES_ID 0x71, 3                        | LEN  -> RTIO
        NAMES_ID 0x72, 4                        | LOOP -> SPRD
9:      jmp     DEST_ON

digigrain_dest_icon:
        move.l  #DESC_TAB, %d6                  | the replaced instruction
        GRANULAR_ONLY 9f
        ICON_ID 0x6d, 0
        ICON_ID 0x6e, 1
        ICON_ID 0x70, 2
        ICON_ID 0x71, 3
        ICON_ID 0x72, 4
9:      jmp     ICON_ON

        .equ    GROUP_SAMPLE, 0x401c6afe        | the stock "Sample" group string (+0x2c of ids 0x6c-0x73)
        .macro  DEST_ENTRY long, short          | 52 bytes: only +0x28, +0x2c and +0x30 are read
        .space  40
        .long   \long, GROUP_SAMPLE, \short
        .endm
        .balign 4
digigrain_dest_tab:
        DEST_ENTRY digigrain_str_env_long, digigrain_str_env
        DEST_ENTRY digigrain_str_rate_long, digigrain_str_rate
        DEST_ENTRY digigrain_str_pos_long, digigrain_str_pos
        DEST_ENTRY digigrain_str_rtio_long, digigrain_str_rtio
        DEST_ENTRY digigrain_str_sprd_long, digigrain_str_sprd
