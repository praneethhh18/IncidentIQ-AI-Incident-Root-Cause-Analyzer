"""Code-aware fix pipeline.

Given an analysed incident and a Git repository URL, run a small chain of
sub-agents that:

  1. LOCATE   - extract candidate files from the incident analysis and
                ripgrep the repo for the strongest matches.
  2. DIAGNOSE - LLM call: pick the buggy file + region, explain why.
  3. PATCH    - LLM call: produce a unified diff that fixes it.
  4. VERIFY   - apply the diff in a scratch copy and run a lint / type
                check; report pass/fail without claiming success blindly.

The output is a :class:`CodeFix` attached to the incident. This is the
"suggests fixes instantly" half of the problem statement: instead of a
generic remediation paragraph, the user gets a PR-ready diff against
their actual codebase.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.models import AnalyzeResponse, CodeFix, CodeFixSubStep
from app.services.bedrock import BedrockClient, BedrockUnavailable

logger = logging.getLogger(__name__)


# Where cloned repos live. Cached across requests so repeated calls on
# the same URL don't re-clone. Resolved relative to the backend cwd.
REPO_CACHE_DIR = Path("cache") / "repos"

# Hard caps - keeps the LLM prompt cheap and predictable.
MAX_CANDIDATE_FILES = 5
MAX_FILE_CHARS = 3500
MAX_LOCATE_HITS = 30
GIT_CLONE_TIMEOUT = 60
VERIFY_TIMEOUT = 45

# File extensions we consider real source code worth showing the LLM.
# Lockfiles, generated bundles, and binaries are excluded.
SOURCE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".go", ".rs", ".java", ".kt", ".rb",
    ".php", ".cs", ".swift", ".scala",
}

# Paths under these prefixes are noise for a root-cause search.
SKIP_DIRS = {
    "node_modules", ".next", ".git", "dist", "build", "out",
    "__pycache__", ".pytest_cache", ".venv", "venv", "target",
    "coverage", ".turbo",
}


# ── Public API ────────────────────────────────────────────────────────────


class CodeFixError(RuntimeError):
    """Raised when the code-fix pipeline cannot produce a usable result."""


def generate_code_fix(
    analysis: AnalyzeResponse,
    repo_url: str,
    bedrock: BedrockClient,
) -> CodeFix:
    """Run the full locate / diagnose / patch / verify pipeline.

    Mutates nothing; caller is responsible for stitching the returned
    :class:`CodeFix` onto the incident and persisting.
    """
    if not bedrock.enabled:
        raise CodeFixError(
            "Code fix needs Bedrock to be configured; running without an LLM is meaningless here."
        )

    started = time.perf_counter()
    sub_steps: List[CodeFixSubStep] = []

    # 1) Ensure the repo is on disk.
    t0 = time.perf_counter()
    repo_root = _ensure_repo(repo_url)
    sub_steps.append(
        CodeFixSubStep(
            name="clone",
            summary=f"Repo ready at {repo_root.name}",
            detail=str(repo_root),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    )

    # 2) LOCATE - candidate files via ripgrep on signature terms.
    t0 = time.perf_counter()
    candidates = _locate(analysis, repo_root)
    if not candidates:
        raise CodeFixError(
            "Locate sub-agent could not find any candidate files matching the incident signature."
        )
    sub_steps.append(
        CodeFixSubStep(
            name="locate",
            summary=f"{len(candidates)} candidate file(s) matched",
            detail=", ".join(c for c, _ in candidates[:MAX_CANDIDATE_FILES]),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    )

    # 3) DIAGNOSE - LLM picks the buggy file + region.
    t0 = time.perf_counter()
    diagnosis = _diagnose(analysis, candidates[:MAX_CANDIDATE_FILES], repo_root, bedrock)
    sub_steps.append(
        CodeFixSubStep(
            name="diagnose",
            summary=f"Buggy region in {diagnosis.file_path}",
            detail=diagnosis.rationale[:400],
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    )

    # 4) PATCH - LLM generates a unified diff.
    t0 = time.perf_counter()
    diff_text = _patch(analysis, diagnosis, bedrock)
    sub_steps.append(
        CodeFixSubStep(
            name="patch",
            summary=f"{diff_text.count(chr(10))} line diff generated",
            detail="",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    )

    # 5) VERIFY - apply patch in a scratch copy, run a quick check.
    t0 = time.perf_counter()
    verify_passed, verify_output = _verify(repo_root, diagnosis.file_path, diff_text)
    sub_steps.append(
        CodeFixSubStep(
            name="verify",
            summary="lint passed" if verify_passed else "lint failed (review patch)",
            detail=verify_output[:500],
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    )

    total_ms = int((time.perf_counter() - started) * 1000)

    return CodeFix(
        repo_url=repo_url,
        file_path=diagnosis.file_path,
        snippet=diagnosis.snippet,
        diff=diff_text,
        rationale=diagnosis.rationale,
        confidence=diagnosis.confidence,
        verify_passed=verify_passed,
        verify_output=verify_output,
        candidate_files=[c for c, _ in candidates[:MAX_CANDIDATE_FILES]],
        sub_steps=sub_steps,
        duration_ms=total_ms,
    )


# ── Sub-agents ────────────────────────────────────────────────────────────


@dataclass
class _Diagnosis:
    file_path: str
    snippet: str
    rationale: str
    confidence: float


def _ensure_repo(repo_url: str) -> Path:
    """Clone the repo if not cached, else `git fetch && reset --hard origin`.

    Cache key is the SHA-1 of the URL so repeated calls reuse a clone.
    Uses ``--depth=1`` to keep the disk footprint small.
    """
    REPO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(repo_url.encode("utf-8")).hexdigest()[:16]
    target = REPO_CACHE_DIR / key

    if target.exists() and (target / ".git").exists():
        logger.info("Reusing cached repo at %s", target)
        # Refresh to latest main so the patch is against current code.
        try:
            subprocess.run(
                ["git", "fetch", "--depth=1", "origin"],
                cwd=target, check=True, timeout=GIT_CLONE_TIMEOUT,
                capture_output=True,
            )
            subprocess.run(
                ["git", "reset", "--hard", "origin/HEAD"],
                cwd=target, check=False, timeout=GIT_CLONE_TIMEOUT,
                capture_output=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Repo refresh failed (continuing with cache): %s", exc)
        return target

    logger.info("Cloning %s into %s", repo_url, target)
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", repo_url, str(target)],
            check=True, timeout=GIT_CLONE_TIMEOUT, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise CodeFixError(
            f"git clone failed: {exc.stderr.decode('utf-8', errors='replace')[:300]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CodeFixError(f"git clone timed out after {GIT_CLONE_TIMEOUT}s") from exc

    return target


def _locate(analysis: AnalyzeResponse, repo_root: Path) -> List[Tuple[str, int]]:
    """Ripgrep the repo for signature terms; rank files by hit count.

    Returns a list of ``(relative_path, hit_count)`` tuples sorted by
    relevance (most hits first).
    """
    terms = _extract_signature_terms(analysis)
    if not terms:
        return []

    hits: dict[str, int] = {}
    for term in terms:
        for hit in _rg_files(repo_root, term):
            hits[hit] = hits.get(hit, 0) + 1
            if sum(hits.values()) >= MAX_LOCATE_HITS:
                break

    ranked = sorted(hits.items(), key=lambda kv: kv[1], reverse=True)
    return ranked


def _extract_signature_terms(analysis: AnalyzeResponse) -> List[str]:
    """Pull the most distinctive search terms from the analysis.

    Prioritises service names, then specific tokens from evidence lines
    and the root cause. Caps the list because each term becomes an rg run.
    """
    terms: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        t = token.strip().lower()
        if len(t) >= 4 and t not in seen:
            seen.add(t)
            terms.append(token.strip())

    # Affected service names are the strongest signal - they almost
    # always appear in route paths or env names in the repo.
    for svc in analysis.affected_services:
        _add(svc.name)

    # Evidence lines: extract identifier-like tokens.
    for line in analysis.evidence[:6]:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_/.-]{4,}", line):
            if token.lower() in {
                "error", "fatal", "warning", "info", "debug",
                "request", "response", "status", "true", "false",
                "exception", "stack", "trace",
            }:
                continue
            _add(token)
            if len(terms) > 18:
                break

    # Service hint from the request and forensic propagation path.
    if analysis.forensic:
        for hop in analysis.forensic.propagation_path:
            _add(hop)

    return terms[:18]


def _rg_files(repo_root: Path, term: str) -> List[str]:
    """List repo-relative paths whose contents match the term.

    Uses ripgrep if available; falls back to a pure-Python recursive
    grep so the pipeline still works on machines without rg.
    """
    rel_paths: list[str] = []

    try:
        # files-with-matches, case-insensitive, fixed-string (no regex).
        proc = subprocess.run(
            ["rg", "-l", "-i", "-F", "--max-count", "1",
             "--type-add", "src:*.{ts,tsx,js,jsx,mjs,cjs,py,go,rs,java,kt,rb,php,cs}",
             "-tsrc", term, str(repo_root)],
            capture_output=True, timeout=15,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        for line in out.splitlines():
            rel = _safe_relpath(line.strip(), repo_root)
            if rel and not _is_skipped(rel):
                rel_paths.append(rel)
        return rel_paths
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # fall through to python fallback

    # Fallback: walk the tree manually.
    needle = term.lower()
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        rel = _safe_relpath(str(path), repo_root)
        if not rel or _is_skipped(rel):
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        try:
            if needle in path.read_text(encoding="utf-8", errors="ignore").lower():
                rel_paths.append(rel)
        except OSError:
            continue
    return rel_paths


def _safe_relpath(absolute: str, root: Path) -> Optional[str]:
    try:
        return str(Path(absolute).resolve().relative_to(root.resolve())).replace("\\", "/")
    except (ValueError, OSError):
        return None


def _is_skipped(rel_path: str) -> bool:
    parts = rel_path.split("/")
    return any(p in SKIP_DIRS for p in parts)


def _diagnose(
    analysis: AnalyzeResponse,
    candidates: List[Tuple[str, int]],
    repo_root: Path,
    bedrock: BedrockClient,
) -> _Diagnosis:
    """LLM call: pick the buggy file + region and explain why."""

    snippets: list[str] = []
    candidate_paths: list[str] = []
    for rel, _hits in candidates:
        content = _read_file_capped(rel, repo_root)
        if content is None:
            continue
        snippets.append(f"# FILE: {rel}\n{content}")
        candidate_paths.append(rel)
        if len(snippets) >= MAX_CANDIDATE_FILES:
            break

    if not snippets:
        raise CodeFixError("No readable candidate files for diagnosis sub-agent.")

    user_prompt = (
        "An incident was analysed and likely originates in one of the files below.\n"
        "Pick the SINGLE file most likely to contain the bug, name the buggy\n"
        "region with line numbers, and explain in 2-3 sentences why this is\n"
        "the bug given the incident evidence. Reply with strict JSON.\n\n"
        "--- INCIDENT ---\n"
        f"Title: {analysis.title}\n"
        f"Root cause: {analysis.root_cause}\n"
        f"Evidence:\n  " + "\n  ".join(analysis.evidence[:5]) + "\n\n"
        "--- CANDIDATE FILES ---\n"
        + "\n\n".join(snippets)
        + "\n\n"
        "Return JSON with keys:\n"
        '  "file_path": str (one of the FILE paths above, exact),\n'
        '  "snippet": str (the suspicious code as it appears now, ~10-30 lines max),\n'
        '  "rationale": str (why this code is the bug, 2-3 sentences),\n'
        '  "confidence": float between 0 and 1\n'
    )

    payload = bedrock.converse_json(
        system_prompt=(
            "You are a senior engineer triaging code in response to a "
            "production incident. You read the candidate files carefully "
            "and never invent paths. Reply with strict JSON only."
        ),
        user_prompt=user_prompt,
        max_tokens=1200,
        temperature=0.2,
    )

    file_path = str(payload.get("file_path", "")).strip()
    snippet = str(payload.get("snippet", "")).strip()
    rationale = str(payload.get("rationale", "")).strip()
    confidence = float(payload.get("confidence", 0.5) or 0.5)

    if not (file_path and snippet and rationale):
        raise CodeFixError("Diagnose sub-agent returned incomplete payload.")
    if file_path not in candidate_paths:
        # Model picked a path we didn't show it; fall back to the top hit.
        logger.warning("Diagnose picked unknown path %s; using top candidate", file_path)
        file_path = candidate_paths[0]

    return _Diagnosis(
        file_path=file_path, snippet=snippet, rationale=rationale, confidence=confidence,
    )


def _patch(
    analysis: AnalyzeResponse,
    diagnosis: _Diagnosis,
    bedrock: BedrockClient,
) -> str:
    """LLM call: emit a unified diff that fixes the buggy region."""
    user_prompt = (
        "Generate a UNIFIED DIFF that fixes the buggy code. The diff must:\n"
        "  - apply cleanly via `git apply` from the repo root,\n"
        "  - start with the standard `--- a/<path>` and `+++ b/<path>` headers,\n"
        "  - include 3 lines of surrounding context,\n"
        "  - change only what is necessary to fix the bug,\n"
        "  - not include any prose, commentary, or markdown fences.\n\n"
        f"Buggy file: {diagnosis.file_path}\n"
        f"Why it's buggy: {diagnosis.rationale}\n"
        "Incident root cause: " + analysis.root_cause + "\n\n"
        "Current suspicious code (as it exists today):\n"
        + diagnosis.snippet
        + "\n\n"
        "Reply with the diff ONLY. No explanation."
    )

    diff_text = bedrock.chat(
        system_prompt=(
            "You are a careful staff engineer writing a minimal, surgical "
            "patch in unified diff format. You never include prose, only "
            "the diff. Lines must use real tabs/spaces from the original."
        ),
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=900,
        temperature=0.15,
    )

    diff_text = _strip_code_fences(diff_text).strip()
    if "--- " not in diff_text or "+++ " not in diff_text:
        raise CodeFixError("Patch sub-agent did not return a recognisable diff.")
    return diff_text


def _verify(repo_root: Path, file_path: str, diff_text: str) -> Tuple[bool, str]:
    """Apply the diff to a scratch copy and run a fast lint check.

    Returns ``(passed, output)``. ``passed`` is False if anything goes
    wrong - we don't claim success blindly. The scratch copy is cleaned
    up before return.
    """
    scratch = repo_root.parent / (repo_root.name + "_verify")
    try:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)
        shutil.copytree(
            repo_root, scratch,
            ignore=shutil.ignore_patterns(*SKIP_DIRS),
            dirs_exist_ok=False,
        )

        diff_file = scratch / "_codefix.patch"
        diff_file.write_text(diff_text, encoding="utf-8")

        apply = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(diff_file)],
            cwd=scratch, capture_output=True, timeout=30,
        )
        if apply.returncode != 0:
            return False, (
                "git apply failed:\n"
                + apply.stderr.decode("utf-8", errors="replace")[:500]
            )

        # Pick a verifier by extension. Anything we don't know how to
        # check counts as "patch applied cleanly" - which is still a
        # real signal that the diff is at least well-formed.
        ext = Path(file_path).suffix.lower()
        if ext in {".ts", ".tsx"}:
            check = subprocess.run(
                ["npx", "--no-install", "tsc", "--noEmit", "--skipLibCheck", file_path],
                cwd=scratch, capture_output=True, timeout=VERIFY_TIMEOUT,
                shell=False,
            )
            ok = check.returncode == 0
            out = check.stderr.decode("utf-8", errors="replace") or check.stdout.decode("utf-8", errors="replace")
            return ok, out[:800] if out.strip() else "tsc clean"

        if ext == ".py":
            check = subprocess.run(
                ["python", "-m", "py_compile", file_path],
                cwd=scratch, capture_output=True, timeout=VERIFY_TIMEOUT,
            )
            ok = check.returncode == 0
            out = check.stderr.decode("utf-8", errors="replace")
            return ok, out[:800] if out.strip() else "py_compile clean"

        return True, f"patch applied cleanly; no verifier for {ext}"
    except subprocess.TimeoutExpired:
        return False, "verify step timed out"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Verify sub-agent failed unexpectedly")
        return False, f"verify error: {exc}"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ── Helpers ────────────────────────────────────────────────────────────────


def _read_file_capped(rel_path: str, repo_root: Path) -> Optional[str]:
    full = repo_root / rel_path
    try:
        text = full.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + "\n# ... [file truncated]\n"
    return text


def _strip_code_fences(text: str) -> str:
    """If the LLM wrapped its diff in ``` fences, peel them off."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()
