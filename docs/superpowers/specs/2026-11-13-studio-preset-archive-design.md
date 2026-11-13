# Studio preset archives in the filament workspace

## Goal

Let a user add the filament presets from a Bambu Studio export directly to the
existing local editor, without manually extracting a ZIP and selecting JSON
files. Preserve accepted work on failure, preserve original settings and import
identity, and keep the existing evidence and inheritance limits visible.

The user has authorized continued implementation and publication to `main`.
This scope is the implementation decision for this iteration; it is not a claim
that the user selected a particular technical design.

## Scope and alternatives

Use a bounded server-side ZIP parser and the existing JSON/session-token API.
This avoids adding a browser ZIP dependency and reuses current workspaces,
review reports and explicit single-parent resolution. Support `.bbsflmt`,
`.bbscfg`, and the ordinary preset `.zip` structures verified against pinned
Bambu Studio source. A mixed printer bundle contributes only its filament
documents and reports the other members.

A saved-project 3MF settings bridge was also investigated. It needs separate
native qualification: generator-version gates and native setting changes make
simple copying insufficient. It is outside this change. Calibration notebooks,
source-evidence editing, portable workspace packages and draft export are also
separate milestones.

## Contracts

`POST /api/profiles/import-archive` accepts `filename` and `content_base64`.
It parses and returns candidates; it neither saves a workspace nor runs Studio.
The existing session-token, origin, JSON-content-type and request-size checks
apply. The whole request is limited to 8 MiB, including base64 overhead.

The parser accepts at most 4 MiB compressed, 4 MiB expanded across all members,
256 archive members, 64 selected filament documents, 2 MiB per JSON member and
2 MiB of accepted document JSON. It never extracts paths or opens local paths
from the archive. Reject unsafe or duplicate member paths, links, encrypted or
unsupported compression, invalid CRCs, malformed structures and invalid JSON.
Inspect manifest consistency and native preset identities before classifying a
member. GUI exports can omit `type`; preserve such originals unchanged.

Each selected document has `filename`, `profile`, and an optional `origin`:

```json
{
  "type": "bambu_preset_archive",
  "archive_name": "example.bbsflmt",
  "archive_sha256": "64 lowercase hexadecimal characters",
  "member_path": "filament/example.json",
  "member_sha256": "64 lowercase hexadecimal characters"
}
```

Archive/member hashes describe original bytes. The existing resolver hash still
describes canonical parsed profile JSON. Neither hash authenticates a publisher
or proves calibration. Origin stays outside the original profile; importing
does not add `source`, `validation`, `type`, or missing parent values. Manifest
account identifiers and networking-library versions do not become authority or
Studio-version claims.

Workspace schema version 1 accepts this optional document field while retaining
the old three-field document form. Review and baseline payloads accept it too;
reports preserve it without changing setting hashes or inherited values.

## Import interaction

A dedicated Studio-export input sits beside JSON import. Both paths prepare a
complete candidate collection and commit once. Successful additions retain the
current target and setup, invalidate the old review, and mark the workspace
dirty. Failed imports leave accepted documents, exact draft text, selection,
setup and any existing review unchanged.

An initial valid pasted profile is adopted before new files are appended. An
invalid standalone pasted draft blocks import with a recovery message and is
retained. In a collection, an unfinished existing draft does not block adding a
parent. Exact original-JSON duplicates are skipped without overwriting an
edited draft; conflicting same-name candidates reject the entire import.

Pending imports cannot apply after a later import, input edit, file removal,
collection clear, or workspace switch. Reuse the existing revision and epoch
guards. Origin remains attached through edits, original restoration, save/open,
baseline comparison, and report download. Show member/asset hashes as import
details and report ignored machine/process documents explicitly.

## Verification and evidence limits

Use source-derived, original synthetic archives; do not vendor third-party
presets. Parser tests cover all three supported layouts, missing parents,
unchanged `nil`/variant data, malformed archives and size/resource bounds. API
tests cover local-session rules, strict base64, side-effect-free failure and
origin persistence across review and app restart. Controller tests cover atomic
append, duplicate rules, incomplete drafts and stale responses. Real Chromium
desktop/mobile workflows cover import, review, edits, save/reopen and rollback.

Run the full repository Python/controller suite, package checks, browser CI and
the existing pinned native CI gate. Report parser/browser/native/physical
evidence separately: these archive fixtures are not a claim that a GUI export
or a physical printer was exercised in this iteration.
