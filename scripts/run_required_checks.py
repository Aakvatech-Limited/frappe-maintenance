#!/usr/bin/env python3

import argparse
import json
import sys
import time
from pathlib import Path

from app_config_links import MAINTENANCE_ROOT, is_onboarded
from mass_pr import gh_json, run


class RequiredChecks:
    """Start the app trigger in checks mode on a branch and wait for its result.

    Pushes and pull requests made with GITHUB_TOKEN do not start workflows, but
    workflow_dispatch does, so release and backport branches get their checks this way.
    """

    def __init__(self, repository: str, branch: str, sha: str, base_sha: str, trigger: str):
        self.repository = repository
        self.branch = branch
        self.sha = sha
        self.base_sha = base_sha
        self.trigger = trigger
        self.previous_runs: set[int] = set()

    def start(self) -> None:
        self.previous_runs = {item["databaseId"] for item in self.get_runs()}
        run(["gh", "workflow", "run", self.trigger, "--repo", self.repository, "--ref", self.branch,
             "-f", "task=checks", "-f", f"base-sha={self.base_sha}"])
        print(f"Started {self.trigger} checks on {self.branch}")

    def wait(self, timeout_seconds: int, poll_seconds: int = 20) -> str | None:
        """Return a failure message, or None when the checks passed."""
        deadline = time.monotonic() + timeout_seconds
        while True:
            result = self.get_new_run()
            if result and result["status"] == "completed":
                print(f"{self.trigger}: {result['conclusion']} {result['url']}")
                return None if result["conclusion"] == "success" else f"{result['conclusion']} {result['url']}"
            if time.monotonic() > deadline:
                return f"no result after {timeout_seconds} seconds"
            time.sleep(poll_seconds)

    def get_new_run(self) -> dict | None:
        runs = [item for item in self.get_runs() if item["databaseId"] not in self.previous_runs]
        return max(runs, key=lambda item: item["databaseId"], default=None)

    def get_runs(self) -> list[dict]:
        return gh_json([
            "run", "list", "--repo", self.repository, "--workflow", self.trigger, "--branch", self.branch,
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
    args = parser.parse_args()

    if not is_onboarded(args.repository.split("/")[-1]):
        print(f"{args.repository} does not use central CI config yet; no required checks to run.")
        return 0

    trigger = json.loads(Path(args.config).read_text(encoding="utf-8"))["trigger"]
    required = RequiredChecks(args.repository, args.branch, args.sha, args.base_sha, trigger)
    required.start()
    if args.no_wait:
        return 0

    failure = required.wait(args.timeout_minutes * 60)
    if failure:
        print(f"Required checks did not pass: {failure}")
        return 1
    print("All required checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
