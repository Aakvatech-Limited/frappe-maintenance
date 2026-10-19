#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path

MAINTENANCE_ROOT = Path(__file__).resolve().parents[1]
APPS_CONFIG = MAINTENANCE_ROOT / "configs/central-ci-apps.json"
FILES_CONFIG = MAINTENANCE_ROOT / "configs/app-config-files.json"


class AppConfigLinks:
    """Link the config files that frappe-maintenance owns into one app checkout.

    The links are never committed: CI links to its frappe-maintenance checkout, a developer
    machine links to the local clone and hides the links in .git/info/exclude.
    """

    def __init__(self, app_root: Path, maintenance_root: Path = MAINTENANCE_ROOT):
        self.app_root = app_root
        self.maintenance_root = maintenance_root
        self.files = json.loads(FILES_CONFIG.read_text(encoding="utf-8"))["files"]

    def get_tracked_files(self) -> list[str]:
        """Managed files committed to the app; they must come from frappe-maintenance instead."""
        targets = [item["target"] for item in self.files]
        result = subprocess.run(["git", "-C", self.app_root, "ls-files", "--", *targets],
                                capture_output=True, text=True, check=True)
        return result.stdout.split()

    def link(self) -> None:
        for item in self.files:
            target = self.app_root / item["target"]
            if target.exists() and not target.is_symlink():
                raise FileExistsError(f"{target} is a real file. Remove it from the app first.")
            target.unlink(missing_ok=True)
            target.symlink_to(self.maintenance_root / item["source"])

    def exclude_locally(self) -> None:
        exclude = self.app_root / ".git/info/exclude"
        existing = exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
        missing = [f"/{item['target']}" for item in self.files if f"/{item['target']}" not in existing]
        if missing:
            with exclude.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(["# Linked from frappe-maintenance", *missing]) + "\n")


def is_onboarded(repository: str) -> bool:
    return repository in json.loads(APPS_CONFIG.read_text(encoding="utf-8"))["repositories"]


def prepare_ci(app_root: Path, repository: str) -> int:
    if not is_onboarded(repository):
        print(f"{repository} does not use central CI config yet; using the app's own config files.")
        return 0

    links = AppConfigLinks(app_root)
    tracked = links.get_tracked_files()
    if tracked:
        print("These files are managed by Aakvatech-Limited/frappe-maintenance. Remove them from the app:")
        for path in tracked:
            print(f"  - {path}")
        return 1
    links.link()
    print("Linked config files from frappe-maintenance.")
    return 0


def install_bench(bench: Path) -> int:
    """Link configs and install git hooks for every onboarded app in a bench."""
    for app_root in sorted(path for path in (bench / "apps").iterdir() if (path / ".git").exists()):
        remote = subprocess.run(["git", "-C", app_root, "remote", "get-url", "origin"],
                                capture_output=True, text=True).stdout.strip()
        repository = remote.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]
        if not is_onboarded(repository):
            continue
        links = AppConfigLinks(app_root)
        links.link()
        links.exclude_locally()
        subprocess.run(["pre-commit", "install", "--install-hooks", "--overwrite"], cwd=app_root, check=True)
        print(f"{app_root.name}: configs linked and git hooks installed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Use frappe-maintenance config files in app checkouts.")
    commands = parser.add_subparsers(dest="command", required=True)
    ci = commands.add_parser("ci", help="Check and link one app checkout in CI")
    ci.add_argument("--root", type=Path, default=Path("."))
    ci.add_argument("--repository", required=True, help="App repository name, for example av_tools")
    install = commands.add_parser("install", help="Link configs and install hooks for a developer bench")
    install.add_argument("--bench", type=Path, required=True, help="Bench folder that contains apps/")
    args = parser.parse_args()

    if args.command == "ci":
        return prepare_ci(args.root.resolve(), args.repository)
    return install_bench(args.bench.resolve())


if __name__ == "__main__":
    sys.exit(main())
