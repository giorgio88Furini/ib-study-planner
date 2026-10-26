# Security policy

## Supported versions

Security fixes are intended for the current `1.x` release line. Users should use the latest available source revision and a supported Python version (3.10 or newer).

## Reporting a vulnerability

Please do not publish sensitive exploit details in a public issue. Contact the repository maintainers through a private security advisory or another private channel available in the hosting platform. Include the affected version, impact, and a minimal reproduction where safe. Do not include real student records or other personal data.

## Scope and data handling

The package reads the CSV path explicitly provided by the user and writes output only when `--output` is specified. It performs scheduling locally, has no network calls, and does not retain topic data beyond the process. Input is treated as data, not executable code. Do not provide confidential or personally identifying information as topic labels.
