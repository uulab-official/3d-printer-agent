# Read-only Bambu LAN status (v0.9.0) — design

Date: 2026-11-16.

## Goal

First step of the "real Bambu printer integration" milestone: identify a printer on the
local network, establish a separately reported connection state, and read the printer's
own reported print status. No control, no persistence of secrets, no claim of physical
results.

## Interfaces used

- SSDP: printers announce `NOTIFY` with `NT: urn:bambulab-com:device:3dprinter:1`,
  `USN: <serial>`, `Location: <ip>` and `DevModel/DevName/DevConnect/DevBind/DevVersion
  .bambu.com` headers on UDP 2021; an `M-SEARCH` is sent to 239.255.255.250:1990.
- MQTT 3.1.1 over TLS on 8883, username `bblp`, password = LAN access code. Subscribe to
  `device/<serial>/report`; publish `pushall` and `get_version` to
  `device/<serial>/request`.

These are community-documented, not a vendor-supported public API. Field names are read
defensively and missing values stay unknown.

## Decisions

| Decision | Reason |
|---|---|
| Stdlib MQTT codec instead of a new dependency | Only CONNECT/SUBSCRIBE/QoS0 PUBLISH/DISCONNECT are needed; keeps the wheel and installed qualification unchanged and the request surface auditable. |
| Two fixed request payloads | The module cannot construct a print/motion/temperature/file command. Tests assert the full set. |
| Private/link-local/loopback IP literals only | The loopback app must not become a general network client. Rejected before any socket use. |
| TLS without issuer verification + session pin | Device certificates are not in common trust stores. The fingerprint is shown; once a report is received the browser pins it per host/serial and the server refuses to send the access code to a different certificate. |
| No stored printers or codes in this release | Avoids new SQLite stores, backup and compatibility migrations; access codes stay in the page input only. A saved printer list is follow-up work. |
| Validation errors on `/api/printers/*` omit inputs | FastAPI's default 422 echoes submitted values; the access code must never be returned. |
| One reader, 5 s per printer | Avoid flooding printers (some models are sensitive to frequent `pushall`). |
| Distinct connection states | `unreachable`, `tls_failed`, `certificate_changed`, `access_rejected`, `subscribe_rejected`, `no_report`, `protocol_error`, `reporting` are separate facts. |

## Out of scope

Starting/stopping prints, uploading files, camera, cloud accounts, persistent printer
registry, continuous monitoring, linking a report to a stored job, and failure
classification. Live qualification on a physical printer is recorded separately.
