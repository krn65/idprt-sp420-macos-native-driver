/* SPDX-License-Identifier: MIT
 * Derived from https://github.com/hubooy/deli-tspl-cups (2026 hubooy).
 * SP420 adaptation developed and maintained by Kollin Napier.
 * Vendor-observed framing, explicit preserved-printer defaults,
 * bounded raster validation, complete-job staging and checked output.
 * Protocol facts were independently observed; no vendor binary is distributed.
 * Retain the accompanying MIT LICENSE.
 *
 * rastertotspl.c - CUPS raster filter for TSPL/TSPL2 thermal label printers
 *                  (Deli DL-888B and other TSC-compatible printers).
 *
 * Invoked by cupsd as:  rastertotspl job-id user title copies options [file]
 * Reads CUPS raster (8-bit gray preferred) and writes TSPL to stdout.
 *
 * Options (from the PPD or -o):
 *   Darkness      0..15                    -> DENSITY
 *   PrintSpeed    1..6 (inch/s)            -> SPEED
 *   MediaTracking Gap|BlackMark|Continuous -> GAP / BLINE
 *   GapHeight     1..10 (mm)               -> GAP/BLINE height
 *   Direction     0|1                      -> DIRECTION
 *   Mirror        0|1                      -> DIRECTION n,1
 *   Halftone      Threshold|Ordered|Diffusion
 *   XShift        -10..10 (mm)             -> SHIFT
 *   YShift        0..20 (mm)               -> REFERENCE 0,y
 */

#include <cups/cups.h>
#include <cups/ppd.h>
#include <cups/raster.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <math.h>
#include <locale.h>
#include <limits.h>

#ifndef DRIVER_VERSION
#define DRIVER_VERSION "development"
#endif
#define VERSION DRIVER_VERSION
#define MAX_WIDTH_DOTS 864     /* DL-888B: 108 mm print head @ 203 dpi */
#define MAX_WIDTH_MM   108.0
#define MAX_HEIGHT_DOTS 2400

static FILE *job_output;
static volatile sig_atomic_t cancelled;
static void cancel_job(int sig) { (void)sig; cancelled = 1; }
typedef struct { int fd; unsigned long long bytes; int error; } input_t;
static ssize_t read_input(void *context, unsigned char *buffer, size_t count)
{
  input_t *input = context;
  ssize_t n;
  do { n = read(input->fd, buffer, count); } while (n < 0 && errno == EINTR && !cancelled);
  if (n > 0) input->bytes += (unsigned long long)n;
  else if (n < 0) input->error = errno;
  return n;
}

enum { HT_THRESHOLD = 0, HT_ORDERED = 1, HT_DIFFUSION = 2 };
enum { MEDIA_SAVED = -1, MEDIA_GAP = 0, MEDIA_BLINE = 1, MEDIA_CONTINUOUS = 2 };

typedef struct
{
  int darkness;
  int speed;
  int media;
  int gap_mm;
  int direction;
  int mirror;
  int halftone;
  int xshift_mm;
  int yshift_mm;
  int rotate;      /* 0 or 180: rotate the image in software */
  unsigned copies;
} opts_t;

static const unsigned char bayer8[8][8] =
{
  {  0, 32,  8, 40,  2, 34, 10, 42 },
  { 48, 16, 56, 24, 50, 18, 58, 26 },
  { 12, 44,  4, 36, 14, 46,  6, 38 },
  { 60, 28, 52, 20, 62, 30, 54, 22 },
  {  3, 35, 11, 43,  1, 33,  9, 41 },
  { 51, 19, 59, 27, 49, 17, 57, 25 },
  { 15, 47,  7, 39, 13, 45,  5, 37 },
  { 63, 31, 55, 23, 61, 29, 53, 21 }
};

static const char *
get_opt(const char *kw, int num_options, cups_option_t *options,
        ppd_file_t *ppd, const char *def)
{
  const char *v = cupsGetOption(kw, num_options, options);
  if (v && *v)
    return v;
  if (ppd)
  {
    ppd_choice_t *c = ppdFindMarkedChoice(ppd, kw);
    if (c)
      return c->choice;
  }
  return def;
}

static int
clampi(int v, int lo, int hi)
{
  return v < lo ? lo : (v > hi ? hi : v);
}

static void
read_opts(opts_t *o, int num_options, cups_option_t *options, ppd_file_t *ppd)
{
  const char *s;

  s = get_opt("Darkness", num_options, options, ppd, "None");
  o->darkness = !strcasecmp(s, "None") ? -1 : clampi(atoi(s), 0, 15);
  s = get_opt("PrintSpeed", num_options, options, ppd, "None");
  o->speed = !strcasecmp(s, "None") ? -1 : clampi(atoi(s), 1, 6);
  o->gap_mm    = clampi(atoi(get_opt("GapHeight", num_options, options, ppd, "2")), 0, 20);
  o->direction = clampi(atoi(get_opt("Direction", num_options, options, ppd, "0")), 0, 1);
  o->mirror    = clampi(atoi(get_opt("Mirror", num_options, options, ppd, "0")), 0, 1);
  o->xshift_mm = clampi(atoi(get_opt("XShift", num_options, options, ppd, "0")), -10, 10);
  o->yshift_mm = clampi(atoi(get_opt("YShift", num_options, options, ppd, "0")), 0, 20);
  o->rotate    = atoi(get_opt("Rotate", num_options, options, ppd, "0")) == 180 ? 180 : 0;

  s = get_opt("MediaTracking", num_options, options, ppd, "None");
  if (!strcasecmp(s, "None"))
    o->media = MEDIA_SAVED;
  else if (!strcasecmp(s, "BlackMark"))
    o->media = MEDIA_BLINE;
  else if (!strcasecmp(s, "Continuous"))
    o->media = MEDIA_CONTINUOUS;
  else
    o->media = MEDIA_GAP;

  s = get_opt("Halftone", num_options, options, ppd, "Threshold");
  if (!strcasecmp(s, "Ordered"))
    o->halftone = HT_ORDERED;
  else if (!strcasecmp(s, "Diffusion"))
    o->halftone = HT_DIFFUSION;
  else
    o->halftone = HT_THRESHOLD;
}

/* Convert one raster line to 8-bit gray (255 = white). */
static void
line_to_gray(const cups_page_header2_t *h, const unsigned char *line,
             unsigned char *gray, unsigned W)
{
  unsigned x;

  switch (h->cupsBitsPerPixel)
  {
    case 1 :
      for (x = 0; x < W; x++)
      {
        int bit = (line[x >> 3] >> (7 - (x & 7))) & 1;
        if (h->cupsColorSpace == CUPS_CSPACE_K)
          gray[x] = bit ? 0 : 255;
        else
          gray[x] = bit ? 255 : 0;
      }
      break;

    case 8 :
      if (h->cupsColorSpace == CUPS_CSPACE_K)
        for (x = 0; x < W; x++)
          gray[x] = (unsigned char)(255 - line[x]);
      else
        memcpy(gray, line, W);
      break;

    case 24 :
      for (x = 0; x < W; x++)
        gray[x] = (unsigned char)((line[3 * x] * 299 + line[3 * x + 1] * 587 +
                                   line[3 * x + 2] * 114) / 1000);
      break;

    case 32 :
      for (x = 0; x < W; x++)
      {
        const unsigned char *p = line + 4 * x;
        int m = p[0];
        if (p[1] > m) m = p[1];
        if (p[2] > m) m = p[2];
        if (p[3] > m) m = p[3];
        gray[x] = (unsigned char)(255 - m);
      }
      break;

    default :
      memset(gray, 255, W);
      break;
  }
}

/* Halftone one gray row into 1-bit TSPL bitmap row (bit 0 = black). */
static void
halftone_row(const unsigned char *gray, unsigned W, unsigned y, int mode,
             int *err, int *nerr, unsigned char *out)
{
  unsigned x;

  for (x = 0; x < W; x++)
  {
    int black;

    if (mode == HT_ORDERED)
    {
      black = gray[x] < (bayer8[y & 7][x & 7] * 4 + 2);
    }
    else if (mode == HT_DIFFUSION)
    {
      int v = gray[x] + err[x + 1];
      int e;

      black = v < 128;
      e     = v - (black ? 0 : 255);
      err[x + 2]  += e * 7 / 16;
      nerr[x]     += e * 3 / 16;
      nerr[x + 1] += e * 5 / 16;
      nerr[x + 2] += e / 16;
    }
    else
    {
      black = gray[x] < 128;
    }

    if (black)
      out[x >> 3] &= (unsigned char)~(0x80 >> (x & 7));
  }

  if (mode == HT_DIFFUSION)
  {
    memcpy(err, nerr, (W + 2) * sizeof(int));
    memset(nerr, 0, (W + 2) * sizeof(int));
  }
}

static int
emit_page(const cups_page_header2_t *h, const opts_t *o,
          const unsigned char *bm, unsigned wbytes, unsigned H)
{
  double dpi   = h->HWResolution[0] ? h->HWResolution[0] : 203;
  double wmm   = h->cupsPageSize[0] > 0 ? h->cupsPageSize[0] * 25.4 / 72.0 : h->cupsWidth  / dpi * 25.4;
  double hmm   = h->cupsPageSize[1] > 0 ? h->cupsPageSize[1] * 25.4 / 72.0 : h->cupsHeight / dpi * 25.4;
  int    xdots = (int)(o->xshift_mm * dpi / 25.4);
  int    ydots = (int)(o->yshift_mm * dpi / 25.4);
  if (!isfinite(wmm) || !isfinite(hmm) || wmm <= 0 || wmm > 108.1 ||
      hmm <= 0 || hmm > 300.1) {
    fputs("ERROR: Unsupported or invalid SP420 page dimensions\n", stderr);
    return 0;
  }

  fprintf(job_output, "SIZE %.1f mm, %.1f mm\r\n", wmm, hmm);
  switch (o->media)
  {
    case MEDIA_BLINE :      fprintf(job_output, "BLINE %d mm, 0 mm\r\n", o->gap_mm); break;
    case MEDIA_CONTINUOUS : fputs("GAP 0 mm, 0 mm\r\n", job_output); break;
    case MEDIA_GAP :        fprintf(job_output, "GAP %d mm, 0 mm\r\n", o->gap_mm); break;
    default : break; /* Preserve printer's configured media mode. */
  }
  if (o->darkness >= 0) fprintf(job_output, "DENSITY %d\r\n", o->darkness);
  if (o->speed >= 0) fprintf(job_output, "SPEED %d\r\n", o->speed);
  if (o->mirror)
    fprintf(job_output, "DIRECTION %d,1\r\n", o->direction);
  else if (o->direction)
    fprintf(job_output, "DIRECTION %d\r\n", o->direction);
  if (ydots) fprintf(job_output, "REFERENCE 0,%d\r\n", ydots);
  if (xdots)
    fprintf(job_output, "SHIFT %d\r\n", xdots);
  fputs("SET TEAR ON\r\nSET CUTTER OFF\r\nSET PEEL OFF\r\nCLS\r\n", job_output);
  fprintf(job_output, "BITMAP 0,0,%u,%u,1,", wbytes, H);
  size_t length = (size_t)wbytes * H;
  if (fwrite(bm, 1, length, job_output) != length) return 0;
  fprintf(job_output, "\r\nPRINT 1,%u\r\n", o->copies);
  return !ferror(job_output);
}

int
main(int argc, char *argv[])
{
  int                  fd = 0;
  int                  num_options = 0;
  cups_option_t        *options = NULL;
  ppd_file_t           *ppd = NULL;
  opts_t               o;
  cups_raster_t        *ras;
  cups_page_header2_t  h;
  int                  page = 0;
  int                  status = 1;
  char                 *end;
  long                 copies;
  input_t              input = {0};
  unsigned long long   before_header = 0;

  if (argc < 6 || argc > 7)
  {
    fputs("Usage: rastertosp420 job-id user title copies options [file]\n", stderr);
    return 1;
  }

  signal(SIGPIPE, SIG_IGN);
  signal(SIGTERM, cancel_job);
  signal(SIGINT, cancel_job);
  setlocale(LC_NUMERIC, "C");
  errno = 0;
  copies = strtol(argv[4], &end, 10);
  if (errno || *end || end == argv[4] || copies < 1 || copies > 999) {
    fputs("ERROR: Copies must be an integer from 1 through 999\n", stderr);
    return 1;
  }

  if (argc == 7)
  {
    if ((fd = open(argv[6], O_RDONLY)) < 0)
    {
      fprintf(stderr, "ERROR: Unable to open raster file %s: %s\n", argv[6], strerror(errno));
      return 1;
    }
  }

  num_options = cupsParseOptions(argv[5], 0, &options);
  const char *ppd_path = getenv("PPD");
  if (ppd_path && *ppd_path) ppd = ppdOpenFile(ppd_path);
  if (ppd)
  {
    ppdMarkDefaults(ppd);
    cupsMarkOptions(ppd, num_options, options);
  }
  else
    fputs("DEBUG: rastertotspl: no PPD, using built-in defaults\n", stderr);

  read_opts(&o, num_options, options, ppd);
  o.copies = (unsigned)copies;
  fprintf(stderr, "DEBUG: rastertotspl " VERSION ": darkness=%d speed=%d media=%d gap=%dmm "
                  "direction=%d mirror=%d halftone=%d xshift=%dmm yshift=%dmm rotate=%d\n",
          o.darkness, o.speed, o.media, o.gap_mm, o.direction, o.mirror, o.halftone,
          o.xshift_mm, o.yshift_mm, o.rotate);

  input.fd = fd;
  ras = cupsRasterOpenIO(read_input, &input, CUPS_RASTER_READ);
  if (!ras)
  {
    fputs("ERROR: Unable to open raster stream\n", stderr);
    goto cleanup;
  }
  job_output = tmpfile();
  if (!job_output) { perror("ERROR: Cannot stage print job"); goto cleanup; }
  /* The complete job is validated before any printer bytes reach stdout. */
  unsigned char preamble[512] = {0};
  if (fwrite(preamble, 1, sizeof(preamble), job_output) != sizeof(preamble) ||
      fputs("\r\n", job_output) == EOF) goto cleanup;

  while ((before_header = input.bytes), cupsRasterReadHeader2(ras, &h))
  {
    unsigned       W, H, wbytes, y;
    unsigned char  *bm, *line, *gray;
    int            *err, *nerr;

    page++;
    fprintf(stderr, "PAGE: %d 1\n", page);
    fprintf(stderr, "DEBUG: page %d: %ux%u px, %u bpp, cspace=%d, bpl=%u, %ux%u dpi, "
                    "pagesize=%.1fx%.1f pt, copies=%u\n",
            page, h.cupsWidth, h.cupsHeight, h.cupsBitsPerPixel, (int)h.cupsColorSpace,
            h.cupsBytesPerLine, h.HWResolution[0], h.HWResolution[1],
            h.cupsPageSize[0], h.cupsPageSize[1], h.NumCopies);

    unsigned min_bpl = 0;
    int gray_format = (h.cupsColorSpace == CUPS_CSPACE_W ||
                       h.cupsColorSpace == CUPS_CSPACE_K) &&
                      (h.cupsBitsPerPixel == 1 || h.cupsBitsPerPixel == 8) &&
                      h.cupsBitsPerColor == h.cupsBitsPerPixel;
    int rgb_format = h.cupsColorSpace == CUPS_CSPACE_RGB &&
                     h.cupsBitsPerPixel == 24 && h.cupsBitsPerColor == 8;
    if (cancelled || page > 1000 || h.cupsWidth == 0 || h.cupsHeight == 0 ||
        h.cupsWidth > MAX_WIDTH_DOTS || h.cupsHeight > MAX_HEIGHT_DOTS ||
        h.HWResolution[0] != 203 || h.HWResolution[1] != 203 ||
        h.cupsColorOrder != CUPS_ORDER_CHUNKED || (!gray_format && !rgb_format))
    {
      fprintf(stderr, "ERROR: page %d has unsupported dimensions, resolution or raster format\n", page);
      goto cleanup;
    }
    min_bpl = (h.cupsWidth * h.cupsBitsPerPixel + 7) / 8;
    if (h.cupsBytesPerLine < min_bpl || h.cupsBytesPerLine > 65536) {
      fprintf(stderr, "ERROR: Invalid row length on page %d\n", page);
      goto cleanup;
    }
    if (h.NumCopies > 999) {
      fprintf(stderr, "ERROR: Unsupported raster copies: %u\n", h.NumCopies);
      goto cleanup;
    }
    /* Native CUPS rasterization already carries the requested count here.
     * Never multiply that count by argv[4]. */
    o.copies = h.NumCopies > 0 ? h.NumCopies : (unsigned)copies;

    W      = h.cupsWidth;
    H      = h.cupsHeight;
    wbytes = (W + 7) / 8;

    bm   = malloc((size_t)wbytes * H);
    line = malloc(h.cupsBytesPerLine);
    gray = malloc(W);
    err  = calloc(W + 2, sizeof(int));
    nerr = calloc(W + 2, sizeof(int));
    if (!bm || !line || !gray || !err || !nerr)
    {
      fputs("ERROR: Out of memory\n", stderr);
      free(bm); free(line); free(gray); free(err); free(nerr);
      goto cleanup;
    }
    memset(bm, 0xFF, (size_t)wbytes * H);         /* 1 = white, 0 = black */

    if (o.rotate == 180)
    {
      /* Read the whole page, then emit rows bottom-up and mirrored. */
      unsigned char *pagebuf = malloc((size_t)W * H);
      unsigned char *rrow    = malloc(W);
      unsigned       x;

      if (!pagebuf || !rrow)
      {
        fputs("ERROR: Out of memory\n", stderr);
        free(pagebuf); free(rrow);
        free(bm); free(line); free(gray); free(err); free(nerr);
        goto cleanup;
      }
      for (y = 0; y < H; y++)
      {
        if (cancelled || cupsRasterReadPixels(ras, line, h.cupsBytesPerLine) != h.cupsBytesPerLine)
        {
          fprintf(stderr, "ERROR: short raster read at line %u of page %d\n", y, page);
          free(pagebuf); free(rrow);
          free(bm); free(line); free(gray); free(err); free(nerr);
          goto cleanup;
        }
        line_to_gray(&h, line, pagebuf + (size_t)y * W, W);
      }
      for (y = 0; y < H; y++)
      {
        const unsigned char *src = pagebuf + (size_t)(H - 1 - y) * W;
        for (x = 0; x < W; x++)
          rrow[x] = src[W - 1 - x];
        halftone_row(rrow, W, y, o.halftone, err, nerr, bm + (size_t)y * wbytes);
      }
      free(pagebuf); free(rrow);
    }
    else
    {
      for (y = 0; y < H; y++)
      {
        if (cancelled || cupsRasterReadPixels(ras, line, h.cupsBytesPerLine) != h.cupsBytesPerLine)
        {
          fprintf(stderr, "ERROR: short raster read at line %u of page %d\n", y, page);
          free(bm); free(line); free(gray); free(err); free(nerr);
          goto cleanup;
        }
        line_to_gray(&h, line, gray, W);
        halftone_row(gray, W, y, o.halftone, err, nerr, bm + (size_t)y * wbytes);
      }
    }

    int emitted = emit_page(&h, &o, bm, wbytes, H);

    free(bm); free(line); free(gray); free(err); free(nerr);
    if (!emitted) goto cleanup;
    fprintf(stderr, "INFO: Encoded page %d (%u x %u dots)\n", page, W, H);
  }

  const char *raster_error = cupsRasterErrorString();
  if (cancelled || !page || input.error || input.bytes != before_header ||
      (raster_error && *raster_error)) {
    fprintf(stderr, "ERROR: Incomplete or empty raster job: %s\n",
            cancelled ? "cancelled" : raster_error ? raster_error :
            input.error ? strerror(input.error) : !page ? "no pages" : "partial trailing header");
    goto cleanup;
  }
  if (fflush(job_output) || fseek(job_output, 0, SEEK_SET)) goto cleanup;
  unsigned char block[8192];
  size_t length;
  while ((length = fread(block, 1, sizeof(block), job_output)) > 0) {
    if (cancelled || fwrite(block, 1, length, stdout) != length) {
      fputs("ERROR: Printer output failed or job cancelled\n", stderr);
      goto cleanup;
    }
  }
  if (ferror(job_output) || fflush(stdout) || ferror(stdout)) goto cleanup;
  status = 0;

cleanup:
  if (job_output) fclose(job_output);
  if (ras) cupsRasterClose(ras);
  if (fd)
    close(fd);
  if (ppd)
    ppdClose(ppd);
  cupsFreeOptions(num_options, options);

  return status;
}
