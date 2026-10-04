| SPDX-License-Identifier: GPL-2.0-or-later
| digiresample: the SRC page layout, value readouts and LFO destination name for the RESAMPLE machine (OS 1.53).
| Same scheme as digigrain's page.s (see there for the firmware routines). Ids 1 and 2 are the spare
| parameter descriptors (tools/gen_resample_sites.py): D = REC/PLAY on SAMP's word 20, G = SRC on LOOP's
| word 23; the other six knobs are ONESHOT's own descriptors (TUNE, PLAY, BR, STRT, LEN, LEV).
        .equ    LAYOUT_ON,  0x400657d2          | stock: after the two replaced instructions
        .equ    STR_A,      0x429a11dc          | SLICE's entry's two std::string objects
        .equ    STR_B,      0x429a11fc
        .equ    MACHINE,    7

        .section .run, "ax"
        .globl  digiresample_layout
digiresample_layout:
        moveq   #3, %d1                         | the replaced instructions
        move.l  4(%sp), %d0
        moveq   #MACHINE, %d1
        cmp.l   %d0, %d1
        bne.s   1f
        move.l  #digiresample_layout_entry, %d0
        rts
1:      moveq   #3, %d1
        jmp     LAYOUT_ON

        .balign 4
digiresample_layout_entry:
        .long   STR_A, STR_B
        .long   0x6c, 0x6d, 0x6e, 1, 0x70, 0x71, 2, 0x73   | TUNE PLAY BR REC/PLAY STRT LEN SRC LEV
        .long   0x0a

        .globl  digiresample_str_mode_long, digiresample_str_mode, digiresample_str_src_long, digiresample_str_src
digiresample_str_mode_long: .asciz  "Rec/Play"
digiresample_str_mode:      .asciz  "R/P"
digiresample_str_src_long:  .asciz  "Rec Source"
digiresample_str_src:       .asciz  "SRC"
        .balign 2

| Value readouts: 0x400657ee(id, word) -> the knob-turn title's value; 0x4000f324(obj, id, word, out) ->
| the value under a turning knob. Ids 1 and 2 are only ours, so no machine check is needed; everything
| else redoes the replaced instructions and runs the stock code.
        .equ    READOUT_ON, 0x400657f8
        .equ    READOUT_BUF, 0x4197ce98
        .equ    CAPTION_ON, 0x4000f32c

| d1 = descriptor id -> d0 = 1 if our readout applies, else 0. Clobbers d0.
digiresample_rd_want:
        moveq   #1, %d0
        cmp.l   %d0, %d1
        beq.s   1f
        moveq   #2, %d0
        cmp.l   %d0, %d1
        bne.s   0f
1:      moveq   #1, %d0
        rts
0:      moveq   #0, %d0
        rts
        .globl  digiresample_readout
digiresample_readout:                              | 0x400657ee(id, word)
        move.l  4(%sp), %d1
        jsr     digiresample_rd_want
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

        .globl  digiresample_caption
digiresample_caption:                              | 0x4000f324(obj, id, word, out)
        move.l  8(%sp), %d1
        jsr     digiresample_rd_want
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

| LFO DEST list. The firmware names a destination from the descriptor of the parameter id found for it (the
| list holds ONESHOT's ids), so a RESAMPLE track would see LOOP where the SRC knob is. The list/text
| formatter 0x400a42ec reads descriptor + id * 52 from 0x401a9d9c (long name +0x28, short +0x30; table in
| a3, id * 52 in d0, id in d2); the DEST knob's icon 0x40065d3e (table in d6, id * 52 in d0, id in d3).
| When the active track is RESAMPLE and the id is LOOP (0x72), point the table at ours (one entry).
| D (SAMP's word) is not modulatable: the engine reads it from the unmodulated copy at the trig.
        .equ    DEST_ON,    0x400a436e
        .equ    ICON_ON,    0x40065dce
        .equ    DESC_TAB,   0x401a9d9c
        .equ    ACTIVE_TRK, 0x4197b6b4
        .equ    UI_KIT,     0x4199dc44
        .macro  RESAMPLE_ONLY fail              | falls through only if the active track is RESAMPLE (uses d1, a0, a1)
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
        lea     digiresample_dest_tab, %a3
        jmp     DEST_ON
8:
        .endm

        .macro  ICON_ID id, idx
        moveq   #\id, %d1
        cmp.l   %d1, %d3
        bne.s   8f
        moveq   #\idx, %d3
        move.l  #\idx * 52, %d0
        move.l  #digiresample_dest_tab, %d6
        jmp     ICON_ON
8:
        .endm

        .globl  digiresample_dest_names, digiresample_dest_icon
digiresample_dest_names:
        lea     DESC_TAB, %a3                   | the replaced instructions
        lea     0x401062dc, %a2
        RESAMPLE_ONLY 9f
        NAMES_ID 0x72, 0                        | LOOP -> SRC
9:      jmp     DEST_ON

digiresample_dest_icon:
        move.l  #DESC_TAB, %d6                  | the replaced instruction
        RESAMPLE_ONLY 9f
        ICON_ID 0x72, 0
9:      jmp     ICON_ON

        .equ    GROUP_SAMPLE, 0x401c6afe
        .balign 4
digiresample_dest_tab:
        .space  40
        .long   digiresample_str_src_long, GROUP_SAMPLE, digiresample_str_src
