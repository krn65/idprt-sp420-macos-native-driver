/* SPDX-License-Identifier: MIT
 * Synthetic, non-personal CUPS raster fixtures for offline contract tests.
 */
#include <cups/raster.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
  if (argc != 3) return 2;
  const char *mode = argv[1];
  int fd = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0600);
  if (fd < 0) return 2;
  cups_raster_t *r = cupsRasterOpen(fd, CUPS_RASTER_WRITE);
  if (!r) { close(fd); return 2; }
  cups_page_header2_t h;
  memset(&h, 0, sizeof(h));
  h.HWResolution[0] = h.HWResolution[1] = 203;
  h.cupsWidth = 13; h.cupsHeight = 2;
  h.PageSize[0] = 288; h.PageSize[1] = 432;
  h.cupsPageSize[0] = 288; h.cupsPageSize[1] = 432;
  h.cupsColorOrder = CUPS_ORDER_CHUNKED;
  h.cupsNumColors = 1;
  h.cupsBitsPerColor = h.cupsBitsPerPixel = 8;
  h.cupsColorSpace = CUPS_CSPACE_W;
  h.NumCopies = 1;
  if (strstr(mode, "K")) h.cupsColorSpace = CUPS_CSPACE_K;
  if (strstr(mode, "1bit")) h.cupsBitsPerColor = h.cupsBitsPerPixel = 1;
  if (strstr(mode, "copies")) h.NumCopies = 3;
  if (!strcmp(mode, "copies-zero")) h.NumCopies = 0;
  if (!strcmp(mode, "copies-excess")) h.NumCopies = 1000;
  if (!strcmp(mode, "rgb")) {
    h.cupsColorSpace = CUPS_CSPACE_RGB;
    h.cupsBitsPerPixel = 24; h.cupsNumColors = 3;
  }
  if (!strcmp(mode, "bad-format")) {
    h.cupsColorSpace = CUPS_CSPACE_CMYK;
    h.cupsBitsPerPixel = 32; h.cupsNumColors = 4;
  }
  if (!strcmp(mode, "wide")) h.cupsWidth = 865;
  if (!strcmp(mode, "tall")) h.cupsHeight = 2401;
  if (!strcmp(mode, "bad-resolution")) h.HWResolution[0] = 300;
  if (!strcmp(mode, "bad-order")) h.cupsColorOrder = CUPS_ORDER_BANDED;
  if (!strcmp(mode, "large-media")) h.cupsPageSize[0] = 400;
  h.cupsBytesPerLine = (h.cupsWidth * h.cupsBitsPerPixel + 7) / 8;
  unsigned char *row = calloc(h.cupsBytesPerLine, 1);
  if (!row) return 2;
  int pages = !strcmp(mode, "multipage") ? 2 : 1;
  int success = 1;
  for (int page = 0; page < pages; page++) {
    if (!cupsRasterWriteHeader2(r, &h)) { success = 0; break; }
    unsigned rows = !strcmp(mode, "truncated-pixels") ? 1 : h.cupsHeight;
    /* Bound rejection fixtures to avoid needlessly generating large streams. */
    if (rows > 2) rows = 2;
    for (unsigned y = 0; y < rows; y++) {
      memset(row, 0, h.cupsBytesPerLine);
      for (unsigned x = 0; x < h.cupsWidth; x++) {
        unsigned char v = ((x + y + (unsigned)page) % 2) ? 0 : 255;
        if (h.cupsColorSpace == CUPS_CSPACE_K) v = 255 - v;
        if (h.cupsBitsPerPixel == 1) {
          if (v) row[x / 8] |= (unsigned char)(128U >> (x % 8));
        } else if (h.cupsBitsPerPixel == 24) {
          row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = v;
        } else if (h.cupsBitsPerPixel == 8) row[x] = v;
      }
      if (cupsRasterWritePixels(r, row, h.cupsBytesPerLine) != h.cupsBytesPerLine) success = 0;
    }
  }
  free(row); cupsRasterClose(r); close(fd);
  return success ? 0 : 2;
}
