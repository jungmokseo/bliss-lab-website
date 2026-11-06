#!/usr/bin/env python3
"""Validate and publish a Notion snapshot without modifying the operator checkout."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools"))

from notion_bibliography import merge_bibliography
from notion_highlights import merge_highlights
from notion_people_news import merge_news, merge_team

ORIGIN = "https://github.com/jungmokseo/bliss-lab-website.git"
SITE = "https://bliss.yonsei.ac.kr"
BRANCH = "refs/heads/main"
SOURCES = ("publications", "patents", "team", "news", "highlights")
FILES = {
    "publications": "data/publications.json", "patents": "data/publications.json",
    "team": "data/team.json", "news": "data/news.json", "highlights": "index.html",
}
ALLOWED = set(FILES.values()) | {"llms.txt", "llms-full.txt", "sitemap.xml"}
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1")


def command(root, *args, capture=False):
    return subprocess.run(args, cwd=root, env=ENV, text=True, check=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def git(root, *args):
    return command(root, "git", *args, capture=True).strip()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_private(path, data):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".sync-", delete=False) as f:
        tmp = Path(f.name)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def validate_snapshot(snapshot, *, fresh=True):
    if snapshot.get("version") != 1 or set(snapshot.get("sources", {})) != set(SOURCES):
        raise ValueError("Unexpected snapshot format or incomplete source set.")
    captured = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - captured
    if fresh and not -timedelta(minutes=2) <= age <= timedelta(minutes=25):
        raise ValueError("Snapshot is stale; export Notion again.")
    for key in SOURCES:
        rows = snapshot["sources"][key]
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"Empty or invalid Notion source: {key}.")
        ids = set()
        for row in rows:
            ident = row.get("_id") if isinstance(row, dict) else None
            if not isinstance(ident, str) or not re.fullmatch(r"[0-9a-f]{32}", ident) or ident in ids:
                raise ValueError(f"Missing or duplicate Notion page ID in {key}.")
            if any(k.startswith("_") and k != "_id" for k in row):
                raise ValueError(f"Unexpected internal field in {key}.")
            ids.add(ident)


def site_hashes(root):
    result = {}
    for key, name in FILES.items():
        data = (root / name).read_bytes()
        if key == "highlights":
            match = re.search(rb'<section\b[^>]*\bid="highlights"[^>]*>.*?</section>', data, re.S)
            if not match:
                raise ValueError("Could not locate the public Highlights section.")
            data = match[0]
        result[key] = hashlib.sha256(data).hexdigest()
    return result


def differences(current, baseline, hashes):
    if datetime.fromisoformat(current['captured_at'].replace('Z', '+00:00')) < datetime.fromisoformat(
            baseline['snapshot']['captured_at'].replace('Z', '+00:00')):
        raise ValueError('Snapshot predates the recorded baseline.')
    result = {}
    for key in SOURCES:
        old = {r["_id"]: r for r in baseline["snapshot"]["sources"][key]}
        new = {r["_id"]: r for r in current["sources"][key]}
        missing = set(old) - set(new)
        if missing:
            raise ValueError(f"{key}: {len(missing)} Notion row(s) disappeared; "
                             "restore them or reconcile explicitly. No public data was deleted.")
        delta = []
        for ident, row in new.items():
            previous = old.get(ident)
            if previous is None:
                delta.append(row)
            else:
                changed = sorted(k for k in set(row) | set(previous)
                                 if not k.startswith("_") and row.get(k) != previous.get(k))
                if changed:
                    delta.append(dict(row, _previous=previous, _changed_fields=changed,
                                      _site_unchanged=hashes[key] == baseline["site_hashes"][key]))
        result[key] = delta
    return result


def keep_fields(before, after, section, key):
    old = before[section]
    new = {key(x): x for x in after[section]}
    if len(new) != len(after[section]) or any(key(x) not in new for x in old):
        raise ValueError(f"{section}: lost an existing record or duplicated an identity.")
    for entry in old:
        candidate = new[key(entry)]
        if set(entry) - set(candidate) or any(value not in (None, "", [], {})
                and candidate[field] in (None, "", [], {}) for field, value in entry.items()):
            raise ValueError(f"{section}: existing metadata would be dropped.")


def write_changed(path, before, after):
    if before != after:
        path.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_delta(root, delta, hashes, baseline_hashes):
    bibliography_path = root / FILES["publications"]
    team_path = root / FILES["team"]
    news_path = root / FILES["news"]
    before = read_json(bibliography_path)
    bibliography = merge_bibliography(before, delta["publications"], delta["patents"], root=root)
    keep_fields(before, bibliography, "publications", lambda x: x["number"])
    keep_fields(before, bibliography, "patents", lambda x: (x["country"], x["number"]))

    team_before = read_json(team_path)
    team = merge_team(team_before, delta["team"], root=root)
    keep_fields(team_before, team, "members", lambda x: x["id"])
    for field in ("alumni", "categories"):
        if team_before[field] != team[field]:
            raise ValueError(f"Team {field} cannot be rewritten automatically.")
    for member in team_before["members"]:
        updated = next(x for x in team["members"] if x["id"] == member["id"])
        if member.get("education") != updated.get("education"):
            raise ValueError("Existing member education is maintained separately.")

    news_before = read_json(news_path)
    news = merge_news(news_before, delta["news"], root=root)
    keep_fields(news_before, news, "news", lambda x: x["slug"])

    index = root / "index.html"
    old_html = index.read_text(encoding="utf-8")
    html = merge_highlights(old_html, delta["highlights"],
                            publications=bibliography["publications"], root=root)
    for key in ("publications", "patents", "team", "news"):
        old, new = ({"publications": (before["publications"], bibliography["publications"]),
                     "patents": (before["patents"], bibliography["patents"]),
                     "team": (team_before, team), "news": (news_before, news)})[key]
        if old != new and hashes[key] != baseline_hashes[key]:
            raise ValueError(f"{key}: both the website and Notion changed since the baseline; reconcile the public copy first.")
    write_changed(bibliography_path, before, bibliography)
    write_changed(team_path, team_before, team)
    write_changed(news_path, news_before, news)
    if old_html != html:
        index.write_text(html, encoding="utf-8")
    return any((before != bibliography, team_before != team, news_before != news, old_html != html))


def verify(root, *, regenerate):
    python = sys.executable
    if regenerate:
        command(root, python, "tools/prerender.py")
        env = dict(ENV, TZ="Asia/Seoul")
        subprocess.run([python, "tools/build_llms.py"], cwd=root, env=env, check=True)
    for args in (("tools/prerender.py", "--check"), ("tools/migrate_brief_slugs.py", "--check"),
                 ("tools/check_bilingual.py",), ("-m", "unittest", "discover", "-s", "tools", "-p", "test_*.py")):
        command(root, python, *args)
    command(root, "git", "diff", "--check")


def live_matches(expected, sha, seconds):
    deadline = time.monotonic() + seconds
    while True:
        matched = True
        for path, wanted in expected.items():
            url = f"{SITE}/{path}?sync={sha[:12]}-{int(time.time())}"
            req = Request(url, headers={"Cache-Control": "no-cache", "Accept-Encoding": "identity"})
            try:
                with urlopen(req, timeout=12) as r:
                    body = r.read(10 * 1024 * 1024)
                if hashlib.sha256(body).hexdigest() != wanted:
                    matched = False
                    break
            except (URLError, TimeoutError, OSError):
                matched = False
                break
        if matched:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(10, remaining))


def sync(args):
    state_dir = args.state_dir.resolve()
    if state_dir.is_relative_to(REPO):
        raise ValueError("State and raw Notion snapshots must remain outside the public repository.")
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state_dir.stat().st_mode & 0o077:
        raise ValueError("Set the private state directory permissions to 700.")
    snapshot_path = args.snapshot.resolve()
    if not snapshot_path.is_relative_to(state_dir) or snapshot_path.stat().st_mode & 0o077:
        raise ValueError("Snapshot must be in the private state directory with mode 600.")
    snapshot = read_json(snapshot_path)
    validate_snapshot(snapshot)
    base_path, pending_path = state_dir / "baseline.json", state_dir / "pending.json"

    with (state_dir / "sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise ValueError("Another Notion sync is running.") from e
        if git(REPO, "remote", "get-url", "origin") != ORIGIN:
            raise ValueError("Unexpected Git origin; will not publish.")
        git(REPO, "fetch", "origin", "main")
        head = git(REPO, "rev-parse", "origin/main")

        if pending_path.exists():
            pending = read_json(pending_path)
            if args.mode != "publish":
                raise ValueError("A published update is waiting for live verification; resume in publish mode.")
            if head == pending["head"] and live_matches(pending["expected"], head, args.wait):
                write_private(base_path, pending["baseline"])
                pending_path.unlink()
                print(f"VERIFIED {head[:12]}: previous push is now live.")
            elif head == pending["parent"]:
                # A failed push with the parent still at main did not publish anything.
                pending_path.unlink()
            else:
                raise ValueError("A prior push cannot yet be verified on the live site; baseline unchanged.")

        with tempfile.TemporaryDirectory(prefix="bliss-notion-sync-") as td:
            work = Path(td) / "site"
            git(REPO, "clone", "--quiet", "--shared", "--no-checkout", str(REPO), str(work))
            git(work, "checkout", "--quiet", "--detach", head)
            hashes = site_hashes(work)
            new_baseline = {"snapshot": snapshot, "site_hashes": hashes, "commit": head}
            if args.mode == "bootstrap":
                if base_path.exists():
                    raise ValueError("Baseline already exists; automatic reset is disabled.")
                verify(work, regenerate=False)
                write_private(base_path, new_baseline)
                print("BASELINE: recorded existing Notion state without changing the site.")
                return
            if not base_path.exists():
                raise ValueError("No initial baseline. Run bootstrap once from a verified snapshot.")
            baseline = read_json(base_path)
            validate_snapshot(baseline["snapshot"], fresh=False)
            delta = differences(snapshot, baseline, hashes)
            counts = {k: len(v) for k, v in delta.items()}
            print("Notion rows changed:", json.dumps(counts), flush=True)
            if not any(counts.values()):
                if args.mode == "publish" and head != baseline["commit"]:
                    write_private(base_path, new_baseline)
                print("NO CHANGE: no commit or deployment.")
                return
            changed = apply_delta(work, delta, hashes, baseline['site_hashes'])
            verify(work, regenerate=changed)
            if not changed:
                if args.mode == "publish":
                    write_private(base_path, new_baseline)
                print("NO PUBLIC CHANGE: existing public content already matches or no fields are publishable.")
                return

            paths = set(git(work, "diff", "--name-only").splitlines())
            if not paths or paths - ALLOWED or git(work, "ls-files", "--others", "--exclude-standard"):
                raise ValueError("Candidate changed files outside the sync allowlist.")
            # Review a scoped diff plus the structured retention checks above before commit.
            diff = git(work, "diff", "--binary", "--", *sorted(paths))
            if not diff:
                raise ValueError("Expected a nonempty reviewed diff.")
            print(git(work, "diff", "--stat", "--", *sorted(paths)), flush=True)
            if args.mode == "preview":
                print("PREVIEW PASSED: no commit, push or baseline change.")
                return

            for key in ("user.name", "user.email"):
                git(work, "config", key, git(REPO, "config", "--get", key))
            git(work, "add", "--", *sorted(paths))
            git(work, "diff", "--cached", "--check")
            if set(git(work, "diff", "--cached", "--name-only").splitlines()) != paths:
                raise ValueError("Staged files differ from the verified candidate.")
            git(work, "commit", "-m", "Sync verified BLISS website updates from Notion")
            sha = git(work, "rev-parse", "HEAD")
            new_baseline.update(site_hashes=site_hashes(work), commit=sha)
            expected = {p: hashlib.sha256((work / p).read_bytes()).hexdigest()
                        for p in paths if p in set(FILES.values())}
            pending = {"head": sha, "parent": head, "expected": expected, "baseline": new_baseline}
            write_private(pending_path, pending)
            try:
                git(work, "push", ORIGIN, "HEAD:" + BRANCH)
            except subprocess.CalledProcessError:
                # Distinguish a confirmed non-fast-forward from a lost push response.
                probe = subprocess.run(["git", "fetch", ORIGIN, "main"], cwd=work, env=ENV,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if probe.returncode == 0 and subprocess.run(
                        ["git", "merge-base", "--is-ancestor", sha, "FETCH_HEAD"],
                        cwd=work, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 1:
                    pending_path.unlink()
                raise
            print(f"PUSHED {sha[:12]}: waiting for GitHub Pages.", flush=True)
            if not live_matches(expected, sha, args.wait):
                raise ValueError("Push completed; live verification is still pending. Baseline was not advanced.")
            write_private(base_path, new_baseline)
            pending_path.unlink()
            print(f"VERIFIED {sha[:12]}: public HTML/JSON matches the release.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["bootstrap", "preview", "publish"])
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--wait", type=int, default=180, help="Seconds to wait for public Pages files")
    parser.add_argument("--consume", action="store_true", help="Discard this generated snapshot after the run")
    args = parser.parse_args()
    try:
        sync(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"SYNC HOLD: {error}", file=sys.stderr)
        return 1
    finally:
        snapshot, state_dir = args.snapshot.resolve(), args.state_dir.resolve()
        if (args.consume and not state_dir.is_relative_to(REPO) and snapshot.parent == state_dir
                and re.fullmatch(r'snapshot-\d{13}\.json', snapshot.name)):
            snapshot.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
