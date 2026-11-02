Native ARM64 CUPS driver for the USB iDPRT SP420, developed and maintained by Kollin Napier.

Physically verified on macOS 27.0.1 with an Apple-silicon Mac: a diagnostic, a full-page native-queue test, and a real Pirate Ship label. Other macOS versions and printer models are not claimed as physically tested. The build deployment target is macOS 14.0.

Download the `.pkg` and `SHA256SUMS.txt`, verify the checksum, then open the installer. Select **iDPRT SP420 (Native)** in the normal macOS print dialog. Default stock is 100 x 150 mm; true 4 x 6 inches is a separate choice.

This first public package is unsigned and not Apple-notarized. The ARM64 executable has an ad hoc signature. GitHub build provenance and checksums are provided; neither replaces Apple signing or guarantees vulnerability-free software. Source builds are available for users who prefer to inspect and compile the code. Do not disable Gatekeeper or SIP globally.

Includes reproducible unit/contract/integration/package tests and AddressSanitizer/UndefinedBehaviorSanitizer checks. The MIT license preserves upstream rendering-code attribution. See README, SECURITY, NOTICE, and the changelog for installation, privacy, support boundaries, and uninstalling.
