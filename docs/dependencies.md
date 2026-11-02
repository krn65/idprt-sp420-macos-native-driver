# Dependency and build policy

Reviewed November 1, 2026.

The installed filter links only to macOS system libraries (CUPS and the system C runtime). No Python, npm, Homebrew, browser extension, network service, or third-party runtime package is installed. Keep macOS updated for fixes in Apple's system libraries; this repository cannot independently patch the operating system's CUPS implementation.

Source builds use Xcode Command Line Tools. Tests and installer-package cleanup use Python 3.9 or newer and its standard library. No pip packages are required. Packaging uses Apple's `pkgbuild`, `pkgutil`, `tar`, `lsbom`, and `mkbom`. All build/package steps run without administrator privileges; only installing the finished package needs authorization.

Rendering code and the PPD template are adapted from the MIT-licensed [deli-tspl-cups](https://github.com/hubooy/deli-tspl-cups) source snapshot [fef8445333639655717589dcf02f46e50b5d7e5d](https://github.com/hubooy/deli-tspl-cups/commit/fef8445333639655717589dcf02f46e50b5d7e5d). Source is reviewed and maintained here, rather than fetched during builds or installation. An upstream revision pin records provenance; it does not mean this modified code remains automatically current or vulnerability-free.

GitHub Actions are pinned to full commits verified in their official repositories:

| Action | Release | Pinned commit |
| --- | --- | --- |
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |
| actions/attest-build-provenance | v4.2.2 | `4d101475d8b20a2381f78447822ac1eab6504dd8` |

Dependabot proposes weekly GitHub Actions updates; updates still require review and passing checks. CI has read-only repository access. The release build has only the additional OIDC/attestation permissions needed for build provenance; a separate job creates a draft release with contents-write permission. Pull requests cannot publish a release through these workflows.

Release packages are rebuilt on GitHub-hosted macOS runners, have SHA-256 checksums, and receive GitHub build-provenance attestations. An attestation ties an asset to its workflow and repository revision; it is not Apple Developer ID signing, Apple notarization, or proof that code has no vulnerabilities.
