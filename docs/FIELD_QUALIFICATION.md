# Physical-printer field qualification (operator checklist)

**Status:** Not qualified. This checklist is an acceptance protocol; it is not evidence
that any hardware has printed a part. Keep synthetic CLI qualification, Studio
read-back and measured printed parts as three separate claims.

## Scope and ownership

- Test a single exact printer + firmware + nozzle diameter/material + bed
  + feed mode + Studio version + filament SKU/color + profile hash combination.
- A qualified combination does **not** qualify another printer, firmware,
  toolhead, filament variant, temperature or sliced model automatically.
- A human operator must examine the actual machine and remain able to stop it.
  This application does not certify safety. Since v0.15 it can send a verified
  slice over LAN after a single-use review and an explicit bed-clear
  confirmation, and since v0.18 it can pause, resume or (after confirmation)
  stop that print; qualify that path separately from Studio's own send.
- Do not bypass machine interlocks, bed exclusion areas, temperature limits or
  vendor maintenance recommendations in order to pass a test.

## Evidence record (create one copy per run)

| Required field | Captured value |
|---|---|
| Operator, local timestamp and run ID | |
| Printer model, serial suffix (optional), firmware | |
| Bambu Studio exact version and operating system | |
| Machine/process/filament preset identities and SHA-256 | |
| Nozzle size/type, plate and feed path | |
| Filament brand, exact SKU/variant, lot (if known), drying state | |
| CAD job ID, source 3MF SHA-256, dimensions in mm | |
| Generated preparation report status and recorded print-volume fields | |
| Prepared 3MF SHA-256, sliced 3MF SHA-256 and Studio read-back | |
| Actual machine selection and actual plate dimensions | |
| Operator visual confirmation of orientation, adhesion space and supports | |
| First-layer observation, final machine status and operator result | |
| Caliper model, measurement points, measured values and tolerance criteria | |
| Photo references and non-sensitive logs | |
| Decision: pass / fail / blocked; explanation and follow-up | |

Keep secrets, full serial numbers, LAN credentials and private camera footage
out of public issues and CI artifacts.

## Gate A — safe non-print preparation

1. Record installed Studio version, printer presets and current physical hardware
   separately. Confirm their names and properties match; do not infer from a
   preset label that hardware is installed.
2. Start with a noncritical, small test model within the known bed dimensions
   and with an explicit positive height margin. Verify generated STL/STEP/3MF
   identities, model size, print-volume review and report hashes.
3. Test a deliberately oversized model and a known unsupported bed exclusion
   configuration. Both must refuse preparation, not merely show a warning.
4. In the native Studio UI inspect the full prepared model: orientation,
   travel/exclusion zones, brim/skirt/support/purge area, plate, toolhead,
   temperature, flow and toolpath. Compare critical values against the
   operator-approved native Studio settings.
5. Verify generated G-code is present and that read-back refers to the same
   model and presets. A successful CLI exit alone is insufficient.
6. On failure or ambiguous inputs, mark the run **blocked** and retain the
   files. Never substitute synthetic CI success for hardware evidence.

## Gate B — controlled physical print

1. Use either Studio's normal reviewed print workflow or the application's LAN
   send (review → bed-clear confirmation → start), and record which one was
   used. Confirm the selected machine and plate on the actual device; keep the
   printer's own stop control within reach even when the app can stop the job.
2. Follow the vendor's ventilation, materials, fire and supervision guidance.
   Verify appropriate bed adhesion and that the area is unobstructed.
3. Observe the first layer and record adhesion, collisions, unexpected travel,
   filament delivery and any alarm. Stop using the printer's standard controls
   when unsafe.
4. Record the final machine-reported result and the independent operator
   assessment. A successful job state does not prove dimensional accuracy.
5. Measure X/Y/Z and relevant inner-fit features after cooling using a
   calibrated instrument. Define dimensional tolerances before the print,
   record numeric deviations and repeatability on at least three samples.
   The job's outcome card can store up to five X/Y/Z samples and the declared
   tolerance (v0.24); it reports per-axis mean/maximum deviation and spread
   against the CAD size as **user-measured** evidence. That record supports,
   but does not replace, the full evidence table above.
6. Save original files, exact software and printer versions, photos,
   measurements and disposition together. Retest after relevant changes.

## Gate C — release decision

A combination is accepted only when all evidence above is present, no
unresolved safety or read-back issue exists, and the measured samples meet
predeclared tolerances. If samples are missing or the user merely reports
success, label the state **user-reported**, not **hardware-verified**.
Use **blocked** for missing identity/setting/geometry evidence and **failed**
for observed incorrect prints. The release must not claim a model/printer
combination was physically qualified without an actual completed record.

The existing automated CI and synthetic native tests are regression evidence
only. This protocol intentionally requires a manual, real-device run; CI
cannot fulfill it by mocking a printer.
