# Changelog

## 0.3.0 — 2026-11-01

First public release of the iDPRT SP420 Native Driver for macOS.

- Native ARM64 CUPS raster filter with the SP420's verified initialization, bitmap framing, and tear-off sequence.
- An independent PPD with 100 × 150 mm and true 4 × 6-inch paper sizes at 203 dpi.
- Printer-controlled defaults for media tracking, speed, and darkness.
- Offline unit, raster contract, and CoreGraphics/CUPS integration tests, plus sanitizer execution.
- Source build and installer packaging scripts, checksums, installation instructions, and an uninstall helper.
- Upstream MIT attribution and a security reporting policy.

Physical validation used an SP420 over USB on an Apple silicon Mac running macOS 27.0.1. The working 0.2.0 development build printed a diagnostic, full-page test, and a real Pirate Ship label. Public-release changes and their validation are recorded in the repository and release notes; other operating systems and printer models are not claimed as tested.

## 0.2.0 — 2026-11-01

Local development build. Established successful printing through a dedicated native macOS queue without Rosetta. This build was not published as a public release.
