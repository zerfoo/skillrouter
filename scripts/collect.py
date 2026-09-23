#!/usr/bin/env python3
"""Collect a licensed, deduplicated skills.sh training corpus.

This program reads untrusted skill text as data. It never executes a skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SKILLS_API = "https://skills.sh/api/v1/skills"
GITHUB_API = "https://api.github.com/repos"
ALLOWED_LICENSES = {"MIT", "Apache-2.0"}
MAX_RESPONSE = 12 * 1024 * 1024


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
                    raise ValueError(f"response too large: {url}")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError(f"expected JSON object: {url}")
                return value
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in {429, 503} or attempt == 4:
                raise RuntimeError(f"HTTP {error.code} from {url}") from error
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
        result = get_json(url, github_token, github=True)
        license_object = result.get("license") if result else None
        cache[source] = license_object.get("spdx_id") if isinstance(license_object, dict) else None
    return cache[source]


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
            for item in rows:
                if count >= limit:
                    break
                if not eligible_listing(item) or item["id"] in seen:
                    continue
                source = item["source"]
                license_id = repository_license(source, github_token, licenses)
                if license_id not in ALLOWED_LICENSES:
                    continue
                detail_url = f"{SKILLS_API}/{urllib.parse.quote(item['id'], safe='/')}"
                detail = get_json(detail_url, skills_token)
                content = skill_markdown(detail)
                if content is None:
                    continue
                digest = hashlib.sha256(content.encode()).hexdigest()
                if digest in seen_hashes:
                    continue
                row = {
                    "id": item["id"], "source": source,
                    "name": item.get("name", ""), "installs": item.get("installs", 0),
                    "license": license_id, "skill_sha256": digest,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100_000)
    parser.add_argument("--output", type=Path, default=Path("data/skills.jsonl"))
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    skills_token = os.environ.get("VERCEL_OIDC_TOKEN")
    github_token = os.environ.get("GITHUB_TOKEN")
    if not skills_token or not github_token:
        parser.error("VERCEL_OIDC_TOKEN and GITHUB_TOKEN are required")
    collect(args.limit, args.output, skills_token, github_token)


if __name__ == "__main__":
    main()
