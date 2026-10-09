"""F14 controlled GitHub gateway.

This module is the only F14 component allowed to mutate GitHub. It enforces:
- repository allow-list;
- base branch main is never written;
- action starts from an exact, freshly checked base SHA;
- one isolated branch per autonomy run;
- serial file writes;
- only create/modify text files under path policy;
- Draft PR only; never merge or force-push.
"""
from __future__ import annotations

import base64
import difflib
import hashlib
import os
import re
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import quote
from typing import Any, Mapping

from persistence.autonomy import (
    AUTONOMY_ALLOWED_REPOSITORIES,
    AUTONOMY_BASE_BRANCH,
    AUTONOMY_MAX_FILE_BYTES,
    validate_change,
    validate_path,
    validate_repository,
)


API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
REQUEST_TIMEOUT_S = 12
MAX_ARCHIVE_BYTES = 40_000_000
MAX_PR_TITLE = 200
MAX_PR_BODY = 10_000
BRANCH_PREFIX = "akira/autonomy/"


class ControlledGitHubError(RuntimeError):
    """Controlled GitHub gateway failure."""



def deterministic_modify_patch(path: str, source: str, find_text: str, replace_text: str) -> str:
    """Generate a canonical unified diff from one exact source replacement."""
    path = validate_path(path)
    if not isinstance(source, str):
        raise ControlledGitHubError(f"patch_source_unavailable:{path}")
    find_text = str(find_text or "")
    replace_text = str(replace_text if replace_text is not None else "")
    if not find_text:
        raise ControlledGitHubError(f"patch_find_empty:{path}")
    occurrences = source.count(find_text)
    if occurrences == 0:
        raise ControlledGitHubError(f"patch_anchor_not_found:{path}")
    if occurrences != 1:
        raise ControlledGitHubError(f"patch_anchor_not_unique:{path}")
    updated = source.replace(find_text, replace_text, 1)
    if updated == source:
        raise ControlledGitHubError(f"patch_noop:{path}")
    diff = "".join(difflib.unified_diff(
        source.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="\n",
    ))
    if not diff.startswith(f"--- a/{path}\n+++ b/{path}\n@@ "):
        raise ControlledGitHubError(f"patch_canonicalization_failed:{path}")
    return diff


def canonicalize_modify_patch(path: str, source: str, patch: str) -> str:
    """Canonicalize a modify patch against the exact authoritative source.

    Hunk coordinates are treated as untrusted metadata. The source text is
    authoritative; recovery is allowed only when the hunk body identifies one
    exact, unique old fragment. Final line numbers and diff syntax are generated
    deterministically by Python.
    """
    path = validate_path(path)
    patch = str(patch or "")
    lines = patch.splitlines(keepends=True)
    old_headers = [line.rstrip("\n") for line in lines if line.startswith("--- ")]
    new_headers = [line.rstrip("\n") for line in lines if line.startswith("+++ ")]
    hunk_indexes = [i for i, line in enumerate(lines) if line.startswith("@@")]
    hunk_pattern = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")
    if (
        len(old_headers) != 1
        or len(new_headers) != 1
        or old_headers[0].strip() != f"--- a/{path}"
        or new_headers[0].strip() != f"+++ b/{path}"
        or len(hunk_indexes) != 1
        or not hunk_pattern.fullmatch(lines[hunk_indexes[0]].rstrip("\n"))
    ):
        raise ControlledGitHubError(f"patch_invalid_hunk:{path}")

    body = lines[hunk_indexes[0] + 1:]
    if not body or any(not line.startswith((" ", "-", "+")) for line in body):
        raise ControlledGitHubError(f"patch_invalid_body:{path}")

    old_text = "".join(line[1:] for line in body if line.startswith((" ", "-")))
    new_text = "".join(line[1:] for line in body if line.startswith((" ", "+")))
    if not old_text or old_text == new_text:
        raise ControlledGitHubError(f"patch_not_recoverable:{path}")
    if source.count(old_text) == 1:
        return deterministic_modify_patch(path, source, old_text, new_text)

    # A generated unified diff may include repeated surrounding context (for
    # example, several blank lines near a file footer). If the complete hunk
    # context is not unique, fall back only to the exact removed lines, and
    # only when that removed block occurs exactly once in the authoritative
    # source. This keeps insertion/replacement deterministic and fail-closed.
    removed_text = "".join(line[1:] for line in body if line.startswith("-"))
    added_text = "".join(line[1:] for line in body if line.startswith("+"))
    if (
        removed_text
        and removed_text != added_text
        and source.count(removed_text) == 1
    ):
        return deterministic_modify_patch(path, source, removed_text, added_text)

    raise ControlledGitHubError(f"patch_anchor_not_unique:{path}")

def _token() -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise ControlledGitHubError("github_token_not_configured")
    return token


def _headers(require_token: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "Akira-Controlled-Autonomy/1.0",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif require_token:
        raise ControlledGitHubError("github_token_not_configured")
    return headers


def _request(method: str, url: str, require_token: bool = True, **kwargs) -> Any:
    try:
        import requests
        response = requests.request(
            method,
            url,
            headers=_headers(require_token=require_token),
            timeout=REQUEST_TIMEOUT_S,
            **kwargs,
        )
    except Exception as exc:
        raise ControlledGitHubError(f"github_request_failed:{type(exc).__name__}") from exc
    if response.status_code >= 400:
        detail = ""
        try:
            data = response.json()
            detail = str(data.get("message") or "")[:300] if isinstance(data, Mapping) else ""
        except Exception:
            pass
        raise ControlledGitHubError(f"github_http_{response.status_code}:{detail}")
    if response.status_code == 204:
        return None
    try:
        return response.json()
    except Exception as exc:
        raise ControlledGitHubError("github_invalid_json") from exc


def _validate_branch_name(branch: str) -> str:
    value = str(branch or "").strip()
    if not value or len(value) > 180:
        raise ControlledGitHubError("invalid_branch_name")
    if not value.startswith(BRANCH_PREFIX):
        raise ControlledGitHubError("branch_prefix_not_allowed")
    if ".." in value.split("/"):
        raise ControlledGitHubError("branch_path_not_allowed")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", value):
        raise ControlledGitHubError("branch_name_unsafe")
    return value


def branch_head(repository: str, branch: str) -> str:
    repo = validate_repository(repository)
    branch = str(branch or "").strip()
    data = _request(
        "GET",
        f"{API_ROOT}/repos/{repo}/git/ref/heads/{quote(branch, safe='')}",
        require_token=False,
    )
    sha = str(((data.get("object") or {}).get("sha")) if isinstance(data, Mapping) else "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise ControlledGitHubError("invalid_branch_head")
    return sha.lower()


def verify_existing_draft_action(repository: str, action: Mapping[str, Any]) -> dict[str, Any]:
    """Re-verify a previously created F14 branch/PR without writing to GitHub."""
    repo = validate_repository(repository)
    if not isinstance(action, Mapping) or action.get("repository") != repo:
        raise ControlledGitHubError("existing_action_repository_mismatch")
    if action.get("base_branch") != AUTONOMY_BASE_BRANCH or action.get("merged") is not False:
        raise ControlledGitHubError("existing_action_safety_metadata_invalid")
    branch = _validate_branch_name(action.get("branch_name"))
    expected_head = str(action.get("branch_head") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise ControlledGitHubError("existing_action_head_missing")
    current_head = branch_head(repo, branch)
    if current_head != expected_head:
        raise ControlledGitHubError("existing_branch_head_mismatch")

    pr_number = action.get("pr_number")
    try:
        pr_number = int(pr_number)
    except (TypeError, ValueError) as exc:
        raise ControlledGitHubError("existing_action_pr_number_invalid") from exc
    if pr_number <= 0:
        raise ControlledGitHubError("existing_action_pr_number_invalid")
    pr = _request("GET", f"{API_ROOT}/repos/{repo}/pulls/{pr_number}")
    if not isinstance(pr, Mapping):
        raise ControlledGitHubError("existing_pr_verification_invalid")
    base = pr.get("base") if isinstance(pr.get("base"), Mapping) else {}
    head = pr.get("head") if isinstance(pr.get("head"), Mapping) else {}
    pr_url = str(action.get("pr_url") or "").strip()
    if (
        str(pr.get("html_url") or "").strip() != pr_url
        or str(pr.get("state") or "") != "open"
        or pr.get("draft") is not True
        or pr.get("merged") is not False
        or str(base.get("ref") or "") != AUTONOMY_BASE_BRANCH
        or str(head.get("ref") or "") != branch
        or str(head.get("sha") or "").lower() != current_head
    ):
        raise ControlledGitHubError("existing_draft_pr_safety_invariant_failed")
    return {
        "branch_head_matches": True,
        "draft_pr": True,
        "merged": False,
        "base_branch": True,
        "pr_number": pr_number,
        "pr_url": pr_url,
    }


def fetch_text_file(repository: str, path: str, branch: str) -> dict[str, str]:
    repo = validate_repository(repository)
    path = validate_path(path)
    data = _request(
        "GET",
        f"{API_ROOT}/repos/{repo}/contents/{quote(path, safe='/')}?ref={quote(branch, safe='')}",
        require_token=False,
    )
    if not isinstance(data, Mapping) or data.get("type") != "file":
        raise ControlledGitHubError("github_content_not_file")
    encoded = str(data.get("content") or "").replace("\n", "")
    try:
        raw = base64.b64decode(encoded, validate=False)
    except Exception as exc:
        raise ControlledGitHubError("github_content_decode_failed") from exc
    if len(raw) > AUTONOMY_MAX_FILE_BYTES:
        raise ControlledGitHubError("file_too_large")
    return {
        "content": raw.decode("utf-8", errors="strict"),
        "sha": str(data.get("sha") or "").strip(),
        "path": path,
    }


def _download_archive(repository: str, ref: str, target: Path) -> str:
    repo = validate_repository(repository)
    try:
        import requests
        response = requests.get(
            f"{API_ROOT}/repos/{repo}/tarball/{quote(ref, safe='')}",
            headers=_headers(require_token=False),
            timeout=REQUEST_TIMEOUT_S,
            stream=True,
        )
    except Exception as exc:
        raise ControlledGitHubError(f"archive_request_failed:{type(exc).__name__}") from exc
    if response.status_code >= 400:
        raise ControlledGitHubError(f"archive_http_{response.status_code}")
    total = 0
    archive_path = target / "repo.tar.gz"
    with archive_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise ControlledGitHubError("archive_too_large")
            fh.write(chunk)
    return str(archive_path)


def _safe_extract(archive_path: str, target: Path) -> Path:
    root = None
    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            if member.islnk() or member.issym():
                raise ControlledGitHubError("archive_links_not_allowed")
            name = member.name.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise ControlledGitHubError("archive_path_traversal")
            parts = [p for p in name.split("/") if p]
            if not parts:
                continue
            if root is None:
                root = target / parts[0]
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if member.isfile():
                with tar.extractfile(member) as src, destination.open("wb") as dst:
                    if src is None:
                        raise ControlledGitHubError("archive_member_missing")
                    remaining = member.size
                    while remaining:
                        chunk = src.read(min(64 * 1024, remaining))
                        if not chunk:
                            raise ControlledGitHubError("archive_member_truncated")
                        dst.write(chunk)
                        remaining -= len(chunk)
        if root is None or not root.is_dir():
            raise ControlledGitHubError("archive_root_missing")
    return root


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def apply_unified_patch(source: str, patch: str, declared_path: str, operation: str) -> str:
    path = validate_path(declared_path)
    clean_change = validate_change({
        "path": path,
        "operation": operation,
        "reason": "internal",
        "patch": patch,
    })
    patch_lines = patch.splitlines(keepends=True)
    old_header = next((line for line in patch_lines if line.startswith("--- ")), None)
    new_header = next((line for line in patch_lines if line.startswith("+++ ")), None)
    if not old_header or not new_header:
        raise ControlledGitHubError("unified_headers_missing")

    old_ref = old_header[4:].strip().split("\t", 1)[0]
    new_ref = new_header[4:].strip().split("\t", 1)[0]
    expected_old = "/dev/null" if operation == "create" else f"a/{path}"
    expected_new = f"b/{path}"
    if old_ref != expected_old or new_ref != expected_new:
        raise ControlledGitHubError("patch_path_mismatch")

    if operation == "create" and source:
        raise ControlledGitHubError("create_target_already_exists")
    if operation == "modify" and not source and " -0,0 " not in patch and "-0,0 " not in patch:
        raise ControlledGitHubError("modify_target_missing")

    source_lines = source.splitlines(keepends=True)
    output: list[str] = []
    source_index = 0
    found_hunk = False
    i = 0
    while i < len(patch_lines):
        line = patch_lines[i]
        if line.startswith("@@ "):
            found_hunk = True
            match = _HUNK_RE.match(line.rstrip("\n"))
            if not match:
                raise ControlledGitHubError("invalid_hunk_header")
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_count = int(match.group(4) or "1")
            target_index = max(0, old_start - 1)
            if target_index < source_index or target_index > len(source_lines):
                raise ControlledGitHubError("hunk_out_of_range")
            output.extend(source_lines[source_index:target_index])
            source_index = target_index
            consumed_old = 0
            produced_new = 0
            i += 1
            while i < len(patch_lines) and not patch_lines[i].startswith("@@ "):
                hline = patch_lines[i]
                if hline == "\\ No newline at end of file\n" or hline == "\\ No newline at end of file":
                    raise ControlledGitHubError("no_newline_marker_not_supported")
                if not hline:
                    raise ControlledGitHubError("empty_patch_line")
                prefix = hline[0]
                payload = hline[1:]
                if prefix == " ":
                    if source_index >= len(source_lines) or source_lines[source_index] != payload:
                        raise ControlledGitHubError("patch_context_mismatch")
                    output.append(source_lines[source_index])
                    source_index += 1
                    consumed_old += 1
                    produced_new += 1
                elif prefix == "-":
                    if source_index >= len(source_lines) or source_lines[source_index] != payload:
                        raise ControlledGitHubError("patch_delete_mismatch")
                    source_index += 1
                    consumed_old += 1
                elif prefix == "+":
                    output.append(payload)
                    produced_new += 1
                else:
                    raise ControlledGitHubError("invalid_hunk_line")
                i += 1
            if consumed_old != old_count or produced_new != new_count:
                raise ControlledGitHubError("hunk_count_mismatch")
            continue
        i += 1

    if not found_hunk:
        raise ControlledGitHubError("no_hunks")
    output.extend(source_lines[source_index:])
    result = "".join(output)
    if len(result.encode("utf-8")) > AUTONOMY_MAX_FILE_BYTES:
        raise ControlledGitHubError("result_file_too_large")
    return result


def sandbox_changes(
    repository: str,
    base_sha: str,
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    repo = validate_repository(repository)
    if not re.fullmatch(r"[0-9a-fA-F]{40}", str(base_sha or "")):
        raise ControlledGitHubError("invalid_base_sha")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 4:
        raise ControlledGitHubError("invalid_change_count")

    with tempfile.TemporaryDirectory(prefix="akira-f14-") as temp:
        target = Path(temp)
        archive = _download_archive(repo, base_sha, target)
        root = _safe_extract(archive, target)
        results = []
        for raw_change in changes:
            change = validate_change(raw_change)
            path = change["path"]
            file_path = root / path
            try:
                file_path.resolve().relative_to(root.resolve())
            except ValueError as exc:
                raise ControlledGitHubError("sandbox_path_escape") from exc

            source = ""
            existed = file_path.exists()
            if change["operation"] == "modify":
                if not existed or not file_path.is_file():
                    raise ControlledGitHubError(f"modify_target_missing:{path}")
                data = file_path.read_bytes()
                if len(data) > AUTONOMY_MAX_FILE_BYTES:
                    raise ControlledGitHubError(f"source_file_too_large:{path}")
                source = data.decode("utf-8", errors="strict")
            elif existed:
                raise ControlledGitHubError(f"create_target_exists:{path}")

            if change["operation"] == "modify":
                try:
                    canonical_patch = canonicalize_modify_patch(path, source, change["patch"])
                except ControlledGitHubError:
                    raise
                change = {**change, "patch": canonical_patch}

            result_text = apply_unified_patch(source, change["patch"], path, change["operation"])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(result_text, encoding="utf-8")
            results.append({
                "path": path,
                "operation": change["operation"],
                "existed": existed,
                "sha256": hashlib.sha256(result_text.encode("utf-8")).hexdigest(),
                "bytes": len(result_text.encode("utf-8")),
            })
        return {
            "base_sha": base_sha.lower(),
            "files": results,
            "root_verified": root.is_dir(),
            "sandbox_mode": "isolated_archive",
        }


def controlled_apply(
    repository: str,
    base_sha: str,
    run_id: str,
    changes: list[dict[str, Any]],
    title: str,
    body: str,
    expected_hashes: Mapping[str, str],
) -> dict[str, Any]:
    repo = validate_repository(repository)
    if not re.fullmatch(r"[0-9a-fA-F]{40}", str(base_sha or "")):
        raise ControlledGitHubError("invalid_base_sha")
    if len(changes) > 4:
        raise ControlledGitHubError("too_many_changes")
    branch = _validate_branch_name(f"{BRANCH_PREFIX}{run_id}")
    if not str(title or "").strip():
        raise ControlledGitHubError("pr_title_required")
    title = str(title).strip()[:MAX_PR_TITLE]
    body = str(body or "").strip()[:MAX_PR_BODY]

    main_head = branch_head(repo, AUTONOMY_BASE_BRANCH)
    if main_head != base_sha.lower():
        raise ControlledGitHubError("base_branch_changed_since_approval")

    # This branch is intentionally derived from the exact verified base SHA.
    _request(
        "POST",
        f"{API_ROOT}/repos/{repo}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": base_sha.lower()},
    )

    commits = []
    expected_branch_head = base_sha.lower()
    for raw_change in changes:
        change = validate_change(raw_change)
        current_branch_head = branch_head(repo, branch)
        if current_branch_head != expected_branch_head:
            raise ControlledGitHubError("unexpected_branch_head_change")
        path = change["path"]

        if change["operation"] == "create":
            source = ""
            file_sha = None
            try:
                existing = fetch_text_file(repo, path, branch)
                if existing:
                    raise ControlledGitHubError("create_target_already_exists")
            except ControlledGitHubError as exc:
                if "404" not in str(exc):
                    # The contents endpoint reports HTTP 404 for a genuinely new path.
                    # The wrapper intentionally does not collapse unrelated failures.
                    raise
            new_content = apply_unified_patch(source, change["patch"], path, "create")
            digest = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
            if digest != expected_hashes.get(path):
                raise ControlledGitHubError(f"sandbox_hash_mismatch:{path}")
            encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
            data = _request(
                "PUT",
                f"{API_ROOT}/repos/{repo}/contents/{quote(path, safe='/')}",
                json={
                    "message": f"f14 autonomy: apply {path}",
                    "content": encoded,
                    "branch": branch,
                },
            )
        else:
            current = fetch_text_file(repo, path, branch)
            # validate_change trims patch text, which can remove the final newline from
            # a context line. Re-canonicalize against the exact branch contents before
            # applying so the patch context and sandbox result remain byte-consistent.
            canonical_patch = canonicalize_modify_patch(path, current["content"], change["patch"])
            new_content = apply_unified_patch(current["content"], canonical_patch, path, "modify")
            digest = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
            if digest != expected_hashes.get(path):
                raise ControlledGitHubError(f"sandbox_hash_mismatch:{path}")
            encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
            data = _request(
                "PUT",
                f"{API_ROOT}/repos/{repo}/contents/{quote(path, safe='/')}",
                json={
                    "message": f"f14 autonomy: apply {path}",
                    "content": encoded,
                    "branch": branch,
                    "sha": current["sha"],
                },
            )

        commit_sha = str(((data.get("commit") or {}).get("sha")) if isinstance(data, Mapping) else "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
            raise ControlledGitHubError("invalid_write_commit_sha")
        commit_sha = commit_sha.lower()
        expected_branch_head = commit_sha
        if branch_head(repo, branch) != expected_branch_head:
            raise ControlledGitHubError("write_not_visible_on_branch")
        commits.append({"path": path, "commit_sha": commit_sha})

    pr_data = _request(
        "POST",
        f"{API_ROOT}/repos/{repo}/pulls",
        json={
            "title": title,
            "body": body,
            "head": branch,
            "base": AUTONOMY_BASE_BRANCH,
            "draft": True,
        },
    )
    pr_number = int(pr_data.get("number") or 0)
    pr_url = str(pr_data.get("html_url") or "").strip()
    if pr_number <= 0 or not pr_url:
        raise ControlledGitHubError("draft_pr_not_confirmed")
    verified = _request("GET", f"{API_ROOT}/repos/{repo}/pulls/{pr_number}")
    if not isinstance(verified, Mapping):
        raise ControlledGitHubError("pr_verification_invalid")
    if bool(verified.get("merged")) or verified.get("base", {}).get("ref") != AUTONOMY_BASE_BRANCH:
        raise ControlledGitHubError("pr_safety_invariant_failed")

    return {
        "repository": repo,
        "base_branch": AUTONOMY_BASE_BRANCH,
        "base_sha": base_sha.lower(),
        "branch_name": branch,
        "branch_head": expected_branch_head,
        "commits": commits,
        "pr_number": pr_number,
        "pr_url": pr_url,
        "pr_state": str(verified.get("state") or ""),
        "pr_draft": bool(verified.get("draft")),
        "merged": bool(verified.get("merged")),
    }
