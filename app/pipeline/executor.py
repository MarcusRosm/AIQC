"""
Step 5 – Playwright Test Executor.

Runs generated Playwright `.spec.ts` files via subprocess, parses the JSON
report, and emits structured :class:`ExecutionResult` objects. Locator
failures trigger the Self-Healing Engine automatically.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

from app.core.exceptions import ExecutionError
from app.core.logging import get_logger
from app.core.schemas import ExecutionResult, TestStatus

logger = get_logger(__name__)

# Regex to detect missing-locator errors in Playwright output
_LOCATOR_RE = re.compile(
    r"locator\s*\((?P<sel>[^)]+)\)|Unable to locate|strict mode violation|"
    r"element not found|TimeoutError.*locator\('(?P<sel2>[^']+)'\)",
    re.IGNORECASE,
)


class PlaywrightExecutor:
    """
    Step 5: Executes Python Pytest spec files and parses results.

    Uses ``uv run pytest`` with the json-report plugin so results are
    machine-readable and integration with the self-healing engine is clean.
    """

    def __init__(self, playwright_timeout_s: int = 300) -> None:
        self._timeout = playwright_timeout_s
        self._uv = shutil.which("uv") or "uv"

    async def run(
        self,
        spec_paths: list[Path],
        working_dir: Path | None = None,
    ) -> list[ExecutionResult]:
        """
        Run all spec files and return structured results.

        Args:
            spec_paths: Paths to ``test_*.py`` files to execute.
            working_dir: Directory to run Playwright from.

        Returns:
            List of :class:`ExecutionResult` (one per test case found).
        """
        if not spec_paths:
            return []

        spec_args = [str(p) for p in spec_paths]
        
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            report_path = tf.name
            
        cmd = [
            self._uv,
            "run",
            "pytest",
            "--json-report",
            f"--json-report-file={report_path}",
            "-q",
            *spec_args,
        ]

        logger.info("Running Pytest: %s", " ".join(cmd))
        cwd = str(working_dir) if working_dir else None

        env = os.environ.copy()
        if "BASE_URL" not in env:
            env["BASE_URL"] = "http://localhost:8000"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError as exc:
            if os.path.exists(report_path):
                os.remove(report_path)
            raise ExecutionError(
                f"Playwright timed out after {self._timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            if os.path.exists(report_path):
                os.remove(report_path)
            raise ExecutionError(
                "uv not found – ensure uv is installed and on PATH."
            ) from exc

        stderr_str = stderr.decode("utf-8", errors="replace")
        if stderr_str:
            logger.debug("Pytest stderr:\n%s", stderr_str[:2000])

        report_content = ""
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()
            os.remove(report_path)

        results = self._parse_json_report(report_content, stderr_str)
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        logger.info("Playwright run done: %d passed, %d failed", passed, failed)
        return results

    def _parse_json_report(self, stdout: str, stderr: str) -> list[ExecutionResult]:
        """Parse pytest-json-report output into ExecutionResult objects."""
        results: list[ExecutionResult] = []

        # Try to extract JSON from stdout (may have leading/trailing text)
        json_start = stdout.find("{")
        if json_start == -1:
            logger.warning("No JSON report found in pytest output – parsing stderr.")
            return self._parse_stderr_fallback(stderr)

        try:
            report: dict[str, Any] = json.loads(stdout[json_start:])
        except json.JSONDecodeError:
            logger.warning("Failed to parse pytest JSON report.")
            return self._parse_stderr_fallback(stderr)

        # Handle collection errors (e.g. LLM generated invalid Python syntax)
        collectors = report.get("collectors", [])
        for collector in collectors:
            if collector.get("result") == "failed":
                longrepr = collector.get("longrepr", "")
                results.append(
                    ExecutionResult(
                        test_title="Test Collection (Syntax Error)",
                        spec_file=collector.get("nodeid", "unknown"),
                        status=TestStatus.ERROR,
                        duration_ms=0,
                        error_message=longrepr[:1000] if longrepr else "Failed to parse generated test file.",
                    )
                )

        # Handle standard test execution results
        for test in report.get("tests", []):
            results.append(self._parse_test(test))

        return results

    @staticmethod
    def _parse_test(test: dict) -> ExecutionResult:
        nodeid: str = test.get("nodeid", "unknown")
        # nodeid looks like "generated_tests/.../test_*.py::test_name"
        spec_file = nodeid.split("::")[0] if "::" in nodeid else "unknown"
        title = nodeid.split("::")[-1] if "::" in nodeid else nodeid

        outcome = test.get("outcome", "unknown")
        call_info = test.get("call", {})
        duration = int(call_info.get("duration", 0) * 1000)

        status_map = {
            "passed": TestStatus.PASSED,
            "failed": TestStatus.FAILED,
            "skipped": TestStatus.SKIPPED,
            "error": TestStatus.ERROR,
        }
        status = status_map.get(outcome, TestStatus.ERROR)

        error_msg: str | None = None
        failing_selector: str | None = None

        if status in (TestStatus.FAILED, TestStatus.ERROR):
            crash = call_info.get("crash", {})
            if crash:
                error_msg = crash.get("message", "")
                m = _LOCATOR_RE.search(error_msg or "")
                if m:
                    failing_selector = m.group("sel") or m.group("sel2")
            else:
                setup = test.get("setup", {})
                if setup.get("outcome") == "failed":
                    error_msg = setup.get("crash", {}).get("message", "")

        return ExecutionResult(
            test_title=title,
            spec_file=spec_file,
            status=status,
            duration_ms=duration,
            error_message=error_msg,
            failing_selector=failing_selector,
        )

    @staticmethod
    def _parse_stderr_fallback(stderr: str) -> list[ExecutionResult]:
        """Minimal fallback when JSON report is unavailable."""
        return [
            ExecutionResult(
                test_title="Pytest execution",
                spec_file="unknown",
                status=TestStatus.ERROR,
                error_message=stderr[:500] if stderr else "Unknown error",
            )
        ]
