# Security policy

## Scope

This project processes CUPS raster data and installs a local printer filter and queue. The installer and uninstaller require administrator authorization. The filter itself uses macOS's printing service and system CUPS library.

Relevant concerns include malformed raster input, unintended printer commands, unsafe privileged file operations, compromised release assets or workflows, and disclosure of label or machine data. The project does not require telemetry, an account, or network access to print over USB.

Only the current release is maintained. Security fixes may require upgrading; no response-time commitment is implied.

## Report a vulnerability

If this repository offers **Security → Report a vulnerability**, use that private reporting feature. Otherwise, open a minimal issue asking the maintainer for a private reporting channel. Do not include exploit details, credentials, personal labels, addresses, serial numbers, or unredacted logs in that public request.

For a private report, include the affected version, a concise impact description, reproduction steps using synthetic data, and any proposed fix. Please allow the maintainer an opportunity to investigate before public disclosure.

## Release integrity and limits

Download release assets from this repository's Releases page and compare their hashes with the published `SHA256SUMS.txt` file. A checksum detects different bytes; it does not prove publisher identity or make a compromised release trustworthy.

The initial public installer is unsigned and not notarized by Apple. Its ARM64 filter uses ad-hoc signing. Users who need a stronger verification path should review and build the source, or wait for a Developer ID signed and notarized release. Do not disable Gatekeeper or SIP.

Automated tests, sanitizers, and source review provide evidence for the paths inspected. They are not a guarantee of freedom from vulnerabilities. Sanitizers do not instrument Apple's system libraries. Keep macOS updated to receive system CUPS and platform security fixes.

## Printing data and local storage

The filter does not contact a network service, collect telemetry, or log document text, job titles, or account names. It encodes a job into an anonymous local temporary file before forwarding validated output to CUPS. That file contains label-derived bitmap data while the filter runs. CUPS and macOS also manage their own spool files, job metadata, and logs according to system settings; this project does not promise that the operating system retains no printing data.

Validating a complete job before transmission reduces malformed-input partial output. It cannot make physical USB delivery atomic: disconnection or a backend failure after transmission begins can still interrupt a label.
