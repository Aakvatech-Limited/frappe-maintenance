#!/usr/bin/env python3
"""Organization-wide, conservative reconciliation of labeled backports.

GitHub Issues are the durable exception register. Linked merged backport PRs
are the only automatic completion evidence; manual cherry-picks need review.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
LABEL = "backport-exception"
MARKER = "<!-- aakvatech-backport-exception:"
TARGET = re.compile(r"^backport-to-(.+)$")
BACKPORT_TITLE = re.compile(r"^\[Backport ([^\]]+)\]")
LINK = re.compile(r"\bBackport of #(\d+)\b", re.I)


class GitHub:
    def __init__(self, token):
        self.token = token

    def get(self, path, params=None):
        url = API + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "frappe-maintenance-backport-reconciler",
        })
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"GitHub GET {path}: {exc.code}: {body}") from exc

    def change(self, method, path, data):
        req = urllib.request.Request(API + path, method=method,
            data=json.dumps(data).encode(), headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "frappe-maintenance-backport-reconciler",
            })
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub {method} {path}: {exc.code}: {exc.read().decode()[:500]}") from exc

    def pages(self, path, params=None, max_pages=20):
        for page in range(1, max_pages + 1):
            data = self.get(path, dict(params or {}, per_page=100, page=page))
            if not isinstance(data, list):
                raise RuntimeError(f"Expected list from {path}")
            yield from data
            if len(data) < 100:
                return
        raise RuntimeError(f"Pagination safety limit exceeded: {path}")


def key_for(repo, number, branch):
    return f"{repo}#{number}@{branch}"


def issue_body(item):
    key = item["key"]
    lines = [
        f"{MARKER}{key} -->",
        "## Outstanding backport",
        "",
        f"- **Source:** {item['source_url']}",
        f"- **Target:** \`{item['branch']}\`",
        f"- **Status:** {item['status']}",
        f"- **Source merged:** {item['merged_at']}",
        f"- **Last audited (UTC):** {item['checked_at']}",
        f"- **Evidence:** {item['evidence']}",
        "",
        "### Backport candidates",
    ]
    lines += [f"- {p['html_url']} ({'merged' if p['merged_at'] else p['state']})"
              for p in item["candidates"]] or ["- None found"]
    lines += ["", "### Resolution",
              "A linked merged backport PR is automatically verifiable. If the change was "
              "manually cherry-picked without a linked PR, add the target commit/PR evidence "
              "and resolve after review. Missing candidates do not prove a conflict.",
              "", "Managed by frappe-maintenance; avoid editing the marker."]
    return "\n".join(lines)


def find_candidates(client, repo, source, branch, cutoff):
    # Search only closed/open PRs on target branch. API list is chronological
    # by last update; do not infer completion from title alone.
    found = []
    for pr in client.pages(f"/repos/{repo}/pulls", {"state": "all", "base": branch,
                                                     "sort": "updated", "direction": "desc"},
                           max_pages=10):
        if pr["updated_at"] < cutoff:
            break
        title = BACKPORT_TITLE.match(pr.get("title") or "")
        if not title or title.group(1) != branch:
            continue
        body = pr.get("body") or ""
        link = LINK.search(body)
        if link and int(link.group(1)) == source:
            found.append({"number": pr["number"], "html_url": pr["html_url"],
                          "state": pr["state"], "merged_at": pr.get("merged_at")})
    return found


def audit_repo(client, repo, cutoff, now, exclusions):
    if repo in exclusions:
        return []
    # Paginate merged PRs, including closed PRs that were not merged (skip).
    items = []
    for pr in client.pages(f"/repos/{repo}/pulls",
                           {"state": "closed", "sort": "updated", "direction": "desc"},
                           max_pages=15):
        # Use merge date rather than update date to include late-labeled PRs.
        if pr["updated_at"] < cutoff:
            break
        if not pr.get("merged_at"):
            continue
        branches = {m.group(1) for l in pr.get("labels", [])
                    if (m := TARGET.fullmatch(l["name"]))}
        for branch in sorted(branches):
            candidates = find_candidates(client, repo, pr["number"], branch, cutoff)
            merged = [p for p in candidates if p["merged_at"]]
            opened = [p for p in candidates if p["state"] == "open"]
            status = ("completed" if merged else "awaiting_merge" if opened
                      else "unverified")
            evidence = ("Linked backport PR merged" if merged else
                        "Linked backport PR open" if opened else
                        "No linked backport PR found; may be conflict, missing run, or manual cherry-pick")
            items.append({"key": key_for(repo, pr["number"], branch), "repository": repo,
                          "source_pr": pr["number"], "source_url": pr["html_url"],
                          "branch": branch, "status": status, "evidence": evidence,
                          "merged_at": pr["merged_at"], "checked_at": now,
                          "candidates": candidates})
    return items


def registered_issues(client, registry):
    known = {}
    for issue in client.pages(f"/repos/{registry}/issues",
                              {"state": "all", "labels": LABEL}, max_pages=20):
        if "pull_request" in issue:
            continue
        match = re.search(r"<!-- aakvatech-backport-exception:(.*?) -->",
                          issue.get("body") or "")
        if match:
            known[match.group(1)] = issue
    return known


def sync_issues(client, registry, items, dry_run):
    current = registered_issues(client, registry)
    actions = []
    for item in items:
        key = item["key"]
        issue = current.get(key)
        done = item["status"] == "completed"
        body = issue_body(item)
        title = f"[Backport] {item['repository'].split('/')[-1]} #{item['source_pr']} -> {item['branch']}"
        if not issue and done:
            continue
        if not issue:
            actions.append(f"OPEN {key}")
            if not dry_run:
                client.change("POST", f"/repos/{registry}/issues",
                              {"title": title, "body": body, "labels": [LABEL]})
        elif done and issue["state"] != "closed":
            actions.append(f"CLOSE {key}")
            if not dry_run:
                client.change("PATCH", f"/repos/{registry}/issues/{issue['number']}",
                              {"state": "closed", "state_reason": "completed", "body": body})
        elif not done:
            changed = (issue.get("body") != body or issue["state"] != "open")
            if changed:
                actions.append(f"UPDATE {key}")
                if not dry_run:
                    client.change("PATCH", f"/repos/{registry}/issues/{issue['number']}",
                                  {"title": title, "state": "open", "body": body})
    return actions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", default="Aakvatech-Limited")
    ap.add_argument("--registry", default="Aakvatech-Limited/frappe-maintenance")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--repo", help="Limit to one repository (name or owner/name)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-repos", type=int, default=150)
    args = ap.parse_args()
    if not 1 <= args.days <= 730:
        ap.error("--days must be between 1 and 730")
    token = os.environ.get("BACKPORT_MONITOR_TOKEN")
    if not token:
        ap.error("BACKPORT_MONITOR_TOKEN is required, including for dry-run")
    client = GitHub(token)
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.repo:
        name = args.repo if "/" in args.repo else args.org + "/" + args.repo
        repositories = [client.get("/repos/" + name)]
    else:
        repositories = list(client.pages(f"/orgs/{args.org}/repos",
                                         {"type": "all", "sort": "full_name"},
                                         max_pages=20))
    active = [r["full_name"] for r in repositories if not r.get("archived")
              and r["full_name"] != args.registry]
    if len(active) > args.max_repos:
        raise RuntimeError("Repository count exceeds safety limit; narrow --repo")
    all_items = []
    errors = []
    for repo in active:
        try:
            items = audit_repo(client, repo, cutoff, now.isoformat(), set())
            all_items.extend(items)
            print(repo, "expected targets:", len(items), flush=True)
        except Exception as exc:
            errors.append(repo + ": " + str(exc))
            print("ERROR", errors[-1], file=sys.stderr, flush=True)
    # Never close issues for missing scan results; only explicit linked merge evidence.
    actions = sync_issues(client, args.registry, all_items, args.dry_run)
    result = {"scanned_repositories": len(active), "expected_targets": len(all_items),
              "unresolved": sum(x["status"] != "completed" for x in all_items),
              "completed": sum(x["status"] == "completed" for x in all_items),
              "actions": actions, "errors": errors, "items": all_items}
    with open("backport-reconciliation.json", "w", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "items"}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
