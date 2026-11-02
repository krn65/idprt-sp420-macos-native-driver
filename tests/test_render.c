/* SPDX-License-Identifier: MIT
 * Unit tests include the renderer in one translation unit to exercise its
 * private conversion functions without exposing a production testing API.
 */
#define main sp420_filter_main
#include "../src/rastertosp420.c"
#undef main
#include <assert.h>

static void check_threshold(void)
{
  const unsigned char gray[] = {0, 127, 128, 255, 0, 255, 127, 128, 0};
  unsigned char out[2] = {255, 255};
  int err[11] = {0}, next[11] = {0};
  halftone_row(gray, 9, 0, HT_THRESHOLD, err, next, out);
  assert(out[0] == 0x35 && out[1] == 0x7f);
}

static void check_color_conversion(void)
{
  cups_page_header2_t h = {0};
  unsigned char out[3];
  h.cupsBitsPerPixel = 8; h.cupsColorSpace = CUPS_CSPACE_K;
  const unsigned char k[] = {0, 127, 255};
  line_to_gray(&h, k, out, 3);
  assert(out[0] == 255 && out[1] == 128 && out[2] == 0);
  h.cupsBitsPerPixel = 1; h.cupsColorSpace = CUPS_CSPACE_W;
  const unsigned char bits[] = {0xa0};
  line_to_gray(&h, bits, out, 3);
  assert(out[0] == 255 && out[1] == 0 && out[2] == 255);
  h.cupsBitsPerPixel = 24; h.cupsColorSpace = CUPS_CSPACE_RGB;
  const unsigned char rgb[] = {255, 0, 0, 0, 255, 0, 0, 0, 255};
  line_to_gray(&h, rgb, out, 3);
  assert(out[0] == 76 && out[1] == 149 && out[2] == 29);
}

static void check_halftone_extremes(void)
{
  unsigned char gray[13], out[2];
  int err[15], next[15];
  for (int mode = HT_THRESHOLD; mode <= HT_DIFFUSION; mode++) {
    for (int white = 0; white <= 1; white++) {
      memset(gray, white ? 255 : 0, sizeof(gray));
      memset(err, 0, sizeof(err)); memset(next, 0, sizeof(next));
      for (unsigned y = 0; y < 8; y++) {
        memset(out, 255, sizeof(out));
        halftone_row(gray, 13, y, mode, err, next, out);
        assert(out[0] == (white ? 0xff : 0x00));
        assert(out[1] == (white ? 0xff : 0x07));
      }
    }
  }
}

int main(void)
{
  assert(clampi(-1, 0, 15) == 0);
  assert(clampi(16, 0, 15) == 15);
  assert(clampi(8, 0, 15) == 8);
  check_threshold(); check_color_conversion(); check_halftone_extremes();
  puts("renderer unit assertions passed");
  return 0;
}
