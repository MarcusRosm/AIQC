"""
Step 1 – Diff Analyzer.

Parses a unified git diff and extracts structured change information:
- Files added/modified/deleted
- Functions and classes touched
- Additions/deletions counts
- Heuristic detection of affected UI components and API routes
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.exceptions import DiffAnalysisError
from app.core.logging import get_logger
from app.core.schemas import DiffResult, FileChange

logger = get_logger(__name__)

# ── regex patterns ────────────────────────────────────────────────────────────
_FILE_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)
_OLD_FILE = re.compile(r"^--- a/(.+)$", re.MULTILINE)
_NEW_FILE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
_HUNK_HEADER = re.compile(r"^@@ .+? @@", re.MULTILINE)
_ADDED_LINE = re.compile(r"^\+(?!\+\+)", re.MULTILINE)
_REMOVED_LINE = re.compile(r"^-(?!--)", re.MULTILINE)

# Python/TS function / class definitions
_PY_FUNC = re.compile(r"^\+\s*(async\s+)?def\s+(\w+)\s*\(", re.MULTILINE)
_PY_CLASS = re.compile(r"^\+\s*class\s+(\w+)[\s:(]", re.MULTILINE)
_TS_FUNC = re.compile(r"^\+(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", re.MULTILINE)
_TS_ARROW = re.compile(r"^\+(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(", re.MULTILINE)
_TS_CLASS = re.compile(r"^\+(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.MULTILINE)

# Route heuristics
_ROUTE_PY = re.compile(r'@(?:router|app)\.\w+\(["\']([/\w{}<>:]+)["\']', re.MULTILINE)
_ROUTE_TS = re.compile(r"""(?:path|route)\s*:\s*["']([/\w{}<>:]+)["']""", re.MULTILINE)


@dataclass
class _FilePatch:
    path: str
    change_type: str = "modified"
    raw: str = ""
    additions: int = 0
    deletions: int = 0
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)


class DiffAnalyzer:
    """
    Parses unified diff text and produces a structured :class:`DiffResult`.

    Responsibilities (Single Responsibility):
    - Parse diff headers to identify changed files
    - Count addition/deletion lines
    - Extract touched function/class names
    - Detect affected routes and UI components
    """

    def analyze(self, diff_text: str) -> DiffResult:
        """
        Analyse a raw ``git diff`` string and return a :class:`DiffResult`.

        Args:
            diff_text: The raw output of ``git diff`` or ``git diff HEAD~1``.

        Returns:
            A fully populated :class:`DiffResult`.

        Raises:
            :exc:`DiffAnalysisError`: If ``diff_text`` is empty or unparsable.
        """
        if not diff_text or not diff_text.strip():
            raise DiffAnalysisError("Diff text is empty – nothing to analyse.")

        logger.info("Analysing diff (%d chars)", len(diff_text))
        patches = self._split_into_file_patches(diff_text)

        if not patches:
            raise DiffAnalysisError(
                "Could not find any file-level diff sections. "
                "Ensure the input is a standard unified diff."
            )

        file_changes: list[FileChange] = []
        all_routes: list[str] = []
        all_components: list[str] = []

        for patch in patches:
            self._populate_patch(patch)
            file_changes.append(
                FileChange(
                    path=patch.path,
                    change_type=patch.change_type,
                    additions=patch.additions,
                    deletions=patch.deletions,
                    functions_touched=patch.functions,
                    classes_touched=patch.classes,
                    raw_diff=patch.raw,
                )
            )
            all_routes.extend(self._find_routes(patch.raw))
            all_components.extend(self._find_components(patch.path, patch.raw))

        result = DiffResult(
            files=file_changes,
            total_additions=sum(f.additions for f in file_changes),
            total_deletions=sum(f.deletions for f in file_changes),
            affected_routes=list(dict.fromkeys(all_routes)),
            affected_components=list(dict.fromkeys(all_components)),
            summary=self._make_summary(file_changes),
        )

        logger.info(
            "Diff analysis complete: %d files, +%d -%d",
            len(result.files),
            result.total_additions,
            result.total_deletions,
        )
        return result

    # ── private helpers ───────────────────────────────────────────────────────

    def _split_into_file_patches(self, diff_text: str) -> list[_FilePatch]:
        """Split the diff into per-file sections."""
        patches: list[_FilePatch] = []

        # Use the "diff --git" header as a delimiter
        sections = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)

        for section in sections:
            if not section.strip():
                continue
            m = _FILE_HEADER.match(section)
            if not m:
                continue
            path = m.group(2)  # "b/" path is the new name
            change_type = self._detect_change_type(section)
            patches.append(_FilePatch(path=path, change_type=change_type, raw=section))

        return patches

    def _populate_patch(self, patch: _FilePatch) -> None:
        """Fill addition/deletion counts and touched symbols in-place."""
        patch.additions = len(_ADDED_LINE.findall(patch.raw))
        patch.deletions = len(_REMOVED_LINE.findall(patch.raw))

        ext = patch.path.rsplit(".", 1)[-1].lower()

        if ext == "py":
            patch.functions = list(
                dict.fromkeys(
                    [m.group(2) for m in _PY_FUNC.finditer(patch.raw)]
                )
            )
            patch.classes = list(
                dict.fromkeys(
                    [m.group(1) for m in _PY_CLASS.finditer(patch.raw)]
                )
            )
        elif ext in {"ts", "tsx", "js", "jsx"}:
            funcs = [m.group(1) for m in _TS_FUNC.finditer(patch.raw)]
            funcs += [m.group(1) for m in _TS_ARROW.finditer(patch.raw)]
            patch.functions = list(dict.fromkeys(funcs))
            patch.classes = list(
                dict.fromkeys(
                    [m.group(1) for m in _TS_CLASS.finditer(patch.raw)]
                )
            )

    def _detect_change_type(self, section: str) -> str:
        if "new file mode" in section:
            return "added"
        if "deleted file mode" in section:
            return "deleted"
        if "rename from" in section:
            return "renamed"
        return "modified"

    def _find_routes(self, raw: str) -> list[str]:
        routes: list[str] = []
        routes.extend(m.group(1) for m in _ROUTE_PY.finditer(raw))
        routes.extend(m.group(1) for m in _ROUTE_TS.finditer(raw))
        return routes

    def _find_components(self, path: str, raw: str) -> list[str]:
        """Heuristically detect React/UI component names from TSX files."""
        components: list[str] = []
        if not path.endswith((".tsx", ".jsx")):
            return components
        # PascalCase function names are typically components
        for m in _TS_FUNC.finditer(raw):
            name = m.group(1)
            if name[0].isupper():
                components.append(name)
        for m in _TS_ARROW.finditer(raw):
            name = m.group(1)
            if name[0].isupper():
                components.append(name)
        return components

    @staticmethod
    def _make_summary(changes: list[FileChange]) -> str:
        names = ", ".join(c.path.split("/")[-1] for c in changes[:5])
        suffix = f" (+{len(changes) - 5} more)" if len(changes) > 5 else ""
        return f"Changed {len(changes)} file(s): {names}{suffix}"
