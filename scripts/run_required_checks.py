#!/usr/bin/env python3

import argparse
import json
import sys
import time
from pathlib import Path

from check_app_config_drift import MAINTENANCE_ROOT, is_onboarded
from mass_pr import gh_json, run


class RequiredChecks:
    """Start the required check workflows on a branch and wait for their result.

    Pushes and pull requests made with GITHUB_TOKEN do not start workflows, but
    workflow_dispatch does, so release and backport branches get their checks this way.
    """

    def __init__(self, repository: str, branch: str, sha: str, base_sha: str, checks: list[dict]):
        self.repository = repository
        self.branch = branch
        self.sha = sha
        self.base_sha = base_sha
        self.checks = checks
        self.previous_runs: dict[str, set[int]] = {}

    def start(self) -> None:
        for check in self.checks:
            workflow = check["workflow"]
            self.previous_runs[workflow] = {item["databaseId"] for item in self.get_runs(workflow)}
            command = ["gh", "workflow", "run", workflow, "--repo", self.repository, "--ref", self.branch]
            if check["accepts_base_sha"]:
                command += ["-f", f"base-sha={self.base_sha}"]
            run(command)
            print(f"Started {workflow} on {self.branch}")

    def wait(self, timeout_seconds: int, poll_seconds: int = 20) -> list[str]:
        """Return one message for each check that did not succeed."""
        deadline = time.monotonic() + timeout_seconds
        pending = [check["workflow"] for check in self.checks]
        failures = []
        while pending:
            for workflow in list(pending):
                result = self.get_new_run(workflow)
                if result and result["status"] == "completed":
                    pending.remove(workflow)
                    print(f"{workflow}: {result['conclusion']} {result['url']}")
                    if result["conclusion"] != "success":
                        failures.append(f"{workflow}: {result['conclusion']} {result['url']}")
            if pending and time.monotonic() > deadline:
                return failures + [f"{workflow}: no result after {timeout_seconds} seconds" for workflow in pending]
            if pending:
                time.sleep(poll_seconds)
        return failures

    def get_new_run(self, workflow: str) -> dict | None:
        runs = [item for item in self.get_runs(workflow) if item["databaseId"] not in self.previous_runs[workflow]]
        return max(runs, key=lambda item: item["databaseId"], default=None)

    def get_runs(self, workflow: str) -> list[dict]:
        return gh_json([
            "run", "list", "--repo", self.repository, "--workflow", workflow, "--branch", self.branch,
            "--event", "workflow_dispatch", "--commit", self.sha, "--limit", "20",
            "--json", "databaseId,status,conclusion,url",
        ]) or []


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the required checks on a branch made by a workflow.")
    parser.add_argument("--repository", required=True, help="owner/name of the app repository")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--sha", required=True, help="Commit at the tip of --branch")
    parser.add_argument("--base-sha", required=True, help="Commit the branch starts from")
    parser.add_argument("--no-wait", action="store_true", help="Start the checks and return")
    parser.add_argument("--timeout-minutes", type=int, default=30)
    parser.add_argument("--config", default=str(MAINTENANCE_ROOT / "configs/required-checks.json"))
    parser.add_argument("--apps", default=str(MAINTENANCE_ROOT / "configs/central-ci-apps.json"))
    args = parser.parse_args()

    if not is_onboarded(Path(args.apps), args.repository.split("/")[-1]):
        print(f"{args.repository} does not use central CI config yet; no required checks to run.")
        return 0

    checks = json.loads(Path(args.config).read_text(encoding="utf-8"))["checks"]
    required = RequiredChecks(args.repository, args.branch, args.sha, args.base_sha, checks)
    required.start()
    if args.no_wait:
        return 0

    failures = required.wait(args.timeout_minutes * 60)
    if failures:
        print("Required checks did not pass:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("All required checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
