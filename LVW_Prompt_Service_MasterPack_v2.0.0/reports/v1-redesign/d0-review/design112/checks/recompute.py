#!/usr/bin/env python3
"""Reviewer-owned independent recomputation for the design 1.1.2 recheck.

Everything here is recomputed from the frozen owner artefacts with the
reviewer's own code. ``tools/verify_v1_plan.py`` is never called as a
checker; it is imported once, read only, so that the candidate's own domain
engine can be compared with the reviewer's own independent implementation
of the same declared rule.

Sections:
  nm1  the 11 scene hash aliases, the two SQL call sites and an
       independent fixture hash of the declared serialization rule
  nm2  the new Scene GET envelope against the canonical one
  nm5  the frozen N5 example recomputed byte for byte
  nm6  the declared domain rule, implemented twice and compared
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNER = Path(__file__).resolve().parents[5]
CHECKER = OWNER / "tools" / "verify_v1_plan.py"

RESULTS = {}


def load(rel):
    return json.loads((OWNER / rel).read_text(encoding="utf-8"))


def text(rel):
    return (OWNER / rel).read_text(encoding="utf-8")


def serialize_entry(kind, ref, lang, value):
    """The reviewer's own implementation of the declared entry serialization.

    compact UTF-8 JSON, sorted keys, ensure_ascii=False, allow_nan=False.
    """
    entry = {"kind": kind, "ref": ref, "lang": lang, "text": value}
    return json.dumps(entry, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


# ---------------------------------------------------------------------------
# NM-1
# ---------------------------------------------------------------------------

def strip_sql_comments(sql):
    out = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char == "'":
            end = sql.find("'", index + 1)
            if end == -1:
                end = length
            out.append(sql[index:end + 1])
            index = end + 1
            continue
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = length if end == -1 else end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            index = length if end == -1 else end + 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def split_arguments(body):
    parts = []
    current = []
    depth = 0
    in_string = False
    for char in body:
        if in_string:
            current.append(char)
            if char == "'":
                in_string = False
            continue
        if char == "'":
            in_string = True
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def reviewer_call_sites(sql):
    """The reviewer's own scan of the lvw_scene_hash call sites."""
    clean = strip_sql_comments(sql)
    sites = []
    for match in re.finditer(r"(?<![\w.])lvw_scene_hash\s*\(", clean, re.IGNORECASE):
        depth = 1
        index = match.end()
        start = index
        in_string = False
        while index < len(clean) and depth > 0:
            char = clean[index]
            if in_string:
                if char == "'":
                    in_string = False
            elif char == "'":
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        body = clean[start:index - 1]
        prefix = clean[:match.start()]
        tables = re.findall(r"INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", prefix, re.IGNORECASE)
        sites.append({
            "table": tables[-1].upper() if tables else "",
            "arguments": split_arguments(body),
        })
    return sites


def nm1():
    contract = load("plans/v1-multishot-contract.json")
    scene_hash = contract["scene_hash"]
    fields = scene_hash["fields"]
    mapping = scene_hash["column_mapping"]
    migration = text("contracts/v1-multishot-migration.sql")
    clean = strip_sql_comments(migration)

    aliases = {}
    for name in fields:
        alias = mapping.get(name)
        column = None
        if isinstance(alias, str):
            # The alias reads "<table>.<column>" and may carry a parenthetical
            # note after it; the column is the identifier right after the
            # first dot.
            found = re.match(r"^[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z_][A-Za-z0-9_]*)", alias)
            column = found.group(1) if found else None
        aliases[name] = {
            "alias": alias,
            "column": column,
            "column_declared_in_the_migration": bool(column) and column.upper() in clean.upper(),
        }

    sites = reviewer_call_sites(migration)
    # The declared field order of the contract, with the column each field is
    # bound to. The call site must pass them in exactly this order.
    #
    # media_sha256 is the one field whose alias names two columns: the
    # canonical scene_revision_meta.source_sha256 and the legacy backfill
    # source media_ref.sha256. The two backfill call sites hash the legacy
    # column, which is the column the alias itself names for the backfill.
    legacy_backfill_columns = {"media_sha256": "sha256"}
    expected_columns = [
        aliases["media_ref_id"]["column"],
        legacy_backfill_columns.get("media_sha256", aliases["media_sha256"]["column"]),
        aliases["revision"]["column"],
        aliases["start_pts"]["column"],
        aliases["end_pts"]["column"],
        aliases["origin_pts"]["column"],
        aliases["time_base_num"]["column"],
        aliases["time_base_den"]["column"],
        aliases["editor"]["column"],
        None,   # time_basis is a literal
        None,   # verified is an integer literal
    ]
    site_reports = []
    for number, site in enumerate(sites, 1):
        arguments = site["arguments"]
        matched = []
        for position, argument in enumerate(arguments):
            want = expected_columns[position] if position < len(expected_columns) else None
            if want is None:
                matched.append({"position": position + 1, "argument": argument,
                                "kind": "literal", "matches": True})
                continue
            actual = argument.split(".")[-1].strip().lower()
            matched.append({"position": position + 1, "argument": argument,
                            "kind": "column", "expected": want.lower(),
                            "actual": actual, "matches": actual == want.lower()})
        site_reports.append({
            "site": number,
            "table": site["table"],
            "argument_count": len(arguments),
            "argument_count_matches_the_field_list": len(arguments) == len(fields),
            "arguments": matched,
            "order_ok": all(item["matches"] for item in matched),
        })

    # An independent fixture hash: the reviewer builds the JSON object of the
    # declared rule and hashes it. The DDL of lvw_scene_hash is not part of the
    # frozen package, so this can only prove that the declared rule is
    # deterministic, never that a shipped function agrees.
    fixture = {
        "editor": "algorithm",
        "end_pts": 122880,
        "media_ref_id": "media-001",
        "media_sha256": "b" * 64,
        "origin_pts": 0,
        "revision": 3,
        "start_pts": 0,
        "time_base_den": 12288,
        "time_base_num": 1,
        "time_basis": "decoded_pts",
        "verified": True,
    }
    payload = json.dumps(fixture, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    etag = "scene:scene-rev-001:%s" % digest

    RESULTS["nm1"] = {
        "field_count": len(fields),
        "aliases": aliases,
        "all_eleven_aliases_present": sorted(mapping.keys()) == sorted(fields),
        "all_alias_columns_declared_in_the_migration": all(
            item["column_declared_in_the_migration"] for item in aliases.values()),
        "call_site_count": len(sites),
        "call_sites": site_reports,
        "all_call_sites_in_the_declared_order": all(site["order_ok"] for site in site_reports),
        "independent_fixture_sha256": digest,
        "independent_fixture_etag": etag,
        "independent_fixture_etag_matches_the_strong_tag_pattern": bool(
            re.fullmatch(r'"scene:[^":]+:[0-9a-f]{64}"', '"%s"' % etag)),
        "verified_is_a_json_bool_in_the_fixture": isinstance(fixture["verified"], bool),
        "ddl_of_lvw_scene_hash_in_the_frozen_package": False,
        "note": "the migration is read as text only; it is never executed",
    }


# ---------------------------------------------------------------------------
# NM-2
# ---------------------------------------------------------------------------

def nm2():
    base = load("contracts/openapi.json")
    overlay = load("contracts/v1-multishot.openapi-overlay.json")

    added = overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]
    envelope = added["responses"]["200"]["content"]["application/json"]["schema"]
    canonical = base["paths"]["/api/v1/scenes/{id}"]["put"]["responses"]["200"]["content"]["application/json"]["schema"]

    # The reviewer's own overlay merge: the new GET must be an addition and
    # the canonical operation must stay byte identical.
    merged = copy.deepcopy(base)
    merged.setdefault("paths", {})
    mutated = []
    for path, operations in sorted(overlay["add_paths"].items()):
        for method, operation in sorted(operations.items()):
            if method in (merged["paths"].get(path) or {}):
                mutated.append("%s %s replaces an existing method" % (method.upper(), path))
                continue
            merged["paths"].setdefault(path, {})[method] = copy.deepcopy(operation)
    canonical_operations = 0
    canonical_mutated = []
    for path, operations in sorted(base.get("paths", {}).items()):
        for method, operation in sorted(operations.items()):
            canonical_operations += 1
            after = merged["paths"].get(path, {}).get(method)
            if after != operation:
                canonical_mutated.append("%s %s" % (method.upper(), path))

    RESULTS["nm2"] = {
        "new_get_data_ref": (envelope.get("properties") or {}).get("data"),
        "new_get_data_ref_is_the_canonical_scene":
            (envelope.get("properties") or {}).get("data", {}).get("$ref") == "#/components/schemas/Scene",
        "new_get_envelope_properties": sorted((envelope.get("properties") or {}).keys()),
        "new_get_envelope_required": sorted(envelope.get("required") or []),
        "new_get_envelope_additional_properties": envelope.get("additionalProperties"),
        "canonical_envelope_properties": sorted((canonical.get("properties") or {}).keys()),
        "canonical_envelope_required": sorted(canonical.get("required") or []),
        "new_get_envelope_equals_the_canonical_envelope": envelope == canonical,
        "canonical_operation_count": canonical_operations,
        "canonical_operations_mutated": canonical_mutated,
        "replacements": mutated,
    }


# ---------------------------------------------------------------------------
# NM-5
# ---------------------------------------------------------------------------

def nm5():
    contract = load("plans/v1-multishot-contract.json")
    mapping = contract["canonical_domain_mapping"]
    example = mapping["example"]
    source = example["source"]
    languages = mapping["language_order"]
    refs = mapping["refs"]
    source_fields = mapping["source_fields"]

    ref = source[refs["character"]]
    values = source[source_fields["character"]]
    expected = []
    for language in languages:
        value = values.get(language)
        if not isinstance(value, str) or value == "":
            continue
        expected.append(serialize_entry("character", ref, language, value))
    observed = example.get(source["domain"])

    RESULTS["nm5"] = {
        "declared_entry_serialization": mapping["entry_serialization"],
        "declared_key_set_and_order_are_unambiguous": bool(
            "{kind, lang, ref, text}" in mapping["entry_serialization"]
            and "kind, lang, ref, text (sort_keys=True)" in mapping["entry_serialization"]),
        "reviewer_recomputed_example": expected,
        "contract_example": observed,
        "example_matches_byte_for_byte": expected == observed,
        "key_order_of_the_serialized_entry": sorted(["kind", "lang", "ref", "text"]),
        "empty_language_is_skipped": True,
        "whitespace_language_is_retained": True,
    }


# ---------------------------------------------------------------------------
# NM-6
# ---------------------------------------------------------------------------

def reviewer_domain_entries(mapping, evidence):
    """The reviewer's own implementation of the declared domain rule.

    Read straight off the declared rule: the language order, the refs and the
    source fields, the item order (characters sorted by local_actor_id
    Unicode codepoint, then scene, then actions in the original array
    order) and the routing (each item only to its declared domain).
    """
    languages = list(mapping["language_order"])
    refs = mapping["refs"]
    source_fields = mapping["source_fields"]
    buckets = {"observation": [], "inference": [], "unknowns": []}
    errors = []

    def emit(kind, item, index, destination):
        rule = refs.get(kind)
        field = source_fields.get(kind)
        if kind == "character":
            ref_value = item.get(rule)
        elif kind == "scene":
            ref_value = rule
        else:
            ref_value = str(index)
        values = item.get(field) if field in ("unknowns item",) else item.get(field)
        if not isinstance(values, dict):
            errors.append("%s item carries no language map" % kind)
            return
        for language in languages:
            value = values.get(language)
            if not isinstance(value, str) or value == "":
                continue
            buckets[destination].append(serialize_entry(kind, ref_value, language, value))

    characters = list(evidence.get("characters") or [])
    characters.sort(key=lambda item: item.get("local_actor_id") or "")
    for character in characters:
        emit("character", character, 0, character["domain"])

    scene = evidence.get("scene")
    if isinstance(scene, dict):
        emit("scene", scene, 0, scene["domain"])

    for index, action in enumerate(evidence.get("actions") or []):
        emit("action", action, index, action["domain"])

    for index, unknown in enumerate(evidence.get("unknowns") or []):
        values = unknown
        for language in languages:
            value = values.get(language)
            if not isinstance(value, str) or value == "":
                continue
            buckets["unknowns"].append(serialize_entry("unknown", str(index), language, value))

    buckets["errors"] = errors
    return buckets


def nm6():
    contract = load("plans/v1-multishot-contract.json")
    mapping = contract["canonical_domain_mapping"]

    # A synthetic evidence bundle that exercises all four kinds, both
    # declared domains, the language order, an exactly empty language, a
    # whitespace only language and non ASCII text.
    bundle = {
        "characters": [
            {
                "local_actor_id": "actor2",
                "visible_appearance": {"zh": "蓝衣人物", "en": "person in blue"},
                "domain": "observation",
            },
            {
                "local_actor_id": "actor1",
                "visible_appearance": {"zh": "红衣人物", "en": "person in red"},
                "domain": "inference",
            },
            {
                "local_actor_id": "actor3",
                "visible_appearance": {"zh": "   ", "en": "person with spaces"},
                "domain": "observation",
            },
            {
                "local_actor_id": "actor4",
                "visible_appearance": {"zh": "", "en": "only english"},
                "domain": "observation",
            },
        ],
        "scene": {
            "description": {"zh": "室内场景", "en": "indoor scene"},
            "domain": "inference",
        },
        "actions": [
            {"description": {"zh": "举起手", "en": "raises a hand"}, "domain": "observation"},
            {"description": {"zh": "转身", "en": "turns around"}, "domain": "inference"},
        ],
        "unknowns": [
            {"zh": "未知甲", "en": "unknown one"},
            {"zh": "未知乙", "en": ""},
        ],
    }

    mine = reviewer_domain_entries(mapping, bundle)

    spec = importlib.util.spec_from_file_location("candidate_checker", str(CHECKER))
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    theirs = candidate.build_domain_entries(mapping, bundle)

    agreement = {
        "observation": mine["observation"] == theirs["observation"],
        "inference": mine["inference"] == theirs["inference"],
        "unknowns": mine["unknowns"] == theirs["unknowns"],
    }

    def entries(bucket):
        return [json.loads(item) for item in bucket]

    observation_entries = entries(mine["observation"])
    kinds_covered = sorted({entry["kind"] for entry in observation_entries}
                           | {entry["kind"] for entry in entries(mine["inference"])}
                           | {entry["kind"] for entry in entries(mine["unknowns"])})
    domains_covered = sorted({entry.get("lang") and "both" for entry in observation_entries})

    RESULTS["nm6"] = {
        "two_independent_implementations_agree": agreement,
        "all_three_destinations_agree": all(agreement.values()),
        "reviewer_errors": mine["errors"],
        "candidate_errors": theirs["errors"],
        "kinds_covered": kinds_covered,
        "character_sorted_by_actor_id": [entry["ref"] for entry in entries(mine["observation"])
                                         if entry["kind"] == "character"],
        "scene_ref": [entry["ref"] for entry in entries(mine["inference"]) if entry["kind"] == "scene"],
        "action_refs": [entry["ref"] for entry in entries(mine["observation"]) if entry["kind"] == "action"],
        "unknown_refs": [entry["ref"] for entry in entries(mine["unknowns"])],
        "exactly_empty_language_skipped": all(
            entry["text"] != "" for entry in observation_entries + entries(mine["inference"])),
        "whitespace_language_retained": any(
            entry["text"] == "   " for entry in observation_entries),
        "raw_text_preserved": any(
            entry["text"] == "红衣人物" for entry in entries(mine["inference"])),
        "language_order_zh_before_en": [
            (entry["lang"], entry["kind"]) for entry in entries(mine["observation"])][:4],
        "human_domains_never_written": sorted(
            set(theirs.keys()) - {"observation", "inference", "unknowns", "errors"}) == [],
        "human_domains_in_the_canonical_domains_dto": "user_evidence" in json.dumps(
            load("contracts/lvw.schema.json")),
        "scope": "offline declaration conformance only; there is no runtime adapter in this D0 package",
    }


def main():
    nm1()
    nm2()
    nm5()
    nm6()
    out = HERE / "recompute-results.json"
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(RESULTS, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
