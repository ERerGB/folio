# Optional library organization profile

Use this mode only when the user asks to organize a reader library. Folio's booklet object and edition ledger remain independent of a user's shelving preferences. Store each user's `library-profile.json` beside that user's private booklet collection, not inside this skill or a public repository.

The profile is declarative. `scripts/library_profile.py` validates it and proposes a relative path; it does not scan, move, upload, delete, or infer reading progress. Before a device change, inventory the current library, inspect the device's actual file-management route, and verify the result there. A delivery record describes the original transfer; a separate catalog records the current location after a move. Do not rewrite historical delivery evidence as if the upload happened at the new location.

## Version 1 contract

The JSON object has five top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`. |
| `profile_id` | Stable lowercase hyphenated identifier. |
| `device` | `name` and safe relative `library_root`; never store a transient LAN address or credentials. |
| `organization` | `primary_axis: reading_state`, `default_on_delivery: inbox` or `unknown`, `state_folders`, `index_file`, `facets`, optional `topics`. |
| `safeguards` | `extension_policies`, `protected_directories`, and `opened_file_move`. |

Canonical state IDs are `inbox`, `reading`, `completed`, and `unknown`. Every ID appears in `state_folders`; a `null` value means catalog-only, with no physical folder. `inbox` means newly received, **not** unread. `completed` or `reading` require `--status-evidence user-confirmed` or `--status-evidence reader-progress` for a placement proposal; a folder name or BOOXDrop file listing alone does not prove progress. `facets` are catalog columns such as `topic` and `source`; multiple facets do not create duplicate device copies. `topics` optionally supplies user-editable labels for the `topic` facet.

`extension_policies` maps case-insensitive suffixes to `managed` or `observe_only`. An unlisted suffix requires manual review. `managed` only makes a file eligible for a placement proposal; it does not authorize a move. `protected_directories` names immediate child folders under `library_root`; no state folder may reuse a protected name, compared case-insensitively. This is a profile consistency check, not an inventory of the real device or proof that its paths are safe. `opened_file_move` is `manual_review` or `index_only`, because changing a read file's path may affect its reading data. The planner defaults `--reading-data` to `unknown`, which yields manual review. Use `none` only for a just-delivered file or after checking that the book has no reading data; use `present` when progress, bookmarks, or annotations exist.

A complete synthetic example (adapt it to the verified reader; it contains no
personal catalog, device address or credentials):

```json
{
  "schema_version": 1,
  "profile_id": "example-reader",
  "device": {"name": "Example reader", "library_root": "Books"},
  "organization": {
    "primary_axis": "reading_state",
    "default_on_delivery": "inbox",
    "state_folders": {"inbox": "Inbox", "reading": null, "completed": "Completed", "unknown": null},
    "index_file": "catalog.json",
    "facets": ["topic", "source"]
  },
  "safeguards": {
    "extension_policies": {".epub": "managed", ".note": "observe_only"},
    "protected_directories": ["Vendor"],
    "opened_file_move": "index_only"
  }
}
```

The command returns a proposal only. It cannot detect collisions, symlinks or
reading data on a real reader; inspect those separately before any authorized move.

Validate and preview without device mutation:

```bash
python3 scripts/library_profile.py /path/to/private/library-profile.json
python3 scripts/library_profile.py /path/to/private/library-profile.json --name 'Article-e001.epub' --reading-data none
python3 scripts/library_profile.py /path/to/private/library-profile.json --name 'Article-e001.epub' --state completed --status-evidence user-confirmed --reading-data present
```

When the user requests actual organization, compare the proposal against a fresh device inventory. Preserve existing reading data, verify any move in the device's own interface, and update the private catalog's current path. BOOXDrop can prove a device file is visible at a location; it cannot by itself prove the native reader has indexed or opened it. If a delivery helper only searches the library root, a nested placement needs a separate verification path; do not treat a root-list miss as deletion.
