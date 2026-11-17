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

## Printer LAN status boundary (v0.9+)

The printer status view reads a Bambu printer's LAN-mode report. Its intended security properties are:

- The status module (`printer_lan.py`) can publish only fixed `pushall` and `get_version` requests; no print, motion, temperature or file command is constructible there. Starting a print is confined to `printer_send.py` (below).
- Targets are private, link-local or loopback IP literals; hostnames and public addresses are rejected before any network use. One read runs at a time, at most once per printer every 5 seconds.
- The device certificate issuer is **not** verified, because printer certificates are not in common trust stores. The fingerprint is shown and pinned per host/serial for the page session; a different certificate stops the read before the access code is sent. A first connection on an untrusted network can therefore still reach an impersonating device.
- Access codes are used for one read and are never stored, logged or returned, including in request-validation errors.

## Printer send boundary (v0.15+)

Sending a job starts a physical machine, so `printer_send.py` is deliberately narrow:

- The only command body it can build is `project_file` for a file it uploaded. The file must be the job's own verified sliced 3MF (byte receipt checked on read) with exactly one plate of G-code; nothing typed by a person or returned by an LLM becomes a command, file name or path.
- Two steps: a review reads the printer and returns a single-use token valid for 3 minutes, bound to the job, file SHA-256, host, serial, device-certificate fingerprint and the chosen filament slots. The start request must carry that token, the access code again and `bed_clear_confirmed: true`. A token is consumed even if the start fails, so one review starts at most one print.
- The start re-checks the file hash, requires the same MQTT certificate fingerprint, and requires an idle/finished printer both before the upload and again before the command. Only one send runs at a time.
- The FTPS certificate fingerprint is recorded and compared with the MQTT one, but not enforced, because that equality is not yet observed on real hardware.
- Results keep the stages apart (ready, uploaded, command sent, printer reported start). The job record keeps these stages and the target, never the access code.
- `PPA_PRINTER_FTPS_PORT` (1024–65535) exists only to run the synthetic printer locally; real printers use 990.
- After a print runs, `POST /api/printers/print/control` can send exactly one of `pause`, `resume` or `stop`, built by `control_command`. It requires a previously pinned certificate fingerprint (the read is refused without one, and a different certificate stops it before the code is sent), a reported printer state in which that command applies, and `stop_confirmed: true` for a stop. An unknown `job_id` is refused before any network use; a sent command is recorded on the job without the access code.

Reports that break one of these properties are in scope.
