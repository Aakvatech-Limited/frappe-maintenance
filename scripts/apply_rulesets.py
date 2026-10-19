#!/usr/bin/env python3

import argparse
import copy
import fnmatch
import json
import sys
import tempfile
from pathlib import Path

from app_config_links import MAINTENANCE_ROOT
from mass_pr import gh_json, gh_text, run

GITHUB_ACTIONS_APP_ID = 15368


def build_ruleset(template: dict, checks: list[dict]) -> dict:
    """Fill the ruleset template with the required checks; only GitHub Actions may report them."""
    ruleset = copy.deepcopy(template)
    rule = next(rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks")
    rule["parameters"]["required_status_checks"] = [
        {"context": check["context"], "integration_id": GITHUB_ACTIONS_APP_ID} for check in checks
    ]
    return ruleset


class RepositoryRuleset:
    """Create or update the required-checks ruleset on one app repository."""

    def __init__(self, full_repo: str, ruleset: dict, dry_run: bool):
        self.full_repo = full_repo
        self.ruleset = ruleset
        self.dry_run = dry_run

    def apply(self) -> None:
        existing = self.get_existing_id()
        action = f"update ruleset {existing}" if existing else "create ruleset"
        print(f"{self.full_repo}: {action} '{self.ruleset['name']}'")
        if self.dry_run:
            return
        method, path = ("PUT", f"repos/{self.full_repo}/rulesets/{existing}") if existing else (
            "POST", f"repos/{self.full_repo}/rulesets")
        with tempfile.NamedTemporaryFile("w", suffix=".json") as body:
            json.dump(self.ruleset, body)
            body.flush()
            run(["gh", "api", "--method", method, path, "--input", body.name])

    def clear_classic_required_checks(self) -> None:
        """Old branch protection checks would wait for check names that no longer run."""
        for branch in self.get_covered_branches():
            path = f"repos/{self.full_repo}/branches/{branch}/protection/required_status_checks"
            if run(["gh", "api", path], check=False).returncode != 0:
                continue
            print(f"{self.full_repo}: remove classic required checks on {branch}")
            if not self.dry_run:
                run(["gh", "api", "--method", "DELETE", path])

    def get_existing_id(self) -> int | None:
        rulesets = gh_json(["api", f"repos/{self.full_repo}/rulesets", "--paginate"]) or []
        return next((item["id"] for item in rulesets if item["name"] == self.ruleset["name"]), None)

    def get_covered_branches(self) -> list[str]:
        default_branch = gh_text(["api", f"repos/{self.full_repo}", "--jq", ".default_branch"])
        branches = gh_text(["api", f"repos/{self.full_repo}/branches", "--paginate", "--jq", ".[].name"]).splitlines()
        return [name for name in branches if name == default_branch or fnmatch.fnmatch(name, "version-*")]


def get_repositories(apps_path: Path, repository: str | None) -> list[str]:
    onboarded = json.loads(apps_path.read_text(encoding="utf-8"))["repositories"]
    if repository is None:
        return onboarded
    if repository not in onboarded:
        raise SystemExit(f"{repository} is not in {apps_path.name}. Add it there before applying rulesets.")
    return [repository]


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the required-checks ruleset to apps on central CI config.")
    parser.add_argument("--repository", help="One app repository name; default is every onboarded app")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--organization", default="Aakvatech-Limited")
    parser.add_argument("--ruleset", default=str(MAINTENANCE_ROOT / "configs/rulesets/required-checks.json"))
    parser.add_argument("--checks", default=str(MAINTENANCE_ROOT / "configs/required-checks.json"))
    parser.add_argument("--apps", default=str(MAINTENANCE_ROOT / "configs/central-ci-apps.json"))
    args = parser.parse_args()

    template = json.loads(Path(args.ruleset).read_text(encoding="utf-8"))
    checks = json.loads(Path(args.checks).read_text(encoding="utf-8"))["checks"]
    ruleset = build_ruleset(template, checks)
    for repository in get_repositories(Path(args.apps), args.repository):
        target = RepositoryRuleset(f"{args.organization}/{repository}", ruleset, args.dry_run)
        try:
            target.apply()
            target.clear_classic_required_checks()
        except RuntimeError as error:
            print(f"{target.full_repo}: {error}")
            print("The token needs Administration: write on this repository. Without the ruleset the checks "
                  "still run on every PR, but a failing check does not block the merge.")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
