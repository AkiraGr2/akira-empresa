"""Read-only GitHub gateway for Akira.

Security contract:
- Only allow-listed public repositories.
- Read-only: GET requests only.
- No git writes, branches, merges, or arbitrary URLs.
- Tight file/count/size limits.
- Never return credentials.
"""
from __future__ import annotations

import base64
import os
import re
from typing import Any


ALLOWED_REPOSITORIES = {
    "AkiraGr2/akira-v3-frontend",
    "AkiraGr2/akira-empresa",
}

DEFAULT_BRANCH = "main"
REQUEST_TIMEOUT_S = 8
MAX_FILES = 24
MAX_TOTAL_BYTES = 120_000
MAX_FILE_BYTES = 60_000
MAX_SEARCH_SOURCE_BYTES = 800_000
MAX_SEARCH_SNIPPET_BYTES = 18_000
MAX_SEARCH_MATCHES_PER_FILE = 8
MAX_SEARCH_CONTEXT_CHARS = 700
MAX_PATH_CHARS = 240

_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


class GitHubReadError(RuntimeError):
    """Base error for safe GitHub reads."""


class GitHubReadValidationError(GitHubReadError):
    """Invalid or unsafe repository/path input."""


class GitHubReadUpstreamError(GitHubReadError):
    """GitHub could not satisfy a read request."""


def _validate_repo(repo: str) -> str:
    value = str(repo or "").strip()
    if value not in ALLOWED_REPOSITORIES:
        raise GitHubReadValidationError("repository_not_allowlisted")
    return value


def _validate_path(path: str) -> str:
    value = str(path or "").strip().strip("/")
    if len(value) > MAX_PATH_CHARS:
        raise GitHubReadValidationError("path_too_long")
    if not value:
        return ""
    if ".." in value.split("/"):
        raise GitHubReadValidationError("parent_path_not_allowed")
    if not _SAFE_PATH_RE.fullmatch(value):
        raise GitHubReadValidationError("unsafe_path")
    return value


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Akira-Readonly-GitHub-Gateway",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str) -> Any:
    try:
        import requests
        response = requests.get(
            url,
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise GitHubReadUpstreamError("github_request_failed") from exc

    if response.status_code == 404:
        raise GitHubReadUpstreamError("not_found")
    if response.status_code == 403:
        raise GitHubReadUpstreamError("forbidden_or_rate_limited")
    if response.status_code >= 400:
        raise GitHubReadUpstreamError(f"github_http_{response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise GitHubReadUpstreamError("invalid_github_json") from exc


def _api_url(repo: str, path: str = "") -> str:
    safe_repo = _validate_repo(repo)
    safe_path = _validate_path(path)
    suffix = f"/{safe_path}" if safe_path else ""
    return f"https://api.github.com/repos/{safe_repo}/contents{suffix}?ref={DEFAULT_BRANCH}"


def _head_commit_sha(repo: str) -> str:
    safe_repo = _validate_repo(repo)
    data = _get_json(
        f"https://api.github.com/repos/{safe_repo}/git/ref/heads/{DEFAULT_BRANCH}"
    )
    sha = str(((data.get("object") or {}).get("sha")) if isinstance(data, dict) else "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise GitHubReadUpstreamError("invalid_head_commit_sha")
    return sha.lower()


def _decode_content(item: dict[str, Any]) -> str:
    return _decode_content_with_limit(item, MAX_FILE_BYTES)


def _decode_content_with_limit(item: dict[str, Any], max_bytes: int) -> str:
    encoded = str(item.get("content") or "").replace("\n", "")
    if not encoded:
        raise GitHubReadUpstreamError("file_content_unavailable")
    try:
        raw = base64.b64decode(encoded, validate=False)
    except (ValueError, TypeError) as exc:
        raise GitHubReadUpstreamError("file_content_decode_failed") from exc
    if len(raw) > max_bytes:
        raise GitHubReadValidationError("file_too_large")
    return raw.decode("utf-8", errors="replace")


def _search_oversized_file(
    item: dict[str, Any],
    queries: list[str],
) -> dict[str, Any]:
    source = _decode_content_with_limit(item, MAX_SEARCH_SOURCE_BYTES)
    normalized_queries = []
    for raw in queries or []:
        value = str(raw or "").strip()
        if value and value.lower() not in {q.lower() for q in normalized_queries}:
            normalized_queries.append(value[:120])
        if len(normalized_queries) >= 12:
            break

    matches = []
    seen = set()
    for query in normalized_queries:
        start = 0
        needle = query.lower()
        while len(matches) < MAX_SEARCH_MATCHES_PER_FILE:
            idx = source.lower().find(needle, start)
            if idx < 0:
                break
            start = idx + max(1, len(needle))
            left = max(0, idx - MAX_SEARCH_CONTEXT_CHARS)
            right = min(len(source), idx + len(query) + MAX_SEARCH_CONTEXT_CHARS)
            snippet = source[left:right]
            key = (left, right)
            if key not in seen:
                seen.add(key)
                matches.append({
                    "query": query,
                    "start_char": idx,
                    "line_start": source.count("\n", 0, idx) + 1,
                    "line_end": source.count("\n", 0, min(len(source), right)) + 1,
                    "evidence_kind": "direct_code_match",
                    "snippet": snippet,
                })
    payload = {
        "status": "ok",
        "mode": "targeted_snippets",
        "size_bytes": len(source.encode("utf-8")),
        "queries": normalized_queries,
        "matches": matches,
    }
    encoded_size = len(str(payload.get("matches") or "").encode("utf-8"))
    if encoded_size > MAX_SEARCH_SNIPPET_BYTES:
        # Keep deterministic, bounded evidence without exposing the whole file.
        kept = []
        used = 0
        for match in matches:
            cost = len(match["snippet"].encode("utf-8"))
            if used + cost > MAX_SEARCH_SNIPPET_BYTES:
                break
            kept.append(match)
            used += cost
        payload["matches"] = kept
        payload["truncated"] = len(kept) < len(matches)
    else:
        payload["truncated"] = False
    return payload


def read_repo_path(repo: str, path: str = "", max_items: int = MAX_FILES) -> dict[str, Any]:
    """Read a file or one directory level from an allow-listed repository."""
    repo = _validate_repo(repo)
    path = _validate_path(path)
    max_items = max(1, min(int(max_items), MAX_FILES))
    data = _get_json(_api_url(repo, path))

    if isinstance(data, dict) and data.get("type") == "file":
        content = _decode_content(data)
        return {
            "ok": True,
            "operation": "read_file",
            "repository": repo,
            "branch": DEFAULT_BRANCH,
            "path": path,
            "source_url": f"https://github.com/{repo}/blob/{DEFAULT_BRANCH}/{path}",
            "size_bytes": len(content.encode("utf-8")),
            "content": content,
        }

    if not isinstance(data, list):
        raise GitHubReadUpstreamError("unexpected_contents_shape")

    entries = []
    total = 0
    for item in data[:max_items]:
        entry = {
            "name": str(item.get("name") or ""),
            "path": str(item.get("path") or ""),
            "type": str(item.get("type") or ""),
            "size_bytes": int(item.get("size") or 0),
        }
        total += max(0, entry["size_bytes"])
        entries.append(entry)

    return {
        "ok": True,
        "operation": "list_directory",
        "repository": repo,
        "branch": DEFAULT_BRANCH,
        "path": path,
        "entries": entries,
        "count": len(entries),
        "truncated": len(data) > max_items,
        "listed_size_bytes": total,
    }


def inspect_repository(
    repo: str,
    paths: list[str] | None = None,
    max_files: int = 8,
    queries: list[str] | None = None,
) -> dict[str, Any]:
    """Read selected files plus targeted evidence from oversized files, read-only."""
    repo = _validate_repo(repo)
    max_files = max(1, min(int(max_files), MAX_FILES))
    selected = [_validate_path(p) for p in (paths or []) if str(p or "").strip()]
    selected = list(dict.fromkeys(selected))[:max_files]
    queries = [
        str(q or "").strip()[:120]
        for q in (queries or [])
        if str(q or "").strip()
    ][:12]

    head_commit_sha = _head_commit_sha(repo)
    root = read_repo_path(repo, "", max_items=MAX_FILES)
    files = []
    total_bytes = 0
    for path in selected:
        data = _get_json(_api_url(repo, path))
        if isinstance(data, dict) and data.get("type") == "file":
            size = int(data.get("size") or 0)
            if size <= MAX_FILE_BYTES:
                if total_bytes + size > MAX_TOTAL_BYTES:
                    files.append({
                        "path": path,
                        "status": "skipped_total_size_limit",
                        "source_url": f"https://github.com/{repo}/blob/{DEFAULT_BRANCH}/{path}",
                        "size_bytes": size,
                    })
                    continue
                content = _decode_content(data)
                total_bytes += size
                files.append({
                    "path": path,
                    "status": "ok",
                    "mode": "full_file",
                    "source_url": f"https://github.com/{repo}/blob/{DEFAULT_BRANCH}/{path}",
                    "size_bytes": size,
                    "content": content,
                })
            elif queries:
                evidence = _search_oversized_file(data, queries)
                matches = list(evidence.get("matches", []))
                # For targeted inspection, the total-return budget counts the
                # snippets exposed to the model, not the full source file.
                used = total_bytes
                kept = []
                for match in matches:
                    cost = len(str(match.get("snippet") or "").encode("utf-8"))
                    if used + cost > MAX_TOTAL_BYTES:
                        break
                    kept.append(match)
                    used += cost
                files.append({
                    "path": path,
                    "status": evidence.get("status", "ok") if kept else "no_targeted_evidence_within_limit",
                    "mode": evidence.get("mode", "targeted_snippets"),
                    "source_url": f"https://github.com/{repo}/blob/{DEFAULT_BRANCH}/{path}",
                    "size_bytes": size,
                    "queries": evidence.get("queries", []),
                    "matches": kept,
                    "truncated": bool(evidence.get("truncated")) or len(kept) < len(matches),
                })
                total_bytes = used
            else:
                files.append({
                    "path": path,
                    "status": "too_large_for_direct_read",
                    "mode": "metadata_only",
                    "source_url": f"https://github.com/{repo}/blob/{DEFAULT_BRANCH}/{path}",
                    "size_bytes": size,
                })
        elif isinstance(data, list):
            files.append({
                "path": path,
                "status": "not_a_file",
            })
        else:
            raise GitHubReadUpstreamError("unexpected_contents_shape")

    return {
        "ok": True,
        "operation": "inspect_repository",
        "repository": repo,
        "branch": DEFAULT_BRANCH,
        "head_commit_sha": head_commit_sha,
        "root": root.get("entries") or [],
        "files": files,
        "total_bytes": total_bytes,
        "limits": {
            "max_files": max_files,
            "max_file_bytes": MAX_FILE_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
            "max_search_source_bytes": MAX_SEARCH_SOURCE_BYTES,
            "max_search_matches_per_file": MAX_SEARCH_MATCHES_PER_FILE,
            "max_search_snippet_bytes": MAX_SEARCH_SNIPPET_BYTES,
        },
        "read_only": True,
    }
