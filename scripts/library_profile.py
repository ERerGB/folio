#!/usr/bin/env python3
"""Validate a private Folio library profile and resolve a proposed file placement.

This command is read-only. It never changes a reader, a catalog, or a delivery log.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


STATES = ("inbox", "reading", "completed", "unknown")
POLICIES = ("managed", "observe_only")


@dataclass(frozen=True)
class LibraryProfile:
    profile_id: str
    device_name: str
    library_root: str
    state_folders: dict[str, str | None]
    default_on_delivery: str
    index_file: str
    facets: tuple[str, ...]
    topics: tuple[dict[str, str], ...]
    extension_policies: dict[str, str]
    protected_directories: tuple[str, ...]
    opened_file_move: str


def _object(value: object, required: set[str], optional: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing or unknown:
        raise ValueError(f"{label}: missing={sorted(missing)}, unknown={sorted(unknown)}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be nonempty trimmed text")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"{label} contains a control character")
    return value


def _relative(value: object, label: str, *, single: bool = False) -> str:
    path = _text(value, label)
    if "\\" in path or path.startswith("/") or any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError(f"{label} must be a safe relative path")
    if single and "/" in path:
        raise ValueError(f"{label} must be one folder or file name")
    return path


def _names(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    names = tuple(_relative(item, f"{label} item", single=True) for item in value)
    if len(set(names)) != len(names):
        raise ValueError(f"{label} contains duplicate names")
    return names


def load_profile(path: Path) -> LibraryProfile:
    raw = _object(json.loads(path.read_text(encoding="utf-8")),
                  {"schema_version", "profile_id", "device", "organization", "safeguards"}, set(), "profile")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    profile_id = _text(raw["profile_id"], "profile_id")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", profile_id):
        raise ValueError("profile_id must be lowercase hyphenated text")

    device = _object(raw["device"], {"name", "library_root"}, set(), "device")
    organization = _object(raw["organization"],
                           {"primary_axis", "default_on_delivery", "state_folders", "index_file", "facets"},
                           {"topics"}, "organization")
    if organization["primary_axis"] != "reading_state":
        raise ValueError("primary_axis currently supports only reading_state")
    folders = _object(organization["state_folders"], set(STATES), set(), "state_folders")
    state_folders = {state: None if folders[state] is None else
                     _relative(folders[state], f"state_folders.{state}", single=True) for state in STATES}
    assigned = [folder.casefold() for folder in state_folders.values() if folder]
    if len(assigned) != len(set(assigned)):
        raise ValueError("state folders must be distinct")
    default = organization["default_on_delivery"]
    if default not in ("inbox", "unknown"):
        raise ValueError("default_on_delivery must be inbox or unknown; delivery does not prove unread")
    facets = _names(organization["facets"], "facets")
    topics_raw = organization.get("topics", [])
    if not isinstance(topics_raw, list):
        raise ValueError("topics must be an array")
    topics = []
    for item in topics_raw:
        topic = _object(item, {"id", "label"}, set(), "topic")
        topic_id = _text(topic["id"], "topic.id")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", topic_id):
            raise ValueError("topic.id must be lowercase hyphenated text")
        topics.append({"id": topic_id, "label": _text(topic["label"], "topic.label")})
    if topics and "topic" not in facets:
        raise ValueError("topics require the topic facet")
    if len({item["id"] for item in topics}) != len(topics):
        raise ValueError("topic ids must be unique")

    safeguards = _object(raw["safeguards"],
                         {"extension_policies", "protected_directories", "opened_file_move"}, set(), "safeguards")
    policies_raw = safeguards["extension_policies"]
    if not isinstance(policies_raw, dict):
        raise ValueError("extension_policies must be an object")
    policies: dict[str, str] = {}
    for extension, policy in policies_raw.items():
        if not isinstance(extension, str) or not re.fullmatch(r"\.[A-Za-z0-9]+", extension):
            raise ValueError("extension policy keys must look like .epub")
        if policy not in POLICIES:
            raise ValueError(f"unsupported policy for {extension}")
        normalized = extension.casefold()
        if normalized in policies:
            raise ValueError("duplicate extension policy")
        policies[normalized] = policy
    protected = _names(safeguards["protected_directories"], "protected_directories")
    if {name.casefold() for name in protected} & set(assigned):
        raise ValueError("a protected directory cannot also be a state folder")
    opened_policy = safeguards["opened_file_move"]
    if opened_policy not in ("manual_review", "index_only"):
        raise ValueError("opened_file_move must be manual_review or index_only")

    return LibraryProfile(
        profile_id=profile_id,
        device_name=_text(device["name"], "device.name"),
        library_root=_relative(device["library_root"], "device.library_root"),
        state_folders=state_folders,
        default_on_delivery=default,
        index_file=_relative(organization["index_file"], "organization.index_file"),
        facets=facets,
        topics=tuple(topics),
        extension_policies=policies,
        protected_directories=protected,
        opened_file_move=opened_policy,
    )


def resolve(profile: LibraryProfile, filename: str, state: str, reading_data: str,
            status_evidence: str | None = None) -> dict[str, str]:
    name = _relative(filename, "filename", single=True)
    if status_evidence not in (None, "user-confirmed", "reader-progress"):
        raise ValueError("status_evidence must be user-confirmed or reader-progress")
    if reading_data not in ("unknown", "none", "present"):
        raise ValueError("reading_data must be unknown, none, or present")
    if state not in STATES:
        raise ValueError(f"state must be one of {', '.join(STATES)}")
    policy = profile.extension_policies.get(PurePosixPath(name).suffix.casefold(), "manual_review")
    if policy == "observe_only":
        return {"decision": "observe_only", "reason": "extension policy"}
    if policy == "manual_review":
        return {"decision": "manual_review", "reason": "file extension has no managed policy"}
    if state in ("reading", "completed") and status_evidence is None:
        return {"decision": "manual_review", "reason": "reading state needs user or reader evidence"}
    if reading_data == "unknown":
        return {"decision": "manual_review", "reason": "reading data has not been checked"}
    if reading_data == "present":
        return {"decision": profile.opened_file_move, "reason": "opened or annotated item needs reading-data review"}
    if reading_data != "none":
        raise ValueError("reading_data must be unknown, none, or present")
    folder = profile.state_folders[state]
    if folder is None:
        return {"decision": "index_only", "reason": "state has no physical folder"}
    return {"decision": "proposed_path", "path": str(PurePosixPath(profile.library_root, folder, name))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--name", help="Book filename for a read-only placement proposal")
    parser.add_argument("--state", choices=STATES)
    parser.add_argument("--status-evidence", choices=("user-confirmed", "reader-progress"))
    parser.add_argument("--reading-data", choices=("unknown", "none", "present"), default="unknown",
                        help="Use none only for a new delivery or a checked book with no reading data")
    args = parser.parse_args()
    try:
        profile = load_profile(args.profile)
        if args.name:
            result = resolve(profile, args.name, args.state or profile.default_on_delivery,
                             args.reading_data, args.status_evidence)
        else:
            result = {"result": "valid", "profile_id": profile.profile_id,
                      "device": profile.device_name, "states": list(profile.state_folders), "facets": list(profile.facets)}
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
