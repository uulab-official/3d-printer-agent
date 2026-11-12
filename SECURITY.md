# Security reporting

## Scope

3D Printer Agent is an early local application. Its current command starts a loopback HTTP server; it is not a hosted, multi-user service. Relevant findings include unauthorized local requests, arbitrary code or file access, credential disclosure, and accepting untrusted generated output as a verified result.

There is no published long-term support schedule. Include the affected commit or version in a report. The maintainer will assess the issue against the current code and document any fix; this document does not promise a response deadline.

## Report a potential vulnerability

Check this repository's [Security page](https://github.com/uulab-official/3d-printer-agent/security). **If GitHub displays “Report a vulnerability,”** use that private reporting action. This document does not assume private vulnerability reporting has been enabled.

If a private reporting action is unavailable, open a minimal issue asking the maintainer to provide a private reporting channel. State the affected version and broad component only. Keep exploit details, sensitive logs, and proof-of-concept payloads out of that public issue until a suitable channel is agreed.

A useful private report includes the affected commit, operating system, relevant component versions, minimal reproduction steps, expected and observed behavior, and the access needed to reproduce the issue. Use synthetic credentials and test data. Never include real API keys, printer access codes, account tokens, or someone else's files.

## Reproduction boundaries

Reproduce findings only in environments you own or are authorized to test. The normal test suite works without a physical printer or live LLM credentials. A test that needs native software or hardware should state that requirement and the actions it would perform before running them.

General bugs, installation problems, and unsupported features can use the normal bug report template. A CAD-valid model or a successfully produced slice is not evidence of physical-print suitability; the project records those stages separately.
