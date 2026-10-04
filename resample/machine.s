| SPDX-License-Identifier: GPL-2.0-or-later
| digiresample: the RESAMPLE SRC machine's descriptor for core 2.1's core_machines table
| (elekloader docs/ADAPTING.md, "SRC machines"). It takes ONESHOT's parameters and plays as ONESHOT:
| resample.c points the stock voice at the record buffer (sample slot 0x82) and drives the RECORDER.
        .equ    BMP_VT,       0x401b73b4        | stock Bitmap vtable (OS 1.53)
        .equ    MACHINE_ID,   7                 | fixed for good: kits store it (6 is digigrain's)
        .equ    PARAMS_ONESHOT, 0
        .equ    PLAYS_ONESHOT,  0

        .section .run, "ax"
        .balign 4
        .globl  digiresample_machine
digiresample_machine:
        .long   MACHINE_ID, str_name, str_short, icon, PARAMS_ONESHOT, PLAYS_ONESHOT

| 11 x 7 menu icon, a word per column, rows in bits 31-25: a record dot inside a loop arrow.
icon:
        .long   BMP_VT, 11, 7, 1, icon_px, icon_mask, 0
icon_px:
        .long   0x38000000, 0x44000000, 0x82000000, 0x92000000, 0x82000000
        .long   0x44000000, 0x38000000, 0x10000000, 0x38000000, 0x54000000
        .long   0x10000000
icon_mask:
        .long   0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000
        .long   0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000, 0xfe000000
        .long   0xfe000000
str_name:       .asciz  "RESAMPLE"
str_short:      .asciz  "RSMP"
        .balign 2
