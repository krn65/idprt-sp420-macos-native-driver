# Attribution and provenance

## SP420 adaptation

**Developer and maintainer: Kollin Napier.**

This project adapts a native macOS CUPS raster renderer for the iDPRT SP420. Its SP420 command envelope was established through protocol analysis and verified by physical printing. The adaptation includes model-specific initialization and bitmap framing, bounded input validation, complete-job staging, packaging, and tests.

## Upstream code

Rendering and halftone code in `src/rastertosp420.c`, and the starting PPD template, are derived from [hubooy/deli-tspl-cups](https://github.com/hubooy/deli-tspl-cups), copyright 2026 hubooy, under the MIT license. That copyright and permission notice are retained in [LICENSE](LICENSE). Kollin Napier's authorship of the SP420 adaptation does not replace the upstream author's credit.

The SP420 implementations in [thorrak/rpi-tspl-cups-driver](https://github.com/thorrak/rpi-tspl-cups-driver) and [cbiffle/raster-tspl-rs](https://github.com/cbiffle/raster-tspl-rs) were consulted as comparison references. Their code and binaries are not included in this MIT-derived renderer.

No proprietary iDPRT executable or PPD is distributed by this repository. Model names identify the hardware this community driver targets; they do not imply vendor affiliation or endorsement.
