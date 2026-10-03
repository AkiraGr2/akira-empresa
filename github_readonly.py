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
MAX_FILE_BYTES = 40_000
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


def _decode_content(item: dict[str, Any]) -> str:
    encoded = str(item.get("content") or "").replace("\n", "")
    if not encoded:
        raise GitHubReadUpstreamError("file_content_unavailable")
    try:
        raw = base64.b64decode(encoded, validate=False)
    except (ValueError, TypeError) as exc:
        raise GitHubReadUpstreamError("file_content_decode_failed") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise GitHubReadValidationError("file_too_large")
    return raw.decode("utf-8", errors="replace")


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
) -> dict[str, Any]:
    """Read selected files plus a shallow root tree, without any write capability."""
    repo = _validate_repo(repo)
    max_files = max(1, min(int(max_files), MAX_FILES))
    selected = [_validate_path(p) for p in (paths or []) if str(p or "").strip()]
    selected = list(dict.fromkeys(selected))[:max_files]

    root = read_repo_path(repo, "", max_items=MAX_FILES)
    files = []
    total_bytes = 0
    for path in selected:
        result = read_repo_path(repo, path, max_items=MAX_FILES)
        if result.get("operation") != "read_file":
            files.append({
                "path": path,
                "status": "not_a_file",
            })
            continue
        size = int(result.get("size_bytes") or 0)
        if total_bytes + size > MAX_TOTAL_BYTES:
            files.append({
                "path": path,
                "status": "skipped_total_size_limit",
            })
            continue
        total_bytes += size
        files.append({
            "path": path,
            "status": "ok",
            "size_bytes": size,
            "content": result.get("content") or "",
        })

    return {
        "ok": True,
        "operation": "inspect_repository",
        "repository": repo,
        "branch": DEFAULT_BRANCH,
        "root": root.get("entries") or [],
        "files": files,
        "total_bytes": total_bytes,
        "limits": {
            "max_files": max_files,
            "max_file_bytes": MAX_FILE_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
        },
        "read_only": True,
    }
