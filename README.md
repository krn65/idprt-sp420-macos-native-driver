# iDPRT SP420 Native Driver for macOS

A native Apple silicon CUPS driver for the **iDPRT SP420 USB label printer**. Print from the normal macOS print dialog without Rosetta.

Developed and maintained by **Kollin Napier**, with rendering code and a PPD template adapted from [hubooy/deli-tspl-cups](https://github.com/hubooy/deli-tspl-cups). See [NOTICE.md](NOTICE.md) and the [MIT license](LICENSE).

## Tested compatibility

| Configuration | Status as of November 1, 2026 |
| --- | --- |
| iDPRT SP420 connected by USB to an Apple silicon Mac, macOS 27.0.1 | Physically tested: diagnostic, full-page output, and a real Pirate Ship shipping label |
| Other Apple silicon Macs or macOS versions | Not physically verified |
| Intel Macs, other printer models, Bluetooth, and network printers | Not supported by this release |

The build targets macOS 14 or later. That deployment target is **not** a tested compatibility claim. Future macOS releases, including macOS 28, are untested. This removes the Rosetta dependency but still uses the CUPS filter/PPD interface supplied by macOS.

## Install

The installer creates **iDPRT SP420 (Native)**. It preserves existing printers and does not change the system's default printer.

1. Connect and power on the SP420.
2. Download `idprt-sp420-macos-native-driver-0.3.0.pkg` and `SHA256SUMS.txt` from the [latest release](https://github.com/krn65/idprt-sp420-macos-native-driver/releases/latest).
3. In Terminal, run this from the download folder and compare the result with the package's line in `SHA256SUMS.txt`:

   ```sh
   shasum -a 256 idprt-sp420-macos-native-driver-0.3.0.pkg
   ```

4. Open the package with macOS Installer and approve the administrator prompt.
5. Select **iDPRT SP420 (Native)** in your app's print dialog.

**Signing status:** the downloadable installer is unsigned and is not notarized by Apple. The ARM64 filter has an ad-hoc signature, which does not verify the developer's identity. Checksums detect a mismatched download; they do not replace Developer ID signing or notarization. If you are uncomfortable installing an unsigned download, [build the package locally](#build-from-source). Do not disable Gatekeeper or SIP to install this driver.

### Paper size

The default is **100 × 150 mm**, matching the original driver's actual default dimensions. For true 4 × 6-inch stock, select **4 × 6 inches (101.6 × 152.4 mm)**. Use **Actual Size / 100%** when the source label already has the correct dimensions.

The driver renders at 203 dpi. Supported custom media is 50–108 mm wide and 25–300 mm long. Darkness, speed, and media tracking default to **Use printer setting**. Explicit changes can persist in the printer; leave those defaults unless a change is needed.

### Printer not added automatically

The driver files are installed in `/Library/Printers/SP420Native`. If no queue appears, connect the SP420 and add it in **System Settings → Printers & Scanners**. Choose **Other…** in the printer software selection and select:

```text
/Library/Printers/SP420Native/idprt-sp420-native.ppd
```

An old queue using iDPRT's Intel-only filter remains separate. Choose the new **Native** queue when testing this driver.

## Build from source

Requirements: an Apple silicon Mac and Xcode Command Line Tools. Tests and package creation additionally use Python 3.9 or later, with only its standard library.

From the repository root:

```sh
make build
make test
make test-sanitize
make package
```

The executable is written to `build/rastertosp420`; the installer is written to `dist/idprt-sp420-macos-native-driver-0.3.0.pkg`. Open that locally built package with macOS Installer.

There are no downloaded libraries or third-party runtime packages. The driver links to Apple's system CUPS library and uses macOS's existing USB backend. Runtime does not need Python, Homebrew, Rosetta, a kernel extension, or an external print server.

## Tests and review

The repository includes C unit assertions, synthetic CUPS raster contract tests, and native CoreGraphics/CUPS integration tests. They check rendering, bitmap polarity and padding, the SP420 command envelope, copies and collation, page bounds, and rejection of malformed input. `make test-sanitize` also uses AddressSanitizer and UndefinedBehaviorSanitizer. See [tests/README.md](tests/README.md).

Automated tests do not print, access USB, require administrator privileges, or contain real shipping labels. Physical printing is a separate compatibility check. Passing tests and source review cannot guarantee that software has no vulnerabilities or certify barcode readability on every printer.

## Uninstall

```sh
sudo /bin/sh /Library/Printers/SP420Native/uninstall.sh
```

Finish or cancel pending native-queue jobs first; the uninstaller refuses to run while they remain. It then removes the native queue and this driver's own files. It preserves the original vendor queue and other printers.

## Contribute or report a problem

See [CONTRIBUTING.md](CONTRIBUTING.md). For security concerns, use [SECURITY.md](SECURITY.md). Reports should omit printer serial numbers, USB URIs, addresses, account details, real labels, and unredacted CUPS logs.

This is an independent community project. It is not an official iDPRT driver and is not affiliated with iDPRT, Apple, or Pirate Ship.
