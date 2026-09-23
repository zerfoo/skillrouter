#!/usr/bin/env python3
"""Collect a licensed, deduplicated skills.sh training corpus.

This program reads untrusted skill text as data. It never executes a skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SKILLS_API = "https://skills.sh/api/v1/skills"
GITHUB_API = "https://api.github.com/repos"
ALLOWED_LICENSES = {"MIT", "Apache-2.0"}
MAX_RESPONSE = 12 * 1024 * 1024


class ResponseTooLarge(ValueError):
    pass


class HTTPStatusError(RuntimeError):
    def __init__(self, code: int, url: str):
        self.code = code
        super().__init__(f"HTTP {code} from {url}")


def get_json(url: str, token: str, *, github: bool = False) -> dict | None:
    headers = {
        "Accept": "application/vnd.github+json" if github else "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "zerfoo-skillrouter-collector/0.1",
    }
    for attempt in range(5):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise ResponseTooLarge(f"response too large: {url}")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError(f"expected JSON object: {url}")
                return value
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in {429, 503} or attempt == 4:
                raise HTTPStatusError(error.code, url) from error
            delay = min(60, int(error.headers.get("Retry-After", "1")))
            time.sleep(max(1, delay))
        except (TimeoutError, urllib.error.URLError) as error:
            if attempt == 4:
                raise RuntimeError(f"request failed: {url}") from error
            time.sleep(2**attempt)
    raise AssertionError("retry loop exhausted")


def eligible_listing(item: dict) -> bool:
    source = item.get("source")
    identifier = item.get("id")
    return (
        item.get("sourceType") == "github"
        and item.get("isDuplicate") is not True
        and isinstance(source, str)
        and len(source.split("/")) == 2
        and isinstance(identifier, str)
        and identifier.startswith(source + "/")
    )


def skill_markdown(detail: dict | None) -> str | None:
    if not detail or not isinstance(detail.get("files"), list):
        return None
    for file in detail["files"]:
        if file.get("path") == "SKILL.md" and isinstance(file.get("contents"), str):
            content = file["contents"].strip()
            return content if content else None
    return None


def existing_keys(path: Path) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    hashes: set[str] = set()
    if not path.exists():
        return ids, hashes
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
                ids.add(record["id"])
                hashes.add(record["skill_sha256"])
            except (ValueError, KeyError) as error:
                raise ValueError(f"invalid corpus line {line_number}") from error
    return ids, hashes


def repository_license(source: str, github_token: str, cache: dict[str, str | None]) -> str | None:
    if source not in cache:
        owner, repo = source.split("/")
        url = f"{GITHUB_API}/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/license"
        try:
            result = get_json(url, github_token, github=True)
        except HTTPStatusError as error:
            if error.code != 451:
                raise
            result = None
        license_object = result.get("license") if result else None
        cache[source] = license_object.get("spdx_id") if isinstance(license_object, dict) else None
    return cache[source]


def fetch_skill(item: dict, skills_token: str) -> tuple[dict, str | None]:
    # Six workers with a per-request pause keep detail reads below the
    # documented 600/minute authenticated limit even on fast connections.
    time.sleep(0.7)
    detail_url = f"{SKILLS_API}/{urllib.parse.quote(item['id'], safe='/')}"
    try:
        return item, skill_markdown(get_json(detail_url, skills_token))
    except (ResponseTooLarge, HTTPStatusError) as error:
        if isinstance(error, HTTPStatusError) and error.code != 400:
            raise
        print(f"skipping unavailable detail: {item['id']} ({error})", file=sys.stderr)
        return item, None


def collect(limit: int, output: Path, skills_token: str, github_token: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    cache_path = output.with_suffix(".licenses.json")
    licenses = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    seen, seen_hashes = existing_keys(output)
    count = len(seen)
    page = 0
    with output.open("a", encoding="utf-8") as stream:
        while count < limit:
            url = f"{SKILLS_API}?view=all-time&page={page}&per_page=500"
            listing = get_json(url, skills_token)
            if listing is None or not isinstance(listing.get("data"), list):
                raise RuntimeError(f"invalid catalog page {page}")
            rows = listing["data"]
            if not rows:
                break
            candidates = []
            for item in rows:
                if eligible_listing(item) and item["id"] not in seen:
                    if repository_license(item["source"], github_token, licenses) in ALLOWED_LICENSES:
                        candidates.append(item)
            with ThreadPoolExecutor(max_workers=6) as pool:
                for item, content in pool.map(lambda candidate: fetch_skill(candidate, skills_token), candidates):
                    if count >= limit:
                        break
                    if content is None:
                        continue
                    digest = hashlib.sha256(content.encode()).hexdigest()
                    if digest in seen_hashes:
                        continue
                    row = {
                        "id": item["id"], "source": item["source"],
                        "name": item.get("name", ""), "installs": item.get("installs", 0),
                        "license": licenses[item["source"]], "skill_sha256": digest,
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "skill_md": content,
                    }
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    seen.add(item["id"])
                    seen_hashes.add(digest)
                    count += 1
            stream.flush()
            cache_path.write_text(json.dumps(licenses, sort_keys=True))
            print(f"page={page} eligible={count} listed_total={listing.get('pagination', {}).get('total', '?')}", file=sys.stderr)
            if not listing.get("pagination", {}).get("hasMore"):
                break
            page += 1
    digest = hashlib.sha256()
    with output.open("rb") as corpus:
        for chunk in iter(lambda: corpus.read(1024 * 1024), b""):
            digest.update(chunk)
    corpus_digest = digest.hexdigest()
    print(json.dumps({"records": count, "sha256": corpus_digest, "output": str(output)}))


def load_oidc_token(path: Path = Path(".env.local")) -> str | None:
    """Read the linked project's local token without printing it."""
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        if line.startswith("VERCEL_OIDC_TOKEN="):
            return line.partition("=")[2].strip().strip('"').strip("'") or None
    return None


def load_github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100_000)
    parser.add_argument("--output", type=Path, default=Path("data/skills.jsonl"))
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    skills_token = os.environ.get("VERCEL_OIDC_TOKEN") or load_oidc_token()
    github_token = load_github_token()
    if not skills_token or not github_token:
        parser.error("VERCEL_OIDC_TOKEN and GITHUB_TOKEN are required")
    collect(args.limit, args.output, skills_token, github_token)


if __name__ == "__main__":
    main()
