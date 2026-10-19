#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

from mass_pr import load_config, render_template, render_text, template_context

MAINTENANCE_ROOT = Path(__file__).resolve().parents[1]


def find_drift(app_root, cfg, repository, branch):
    """Return a message for each managed file that differs from what the campaign writes."""
    full_repo = f"{cfg['organization']}/{repository}"
    context = template_context(cfg, full_repo, repository, branch)
    problems = []
    for item in cfg["files"]:
        target = render_text(item["target"], context)
        path = app_root / target
        if item.get("mode") == "delete":
            if path.exists():
                problems.append(f"{target}: must be removed")
            continue
        if not path.is_file():
            problems.append(f"{target}: missing")
        elif path.read_bytes() != render_template(item, context, MAINTENANCE_ROOT):
            problems.append(f"{target}: differs from {item['source']}")
    return problems


def is_onboarded(apps_path, repository):
    return repository in json.loads(apps_path.read_text(encoding="utf-8"))["repositories"]


def main():
    parser = argparse.ArgumentParser(description="Fail when files managed by frappe-maintenance were edited in an app.")
    parser.add_argument("--root", default=".", help="App repository root")
    parser.add_argument("--repository", required=True, help="App repository name, for example av_tools")
    parser.add_argument("--branch", required=True, help="Base branch the campaign targets")
    parser.add_argument("--config", default=str(MAINTENANCE_ROOT / "configs/sync-app-ci.json"))
    parser.add_argument("--apps", default=str(MAINTENANCE_ROOT / "configs/central-ci-apps.json"))
    args = parser.parse_args()

    if not is_onboarded(Path(args.apps), args.repository):
        print(f"{args.repository} does not use central CI config yet; skipping drift check.")
        return 0

    problems = find_drift(Path(args.root), load_config(args.config), args.repository, args.branch)
    if not problems:
        print("Managed config files match frappe-maintenance.")
        return 0

    print("These files are managed by Aakvatech-Limited/frappe-maintenance. Change the templates there, not in this app:")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
