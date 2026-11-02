# Verification and release scope

Reviewed November 1, 2026.

- Thirty automated tests pass normally and with AddressSanitizer plus UndefinedBehaviorSanitizer. They cover C renderer unit assertions, synthetic raster contracts, native CoreGraphics copy/collation integration, and package/script/privacy contracts. Run `make test` and `make test-sanitize`.
- The verified protocol printed through a native macOS queue on an SP420 connected by USB to an Apple-silicon Mac running macOS 27.0.1. The maintainer then independently printed a real Pirate Ship label successfully. No real shipping label is included in this repository or its tests.
- Public release packaging is rebuilt from source. Tests check the exact four-file payload, root ownership and file modes, installer scripts, checksums, ARM64 ad hoc signature, and the absence of AppleDouble metadata or local source/account paths in the payload, script archives, BOM, and outer archive metadata.
- Source review covers the raster filter, PPD, privileged scripts, packaging helpers, workflows, fixtures, and documentation. No reportable vulnerability was identified in the reviewed paths. That is a scoped review result, not a guarantee that the project or its platform libraries are vulnerability-free.
- The repository starts with clean public history and a GitHub no-reply commit identity. Printer serial numbers, hardware UUIDs, private hostnames, credentials, personal filesystem paths, raw CUPS logs, and real shipping documents are excluded. The maintainer's requested public name, GitHub identity, and tested operating-system version are intentionally public.
- ASan/UBSan instrument this project's test builds, not Apple's system CUPS implementation. Other macOS releases, printer models, firmware revisions and every barcode/label configuration are not claimed as physically tested.

Release workflow success and artifact provenance must be checked on GitHub for each published tag. The package is currently unsigned and not Apple-notarized; checksums and GitHub build provenance have different purposes from Apple publisher verification.
