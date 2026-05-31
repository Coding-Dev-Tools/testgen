"""Git diff parser — extract changed functions/classes from git diffs."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChangedUnit:
    """A function or class that was changed in a diff."""

    file_path: Path
    name: str
    line_start: int
    line_end: int


@dataclass
class DiffHunk:
    """A single hunk from a git diff."""

    file_path: Path
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    changed_lines: list[int] = field(default_factory=list)


_HUNK_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")
_FUNC_RE = re.compile(r"^\+\s*(?:async\s+)?def\s+(\w+)")
_CLASS_RE = re.compile(r"^\+\s*class\s+(\w+)")
_DEF_RE = re.compile(r"^\+\s*(?:async\s+)?def\s+(\w+)|^\+\s*class\s+(\w+)")


def _run_git_diff(target: Path, cached: bool = False) -> str:
    """Run git diff and return the output."""
    cmd = ["git", "diff"]
    if cached:
        cmd.append("--cached")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _run_git_diff_head(target: Path) -> str:
    """Try git diff HEAD first, fall back to git diff --cached."""
    output = _run_git_diff(target)
    if not output.strip():
        output = _run_git_diff(target, cached=True)
    return output


def parse_diff(diff_text: str) -> list[DiffHunk]:
    """Parse unified diff output into DiffHunk objects."""
    hunks: list[DiffHunk] = []
    current_file: Path | None = None

    for line in diff_text.splitlines():
        # File path detection
        if line.startswith("diff --git"):
            # Extract path from "diff --git a/path b/path"
            parts = line.split(" b/", 1)
            if len(parts) == 2:
                current_file = Path(parts[1].split()[0])
            continue

        if line.startswith("--- a/"):
            continue

        if line.startswith("+++ b/"):
            path_str = line[6:].strip()
            if path_str != "/dev/null":
                current_file = Path(path_str)
            continue

        # Hunk header
        match = _HUNK_RE.match(line)
        if match and current_file:
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            hunks.append(DiffHunk(
                file_path=current_file,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
            ))
            continue

        # Track changed (added) lines
        if hunks and line.startswith("+") and not line.startswith("+++"):
            hunk = hunks[-1]
            # Compute line number from new file
            # new_start is 1-based line number of the first line in the hunk
            # We track relative offset
            hunk.changed_lines.append(hunk.new_start + len(hunk.changed_lines))

    return hunks


def get_changed_functions(target: Path) -> set[tuple[Path, str]]:
    """Get a set of (file_path, function_or_class_name) for changed units."""
    diff_text = _run_git_diff_head(target)
    if not diff_text.strip():
        return set()

    hunks = parse_diff(diff_text)
    changed: set[tuple[Path, str]] = set()

    for _hunk in hunks:
        # DiffHunk objects available for line-range-based analysis
        pass

    # Simpler approach: scan the diff text for added def/class lines
    current_file: Path | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            path_str = line[6:].strip()
            if path_str != "/dev/null":
                current_file = Path(path_str)
            continue

        if current_file and line.startswith("+"):
            func_match = _FUNC_RE.match(line)
            if func_match:
                changed.add((current_file, func_match.group(1)))
                continue
            class_match = _CLASS_RE.match(line)
            if class_match:
                changed.add((current_file, class_match.group(1)))

    return changed


def get_changed_files(target: Path) -> set[Path]:
    """Get a set of file paths that have changes."""
    diff_text = _run_git_diff_head(target)
    if not diff_text.strip():
        return set()

    files: set[Path] = set()
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            path_str = line[6:].strip()
            if path_str != "/dev/null":
                files.add(Path(path_str))

    return files
