/* SPDX-License-Identifier: GPL-2.0-or-later */
/* lucys-granular: scaffold. Draws a 3x3 marker in the top-left corner of every
 * screen so a built firmware is visibly running this mod. Replace with the
 * granular SRC machine. */
typedef void (*fillrect_t)(void *bmp, int x0, int y0, int x1, int y1, int colour);

/* Bitmap::fillRect(bmp, x0, y0, x1, y1, colour); screen is 128x64, y = 0 is the bottom row. */
#define FILLRECT ((fillrect_t)0x400c19a6)

void lucys_granular_draw(void *bmp, void *ctrl)
{
    (void)ctrl;
    FILLRECT(bmp, 0, 61, 2, 63, 1);
}
