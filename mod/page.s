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
        .long   0x6c, 0x6d, 0x70, 0x6f, 1, 2, 3, 0x73   | TUNE PLAY STRT(position) SAMP DENS SHAPE RAND LEV
        .long   0x0a

| Labels for descriptors 1-3 (tools/gen_page_sites.py): long name and the knob's short label.
        .globl  digigrain_str_dens_long, digigrain_str_dens, digigrain_str_shape_long, digigrain_str_shape
        .globl  digigrain_str_rand_long, digigrain_str_rand
digigrain_str_dens_long:   .asciz  "Grain Density"
digigrain_str_dens:        .asciz  "DENS"
digigrain_str_shape_long:  .asciz  "Grain Shape"
digigrain_str_shape:       .asciz  "SHAPE"
digigrain_str_rand_long:   .asciz  "Randomness"
digigrain_str_rand:        .asciz  "RAND"
        .balign 2
