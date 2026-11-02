# Contributing

Kollin Napier maintains this project. Small, reproducible reports and focused pull requests are welcome.

## Report a printing problem

Include the printer model, macOS version, connection type, selected paper dimensions, and the steps needed to reproduce the problem. Distinguish an automated test result from a result observed on paper.

Use a synthetic label containing ordinary text and shapes. Do not upload real shipping labels, addresses, order numbers, printer serial numbers, complete USB device URIs, access tokens, or unredacted CUPS logs. Redact screenshots before posting them. A report does not need a Mac serial number or hardware UUID.

If the issue may be a vulnerability, follow [SECURITY.md](SECURITY.md) instead of posting exploit details publicly.

## Develop and test

On an Apple silicon Mac with Xcode Command Line Tools and Python 3.9 or later:

```sh
make build
make test
make test-sanitize
make package
```

Keep generated files in the ignored build or distribution directories. Do not commit compiled executables, installer packages, machine logs, or personal test data. Add regression tests for behavior changes. Tests must run without a printer, administrator privileges, network access, or third-party Python packages.

Keep changes to the driver, PPD, privileged installer, and release workflow separately understandable. Avoid changing printer firmware settings unless the behavior is documented and tested. Preserve the working default SP420 command sequence and explain any changes to it.

## Pull requests

Describe the concrete problem, the resulting behavior, and the checks run. State whether physical printing was tested and on which model and macOS version. Do not describe a build target or a CI runner as a physical compatibility test.

Contributions are provided under the repository's [MIT license](LICENSE). Preserve existing copyright and attribution notices. Report security or licensing concerns before importing additional code or dependencies.
