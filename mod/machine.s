| SPDX-License-Identifier: GPL-2.0-or-later
| digigrain: the GRANULAR SRC machine's descriptor for core 2.1's
| core_machines table (elekloader docs/ADAPTING.md, "SRC machines").
| Scaffold: it takes ONESHOT's parameters and plays as ONESHOT, so a GRANULAR
| track behaves like ONESHOT until the engine overrides the render.
        .equ    BMP_VT,       0x401b73b4        | stock Bitmap vtable (OS 1.53)
        .equ    MACHINE_ID,   6                 | fixed for good: kits store it
        .equ    PARAMS_ONESHOT, 0
        .equ    PLAYS_ONESHOT,  0

        .section .run, "ax"
        .balign 4
        .globl  digigrain_granular_machine
digigrain_granular_machine:
        .long   MACHINE_ID, str_name, str_short, icon, PARAMS_ONESHOT, PLAYS_ONESHOT

| 11 x 7 menu icon, a word per column, rows in bits 31-25: scattered grains.
icon:
        .long   BMP_VT, 11, 7, 1, icon_px, icon_mask, 0
icon_px:
        .long   0x38000000, 0x00000000, 0x10000000, 0x54000000, 0x10000000
        .long   0x00000000, 0x7c000000, 0x00000000, 0x10000000, 0x28000000
        .long   0x10000000
icon_mask:
        .long   0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000
        .long   0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000
        .long   0xfe000000
str_name:       .asciz  "GRANULAR"
str_short:      .asciz  "GRAN"
        .balign 2
