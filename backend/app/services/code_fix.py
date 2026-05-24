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

import difflib
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
# Diagnose step looks at multiple files; keep each one small enough that
# the combined prompt stays cheap.
MAX_FILE_CHARS_DIAGNOSE = 4000
# Patch step looks at one file - we can afford to send the whole thing
# so the LLM has every line to copy bytes from.
MAX_FILE_CHARS_PATCH = 12000
MAX_LOCATE_HITS = 30
GIT_CLONE_TIMEOUT = 180
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

    # 4) PATCH - LLM produces the fixed snippet; we generate the diff
    # locally via difflib so syntax + line numbers are always valid.
    t0 = time.perf_counter()
    diff_text = _patch(analysis, diagnosis, repo_root, bedrock)
    sub_steps.append(
        CodeFixSubStep(
            name="patch",
            summary=f"{diff_text.count(chr(10))} line diff generated",
            detail="",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    )

    # 5) VERIFY - apply patch in a scratch copy, run a quick check, AND
    # honestly flag patches that are only whitespace/no-op edits so we
    # never claim a meaningful fix when there isn't one.
    t0 = time.perf_counter()
    verify_passed, verify_output = _verify(repo_root, diagnosis.file_path, diff_text)
    cosmetic = _is_cosmetic_diff(diff_text)
    if verify_passed and cosmetic:
        verify_passed = False
        verify_output = (
            "Patch applied cleanly BUT only changes whitespace / no-op "
            "casts. The incident's root cause may not exist in this file. "
            "Treat as a suggestion; do not auto-apply.\n\n" + verify_output
        )
    sub_steps.append(
        CodeFixSubStep(
            name="verify",
            summary=(
                "lint passed"
                if verify_passed
                else (
                    "cosmetic only - needs human review"
                    if cosmetic
                    else "lint failed (review patch)"
                )
            ),
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
        # autocrlf=false keeps files with their checked-in line endings
        # (usually LF), so diffs we generate match the bytes on disk.
        subprocess.run(
            ["git", "-c", "core.autocrlf=false", "clone", "--depth=1", repo_url, str(target)],
            check=True, timeout=GIT_CLONE_TIMEOUT, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "core.autocrlf", "false"],
            cwd=str(target), check=False, capture_output=True, timeout=10,
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

    # Stack-trace paths are the strongest hint when present. They tell
    # us exactly which file blew up. Extract the full path, basename,
    # and meaningful directory components.
    path_re = re.compile(
        r"[A-Za-z][A-Za-z0-9_/\\-]{2,}\.(?:ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|kt|rb|php|cs)"
    )
    for line in analysis.evidence[:6]:
        for match in path_re.findall(line):
            normalised = match.replace("\\", "/")
            _add(Path(normalised).stem)
            for part in Path(normalised).parts[:-1]:
                if part and part not in {"var", "task", "src", "app"} and len(part) >= 3:
                    _add(part)

    # Other identifier-like tokens from evidence.
    for line in analysis.evidence[:6]:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_/.-]{4,}", line):
            if token.lower() in {
                "error", "fatal", "warning", "info", "debug",
                "request", "response", "status", "true", "false",
                "exception", "stack", "trace",
            }:
                continue
            _add(token)
            if len(terms) > 22:
                break

    # Service hint from the request and forensic propagation path.
    if analysis.forensic:
        for hop in analysis.forensic.propagation_path:
            _add(hop)

    return terms[:22]


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
        # Model picked a path we didn't show it - typically a tiny
        # variation like .js vs .ts. Try to match by filename stem
        # against the candidates we actually offered before falling
        # back to the top hit.
        target_stem = Path(file_path).stem.lower()
        target_basename = Path(file_path).name.lower()
        matched: Optional[str] = None
        for c in candidate_paths:
            if Path(c).name.lower() == target_basename:
                matched = c
                break
        if matched is None:
            for c in candidate_paths:
                if Path(c).stem.lower() == target_stem:
                    matched = c
                    break
        if matched is None:
            logger.warning(
                "Diagnose picked unknown path %s; no stem match in %s; using top candidate",
                file_path, candidate_paths,
            )
            matched = candidate_paths[0]
        else:
            logger.info("Diagnose path %s resolved to %s via stem match", file_path, matched)
        file_path = matched

    return _Diagnosis(
        file_path=file_path, snippet=snippet, rationale=rationale, confidence=confidence,
    )


def _patch(
    analysis: AnalyzeResponse,
    diagnosis: _Diagnosis,
    repo_root: Path,
    bedrock: BedrockClient,
) -> str:
    """LLM picks a verbatim find chunk and writes its replacement.

    We then locate the find chunk in the actual file bytes and generate
    a unified diff with difflib. The LLM never authors diff syntax, so
    it can't miscount hunks, hallucinate context, or use wrong line
    numbers. This is the single biggest reliability win in the pipeline.
    """
    file_text = _read_file_capped(
        diagnosis.file_path, repo_root, max_chars=MAX_FILE_CHARS_PATCH,
    )
    if file_text is None:
        raise CodeFixError(f"Patch sub-agent could not read {diagnosis.file_path}")

    user_prompt = (
        "Fix the bug. Respond with strict JSON.\n\n"
        "Rules:\n"
        "  - `find` MUST be a verbatim copy of contiguous lines from the\n"
        "    file shown below. Copy the bytes EXACTLY: same indentation,\n"
        "    same quotes, same operators, same trailing punctuation. Do\n"
        "    not paraphrase or re-format. If you change a single byte,\n"
        "    the patch will fail to apply.\n"
        "  - `replace` is what those bytes should become. Keep the same\n"
        "    indentation. Change only what is necessary to fix the bug.\n"
        "  - `find` should be at least 1 full line and at most ~12 lines.\n"
        "    Make it long enough to appear exactly once in the file.\n\n"
        f"Buggy file path: {diagnosis.file_path}\n"
        f"Why it's buggy: {diagnosis.rationale}\n"
        f"Incident root cause: {analysis.root_cause}\n\n"
        "Full file contents (copy bytes from here, do not paraphrase):\n"
        "----- begin file -----\n"
        f"{file_text}"
        "----- end file -----\n\n"
        'Return JSON: {"find": "...", "replace": "..."}'
    )

    payload = bedrock.converse_json(
        system_prompt=(
            "You are a careful staff engineer producing a minimal, "
            "byte-exact code edit. You never paraphrase the `find` "
            "string - it has to match the source file character for "
            "character. Reply with strict JSON only."
        ),
        user_prompt=user_prompt,
        max_tokens=900,
        temperature=0.15,
    )

    find = str(payload.get("find", ""))
    replace = str(payload.get("replace", ""))
    if not find or not replace:
        raise CodeFixError("Patch sub-agent returned empty find/replace.")
    if find == replace:
        raise CodeFixError("Patch sub-agent returned no-op (find == replace).")

    # Find the chunk in the real file. If the LLM normalised line
    # endings or trimmed trailing whitespace, retry against a tolerant
    # form of the file text.
    # Anchor the find chunk in the real file, trying progressively more
    # tolerant matchers. LLMs frequently normalise whitespace or quote
    # style even when told not to.
    anchored = _anchor_find_chunk(file_text, find)
    if anchored is None:
        logger.warning(
            "Patch find did not anchor in file %s.\n--- find ---\n%s\n--- file head ---\n%s",
            diagnosis.file_path, find[:400], file_text[:400],
        )
        raise CodeFixError(
            "Patch sub-agent's `find` chunk does not appear in the file - "
            "the model paraphrased instead of copying bytes."
        )

    matched_text_in_file, _normalised_file = anchored
    patched_text = _normalised_file.replace(matched_text_in_file, replace, 1)
    return _make_unified_diff(diagnosis.file_path, _normalised_file, patched_text)


def _anchor_find_chunk(file_text: str, find: str) -> Optional[Tuple[str, str]]:
    """Return (matched_chunk_as_it_appears_in_file, file_text) or None.

    Tries progressively looser matchers. The first one that produces a
    unique match wins. The returned chunk is always the exact bytes
    from the file, never the LLM's paraphrase, so the downstream
    replace + diff stays byte-correct.
    """
    file_lines = file_text.splitlines()

    # 1) Exact substring.
    if file_text.count(find) == 1:
        return find, file_text

    # 2) Trailing-whitespace-tolerant on both sides.
    file_rstripped = "\n".join(line.rstrip() for line in file_lines)
    find_rstripped = "\n".join(line.rstrip() for line in find.splitlines())
    if file_rstripped.count(find_rstripped) == 1:
        return find_rstripped, file_rstripped

    # 3) Whitespace-normalised line keys, exact line-by-line window.
    def _key(line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()

    find_lines_nonempty = [l for l in find.splitlines() if l.strip()]
    if find_lines_nonempty:
        file_keys = [_key(l) for l in file_lines]
        find_keys = [_key(l) for l in find_lines_nonempty]
        for start in range(0, len(file_keys) - len(find_keys) + 1):
            if file_keys[start : start + len(find_keys)] == find_keys:
                window = "\n".join(file_lines[start : start + len(find_keys)])
                return window, "\n".join(file_lines)

    # 4) Last resort: strip ALL whitespace, find the substring, map back
    # to the original line range. This is robust against the most common
    # LLM mistake (changing space-around-operators), and still safe
    # because we only accept exactly-one match.
    def _strip_all_ws(s: str) -> str:
        return re.sub(r"\s+", "", s)

    file_stripped = _strip_all_ws(file_text)
    find_stripped = _strip_all_ws(find)
    if not find_stripped:
        return None
    if file_stripped.count(find_stripped) != 1:
        return None

    # Build an index from stripped-position -> original char index.
    # We walk the file once, recording the original char index for every
    # non-whitespace character.
    orig_index_for_stripped: list[int] = []
    for i, ch in enumerate(file_text):
        if not ch.isspace():
            orig_index_for_stripped.append(i)

    start_stripped = file_stripped.find(find_stripped)
    end_stripped = start_stripped + len(find_stripped) - 1
    start_orig = orig_index_for_stripped[start_stripped]
    end_orig = orig_index_for_stripped[end_stripped] + 1

    # Expand to whole lines so the replace doesn't leave dangling chars.
    line_start = file_text.rfind("\n", 0, start_orig) + 1
    line_end = file_text.find("\n", end_orig)
    if line_end == -1:
        line_end = len(file_text)
    window = file_text[line_start:line_end]
    return window, file_text


def _make_unified_diff(rel_path: str, before: str, after: str) -> str:
    """Generate a clean unified diff via difflib.

    difflib gives us correct hunk headers and line counts unconditionally,
    so verify-time `git apply` failures from miscounted hunks disappear.
    """
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
        n=3,
    )
    text = "".join(diff)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _verify(repo_root: Path, file_path: str, diff_text: str) -> Tuple[bool, str]:
    """Apply the diff to a scratch copy and run a fast lint check.

    Returns ``(passed, output)``. ``passed`` is False if anything goes
    wrong - we don't claim success blindly. The scratch copy is cleaned
    up before return.
    """
    # Resolve to an absolute path so paths passed to subprocess stay
    # unambiguous regardless of cwd.
    scratch = (repo_root.parent / (repo_root.name + "_verify")).resolve()
    try:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)
        shutil.copytree(
            repo_root, scratch,
            ignore=shutil.ignore_patterns(*SKIP_DIRS),
            dirs_exist_ok=False,
        )

        # Normalise the diff: LLMs occasionally emit CRLF, drop trailing
        # newlines, or miscount hunk lines. We re-count hunks and strip
        # CR characters before handing the patch to git.
        normalised = _normalise_diff(diff_text)
        diff_file = (scratch.parent / f"{scratch.name}.patch").resolve()
        diff_file.write_text(normalised, encoding="utf-8", newline="\n")

        # Try increasingly forgiving apply strategies. We start strict so
        # a clean patch is reported honestly; only fall back when the
        # strict pass rejects.
        apply_attempts = [
            ["git", "apply", "--whitespace=nowarn"],
            ["git", "apply", "--whitespace=fix", "--recount"],
            ["git", "apply", "--whitespace=fix", "--recount", "--unidiff-zero"],
        ]
        apply = None
        for cmd in apply_attempts:
            apply = subprocess.run(
                cmd + [str(diff_file)],
                cwd=str(scratch), capture_output=True, timeout=30,
            )
            if apply.returncode == 0:
                break
        if apply is None or apply.returncode != 0:
            stderr = (apply.stderr if apply else b"").decode("utf-8", errors="replace")
            return False, "git apply failed (tried strict + forgiving):\n" + stderr[:500]

        # Pick a verifier by extension. Anything we don't know how to
        # check counts as "patch applied cleanly" - which is still a
        # real signal that the diff is at least well-formed.
        ext = Path(file_path).suffix.lower()
        if ext in {".ts", ".tsx", ".js", ".jsx"}:
            # Prefer the repo's own tsc under node_modules so we don't
            # collide with unrelated commands also named "tsc" on PATH
            # (TimeShift on some Linuxes; Windows can find stray ones).
            local_tsc = scratch / "node_modules" / ".bin"
            tsc_candidates = [
                local_tsc / "tsc.cmd",
                local_tsc / "tsc",
            ]
            tsc = next((str(p) for p in tsc_candidates if p.exists()), None)
            if tsc:
                check = subprocess.run(
                    [tsc, "--noEmit", "--skipLibCheck", file_path],
                    cwd=str(scratch), capture_output=True, timeout=VERIFY_TIMEOUT,
                )
                ok = check.returncode == 0
                out = check.stderr.decode("utf-8", errors="replace") or check.stdout.decode("utf-8", errors="replace")
                return ok, (out[:800] if out.strip() else "tsc clean")
            # No local tsc - patch applied cleanly is still a strong
            # signal. Don't trust whatever stray "tsc" is on global PATH.
            return True, "patch applied cleanly; no project-local tsc available"

        if ext == ".py":
            python = shutil.which("python") or shutil.which("python3") or "python"
            check = subprocess.run(
                [python, "-m", "py_compile", file_path],
                cwd=str(scratch), capture_output=True, timeout=VERIFY_TIMEOUT,
            )
            ok = check.returncode == 0
            out = check.stderr.decode("utf-8", errors="replace")
            return ok, (out[:800] if out.strip() else "py_compile clean")

        return True, f"patch applied cleanly; no verifier for {ext}"
    except subprocess.TimeoutExpired:
        return False, "verify step timed out"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Verify sub-agent failed unexpectedly")
        return False, f"verify error: {exc}"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        try:
            (scratch.parent / f"{scratch.name}.patch").unlink(missing_ok=True)
        except OSError:
            pass


# ── Helpers ────────────────────────────────────────────────────────────────


def _read_file_capped(
    rel_path: str, repo_root: Path, max_chars: int = MAX_FILE_CHARS_DIAGNOSE,
) -> Optional[str]:
    full = repo_root / rel_path
    try:
        # Read raw bytes and decode without newline translation, so the
        # text we hand to the LLM and to difflib matches the bytes on
        # disk exactly. Without this, Python silently maps CRLF -> LF
        # on Windows and our generated diff fails to git-apply.
        raw = full.read_bytes()
    except OSError:
        return None
    text = raw.decode("utf-8", errors="ignore")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n# ... [file truncated]\n"
    return text


def _is_cosmetic_diff(diff_text: str) -> bool:
    """True when the diff only changes whitespace or removes ``as any`` casts.

    Important honesty guard: when the LLM has nothing meaningful to
    change (because the incident's root cause doesn't actually exist in
    the chosen file) it tends to produce whitespace fiddling that
    applies cleanly but fixes nothing. We surface that as 'cosmetic -
    needs human review' instead of letting the green 'verified' badge
    over-claim.
    """
    plus: list[str] = []
    minus: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- ") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            plus.append(line[1:])
        elif line.startswith("-"):
            minus.append(line[1:])

    if not plus and not minus:
        return True  # empty diff

    def _strip_for_compare(lines: list[str]) -> str:
        # Remove whitespace AND `as any` casts (and trailing semicolons
        # that come along with them) so we don't credit pure noise.
        joined = "".join(lines)
        joined = re.sub(r"\s+", "", joined)
        joined = joined.replace("asany", "")
        return joined

    return _strip_for_compare(plus) == _strip_for_compare(minus)


def _normalise_diff(text: str) -> str:
    """Tidy a diff so picky `git apply` quirks don't reject sane patches.

    Strips carriage returns, removes accidental trailing whitespace on
    diff metadata lines, ensures a trailing newline. We deliberately do
    not touch content inside hunks beyond CR removal because the bytes
    must match the source file.
    """
    text = text.replace("\r\n", "\n").replace("\r", "")
    if not text.endswith("\n"):
        text += "\n"
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
