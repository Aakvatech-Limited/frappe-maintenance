#!/usr/bin/env python3

import argparse
import base64
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def run(cmd, check=True, capture=True):
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise RuntimeError("Command failed: " + " ".join(cmd))
    return result


def gh_json(args):
    result = run(["gh", *args])
    text = result.stdout.strip()
    return json.loads(text) if text else None


def gh_text(args, check=True):
    result = run(["gh", *args], check=check)
    return result.stdout.strip()


def slug(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        cfg = json.load(handle)

    required = [
        "organization",
        "files",
        "work_branch_prefix",
        "commit_message",
        "pr_title",
        "pr_body",
    ]
    missing = [key for key in required if key not in cfg]
    if missing:
        raise ValueError("Missing config keys: " + ", ".join(missing))

    if not isinstance(cfg["files"], list) or not cfg["files"]:
        raise ValueError("files must be a non-empty list")

    for item in cfg["files"]:
        if not item.get("source") or not item.get("target"):
            raise ValueError("Each files entry requires source and target")
        if item.get("mode", "create_or_update") not in {
            "create_only",
            "update_only",
            "create_or_update",
        }:
            raise ValueError("Unsupported file mode: " + item.get("mode", ""))

    return cfg


def list_repositories(org):
    data = gh_json([
        "repo",
        "list",
        org,
        "--limit",
        "1000",
        "--json",
        "name,isArchived,isFork",
    ]) or []
    return [r["name"] for r in data if not r.get("isArchived") and not r.get("isFork")]


def list_branches(full_repo):
    data = gh_json([
        "api",
        "--paginate",
        f"repos/{full_repo}/branches?per_page=100",
    ]) or []
    return [b["name"] for b in data]


def tree_paths(full_repo, branch):
    data = gh_json([
        "api",
        f"repos/{full_repo}/git/trees/{branch}?recursive=1",
    ]) or {}
    return [item.get("path", "") for item in data.get("tree", [])]


def path_requirements_match(paths, patterns, mode):
    if not patterns:
        return True, ""

    counts = {
        pattern: sum(1 for path in paths if fnmatch.fnmatch(path, pattern))
        for pattern in patterns
    }

    if mode == "at_least_one_each":
        ok = all(count > 0 for count in counts.values())
    elif mode == "exactly_one_each":
        ok = all(count == 1 for count in counts.values())
    elif mode == "any":
        ok = any(count > 0 for count in counts.values())
    else:
        raise ValueError("Unknown required_paths_mode: " + mode)

    details = ", ".join(f"{pattern}={count}" for pattern, count in counts.items())
    return ok, details


def get_ref_sha(full_repo, branch):
    data = gh_json(["api", f"repos/{full_repo}/git/ref/heads/{branch}"])
    return data["object"]["sha"]


def branch_exists(full_repo, branch):
    result = run(
        ["gh", "api", f"repos/{full_repo}/git/ref/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def create_branch(full_repo, branch, sha):
    gh_text([
        "api",
        "-X",
        "POST",
        f"repos/{full_repo}/git/refs",
        "-f",
        f"ref=refs/heads/{branch}",
        "-f",
        f"sha={sha}",
    ])


def fetch_file_meta(full_repo, target, branch):
    result = run(
        ["gh", "api", f"repos/{full_repo}/contents/{target}?ref={branch}"],
        check=False,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def put_file(full_repo, target, branch, content, message, existing_sha=None):
    args = [
        "api",
        "-X",
        "PUT",
        f"repos/{full_repo}/contents/{target}",
        "-f",
        f"message={message}",
        "-f",
        "content=" + base64.b64encode(content).decode("ascii"),
        "-f",
        f"branch={branch}",
    ]
    if existing_sha:
        args += ["-f", f"sha={existing_sha}"]
    gh_text(args)


def apply_files(full_repo, base_branch, work_branch, cfg, dry_run):
    changes = 0

    for item in cfg["files"]:
        source = Path(item["source"])
        target = item["target"]
        mode = item.get("mode", "create_or_update")

        if not source.is_file():
            raise FileNotFoundError(f"Template not found: {source}")

        desired = source.read_bytes()
        existing = fetch_file_meta(full_repo, target, work_branch)

        if existing is None and mode == "update_only":
            print(f"    skip {target}: update_only and file does not exist")
            continue
        if existing is not None and mode == "create_only":
            print(f"    skip {target}: create_only and file already exists")
            continue

        if existing is not None:
            current = base64.b64decode(existing.get("content", ""))
            if current == desired:
                print(f"    unchanged {target}")
                continue

        changes += 1
        action = "update" if existing else "create"
        print(f"    {action} {target}")

        if not dry_run:
            put_file(
                full_repo,
                target,
                work_branch,
                desired,
                cfg["commit_message"],
                existing_sha=existing.get("sha") if existing else None,
            )

    return changes


def ensure_pr(full_repo, base_branch, work_branch, cfg, dry_run):
    prs = gh_json([
        "pr",
        "list",
        "--repo",
        full_repo,
        "--head",
        work_branch,
        "--state",
        "open",
        "--json",
        "number,url",
    ]) or []

    if prs:
        print(f"    PR already open: {prs[0].get('url', prs[0]['number'])}")
        return

    if dry_run:
        print("    would create PR")
        return

    url = gh_text([
        "pr",
        "create",
        "--repo",
        full_repo,
        "--base",
        base_branch,
        "--head",
        work_branch,
        "--title",
        cfg["pr_title"],
        "--body",
        cfg["pr_body"],
    ])
    print(f"    PR created: {url}")


def main():
    parser = argparse.ArgumentParser(description="Create configuration-driven PRs across GitHub organization repositories")
    parser.add_argument("config", help="Path to JSON configuration")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and report without making changes")
    args = parser.parse_args()

    if not os.environ.get("GH_TOKEN"):
        print("GH_TOKEN is required", file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    org = cfg["organization"]
    repo_include = re.compile(cfg.get("repository_include_regex", ".*"))
    repo_exclude = re.compile(cfg.get("repository_exclude_regex", r"$^"))
    branch_include = re.compile(cfg.get("branch_include_regex", ".*"))
    branch_exclude = re.compile(cfg.get("branch_exclude_regex", r"$^"))
    required_paths = cfg.get("required_paths", [])
    required_mode = cfg.get("required_paths_mode", "at_least_one_each")

    for repo in list_repositories(org):
        if not repo_include.search(repo) or repo_exclude.search(repo):
            continue

        full_repo = f"{org}/{repo}"
        print(f"== {full_repo} ==")

        for branch in list_branches(full_repo):
            if not branch_include.search(branch) or branch_exclude.search(branch):
                continue

            paths = tree_paths(full_repo, branch)
            matched, details = path_requirements_match(paths, required_paths, required_mode)
            if not matched:
                print(f"  skip {branch}: required path check failed ({details})")
                continue

            work_branch = slug(f"{cfg['work_branch_prefix']}-{branch}")
            print(f"  {branch} -> {work_branch}")

            if args.dry_run:
                changes = apply_files(full_repo, branch, work_branch if branch_exists(full_repo, work_branch) else branch, cfg, True)
                if changes:
                    ensure_pr(full_repo, branch, work_branch, cfg, True)
                else:
                    print("    no changes required")
                continue

            if not branch_exists(full_repo, work_branch):
                create_branch(full_repo, work_branch, get_ref_sha(full_repo, branch))

            changes = apply_files(full_repo, branch, work_branch, cfg, False)
            if changes:
                ensure_pr(full_repo, branch, work_branch, cfg, False)
            else:
                print("    no changes required")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
