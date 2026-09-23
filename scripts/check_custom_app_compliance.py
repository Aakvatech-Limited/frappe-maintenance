#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_json_files(root, ignored):
    for path in root.rglob("*.json"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file():
            yield path


def collect_doctypes(value, found):
    if isinstance(value, dict):
        doctype = value.get("doctype")
        if isinstance(doctype, str):
            found.add(doctype)
        for child in value.values():
            collect_doctypes(child, found)
    elif isinstance(value, list):
        for child in value:
            collect_doctypes(child, found)


def analyze(root, config):
    ignored = set(config.get("ignored_directories", []))
    rules = config["required_artifacts"]

    results = {
        rule["key"]: {
            "name": rule["name"],
            "min_count": int(rule.get("min_count", 1)),
            "matches": [],
        }
        for rule in rules
    }

    for path in iter_json_files(root, ignored):
        relative = path.relative_to(root)
        segments = set(relative.parts)

        for rule in rules:
            if any(segment in segments for segment in rule.get("path_segments", [])):
                results[rule["key"]]["matches"].append(str(relative))

        doctypes = set()
        try:
            parsed = load_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            parsed = None

        if parsed is not None:
            collect_doctypes(parsed, doctypes)
            for rule in rules:
                if doctypes.intersection(rule.get("doctypes", [])):
                    results[rule["key"]]["matches"].append(str(relative))

    for result in results.values():
        result["matches"] = sorted(set(result["matches"]))
        result["count"] = len(result["matches"])
        result["compliant"] = result["count"] >= result["min_count"]

    compliant = all(result["compliant"] for result in results.values())
    return compliant, results


def write_summary(compliant, results):
    status = "PASS" if compliant else "FAIL"
    lines = [
        "# Custom App Compliance",
        "",
        f"Overall status: **{status}**",
        "",
        "| Requirement | Found | Minimum | Status |",
        "|---|---:|---:|---|",
    ]

    for result in results.values():
        state = "PASS" if result["compliant"] else "MISSING"
        lines.append(
            f"| {result['name']} | {result['count']} | {result['min_count']} | {state} |"
        )

    lines.append("")
    for result in results.values():
        if result["matches"]:
            lines.append(f"## {result['name']}")
            for match in result["matches"][:20]:
                lines.append(f"- {match}")
            if len(result["matches"]) > 20:
                lines.append(f"- ... and {len(result['matches']) - 20} more")
            lines.append("")

    summary = "\n".join(lines)
    print(summary)

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Check a Frappe custom app repository for required UI/reporting artifacts."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan")
    parser.add_argument(
        "--config",
        default="configs/custom-app-compliance.json",
        help="Compliance rule configuration",
    )
    parser.add_argument("--json-output", help="Optional path for machine-readable results")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config_path = Path(args.config).resolve()

    if not root.is_dir():
        print(f"Repository root does not exist: {root}", file=sys.stderr)
        return 2
    if not config_path.is_file():
        print(f"Compliance config does not exist: {config_path}", file=sys.stderr)
        return 2

    config = load_json(config_path)
    compliant, results = analyze(root, config)
    write_summary(compliant, results)

    if args.json_output:
        Path(args.json_output).write_text(
            json.dumps(
                {"compliant": compliant, "requirements": results},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    if not compliant:
        missing = [
            result["name"]
            for result in results.values()
            if not result["compliant"]
        ]
        print(
            "::error title=Custom app compliance failed::Missing required artifacts: "
            + ", ".join(missing)
        )
        return 1

    print("::notice title=Custom app compliance passed::All required artifacts were found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
