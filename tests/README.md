# Offline tests

Run `make test` on macOS with Xcode Command Line Tools and Python 3. Run
`make test-sanitize` to compile and exercise the same suite with AddressSanitizer
and UndefinedBehaviorSanitizer. Python uses only its standard library. Tests
compile into a temporary directory and remove their fixtures when finished.
No test contacts a printer, opens USB, submits a CUPS job, requires administrator
access, or downloads a dependency.

The suite combines four kinds of checks:

- C unit assertions exercise grayscale conversion, threshold boundaries,
  halftone extremes, and white padding in the renderer's private functions.
- Synthetic CUPS raster contract tests decode the exact output bytes and check
  initialization, bitmap mode, pixel polarity, rows, copies, page ordering,
  options, and rejection of malformed or unsupported input without partial
  printer output.
- A small synthetic two-page PDF is converted by macOS CoreGraphics/CUPS to
  verify the real raster formats, page sizing, and collated/uncollated copies.
  This integration check skips if the system `cupsfilter` tool is unavailable.
- Package integration checks rebuild in a temporary directory containing a
  generated privacy marker, expand the package without installing it, and check
  its exact file allowlist, modes, root ownership in the BOM, metadata, install
  script identity, ARM64 architecture, ad hoc signature, and release checksum.
  Raw archive names are checked as well as the BOM and expanded filesystem, so
  AppleDouble metadata cannot hide behind the system's resource-fork merging.
  Expanded files and the archive must contain neither the marker nor `/Users/`
  home paths. Shell scripts receive syntax checks. Only the extracted,
  self-contained USB URI predicate is executed; installer and uninstaller scripts
  are never executed.

The package cleaner is tested for safe path handling, rejection of signed or
unrecognized signature states before mutation, and preservation of every payload
and installer-script byte when cleaning an already-clean unsigned package.

`fixture_writer.c` creates intentionally small, non-personal fixtures through
Apple's CUPS raster writer. The parser in `test_driver.py` uses declared bitmap
lengths, so binary pixel bytes cannot be mistaken for a print command. The
known expected alternating pattern and padding are independent of the driver.
The tests do not contain shipping labels, addresses, printer serial numbers,
private log files, or machine-specific paths.

Sanitizers instrument this project's code and test helpers; Apple's system CUPS
library is not rebuilt or instrumented. LeakSanitizer is disabled because it is
not supported by the macOS sanitizer runtime. Passing tests is evidence for the
covered behavior, not a guarantee that software has no vulnerabilities.
The package check always builds the normal release binary, including during
`make test-sanitize`; the raster and renderer checks use the sanitized build.

Physical printing is separate. The maintainer confirmed a diagnostic and a full
page on an SP420 connected to an Apple-silicon Mac running macOS 27.0.1, followed
by a real Pirate Ship label. Automated checks never reproduce those physical
steps or claim to certify barcode readability on every printer.
