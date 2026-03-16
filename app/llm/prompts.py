"""
LLM Prompt Templates.

Factory functions that produce structured prompts for each pipeline stage.
Each function is a pure function with no side effects.
"""

from __future__ import annotations

from app.core.schemas import DiffResult, TestScenario, TestScenarioList


# ── System Prompts ────────────────────────────────────────────────────────────

SYSTEM_QA_ARCHITECT = """You are a Principal QA Architect and Playwright expert.
You produce precise, structured JSON responses – no prose outside the JSON object.
All generated Playwright code must use the modern locator API (get_by_role, get_by_label,
get_by_text, get_by_placeholder, get_by_test_id) and never use XPath or CSS id/class selectors
unless strictly necessary.
Respond ONLY with the requested JSON structure."""

SYSTEM_HEALER = """You are an expert UI test self-healing engine.
Given a broken Playwright selector and a DOM snapshot, identify the most likely
correct element and return a ranked list of candidate locators with confidence scores."""


# ── Step 3 – Scenario Generation ─────────────────────────────────────────────

def scenario_generation_prompt(diff: DiffResult, context: list[str]) -> str:
    """
    Build the prompt for LLM-based test scenario generation (Step 3).

    Output JSON schema::

        {
          "scenarios": [
            {
              "title": "string",
              "category": "happy_path|negative|edge_case|security",
              "description": "string",
              "preconditions": ["string"],
              "steps": [
                {
                  "action": "navigate|click|fill|assert|hover|wait",
                  "selector": "string or null",
                  "value": "string or null",
                  "assertion": "string or null"
                }
              ],
              "expected_result": "string",
              "tags": ["string"]
            }
          ]
        }
    """
    context_block = _format_context(context)
    diff_block = _format_diff(diff)

    return f"""## Task: Generate Test Scenarios

### Diff Summary
{diff_block}

### Repository Context (relevant existing code)
{context_block}

### Instructions
Analyse the diff and context above. Generate comprehensive test scenarios covering:
1. **happy_path** – the expected successful user flows introduced by the changes
2. **negative** – invalid inputs, missing data, expected error responses
3. **edge_case** – boundary values, timeouts, empty states, concurrent actions
4. **security** – unauthorized access, SQL injection probes, XSS inputs or OWASP Top 10 vulnerabilities

Rules:
- Generate between 6 and 16 scenarios total.
- Each scenario must reference the exact files or routes identified in the diff.
- Steps must be concrete and actionable (use specific URLs, button labels, field names from the code).
- For API changes produce both UI and API-level test steps where applicable.
- Do NOT invent features not visible in the diff.

Respond ONLY with this JSON (no markdown prose):
{{
  "scenarios": [
    {{
      "title": "...",
      "category": "happy_path",
      "description": "...",
      "preconditions": [],
      "steps": [{{"action": "navigate", "selector": null, "value": "/path", "assertion": null}}],
      "expected_result": "...",
      "tags": []
    }}
  ]
}}"""


# ── Step 4 – Code Generation ─────────────────────────────────────────────────

def code_generation_prompt(scenarios: TestScenarioList, context: list[str]) -> str:
    """
    Build the prompt for Python Pytest Playwright spec generation (Step 4).

    The LLM must return valid Python that uses ``playwright.sync_api``.
    Includes QA guardrails: coverage requirements, assertion quality,
    error handling, and code clarity constraints.
    """
    context_block = _format_context(context)
    scenarios_json = scenarios.model_dump_json(indent=2)

    return f"""## Task: Generate Python Pytest Playwright Spec

### Test Scenarios (input)
{scenarios_json}

### Repository Context
{context_block}

### Instructions
Convert ALL scenarios above into a single Python Pytest Playwright test file.

#### Structure requirements
- Import from `playwright.sync_api` and use `pytest`.
- Each scenario maps to exactly one `def test_*(page: Page):` function.
- Add a `# SCENARIO_ID: <id>` comment before each test function.
- Include `page.goto(...)` using `os.environ.get("BASE_URL", "http://localhost:8000")`.

#### Locator requirements
Use ONLY these semantic locators — in this priority order:
1. `page.get_by_role()`
2. `page.get_by_label()`
3. `page.get_by_placeholder()`
4. `page.get_by_text()`
5. `page.get_by_test_id()`

Never use `page.locator("css=...")`, XPath, or index-based selectors.

#### Assertion requirements (QA guardrail)
Every test MUST include at least one `expect(...)` assertion that verifies
a meaningful outcome — not just that the page loaded or a click succeeded.

Good: `expect(page.get_by_role("alert")).to_contain_text("Order confirmed")`
Bad:  `expect(page).to_have_url("http://localhost:8000")` as the sole assertion

Assertions must target the specific UI state the scenario is validating.
Do not assert generic page properties unless the scenario explicitly tests navigation.

#### Error surface requirements (QA guardrail)
- If a scenario involves a form submission, network action, or state change,
  include an assertion that verifies the success OR failure outcome — not both.
- Do not use bare `try/except` blocks. If error handling is needed, re-raise
  or let Playwright's built-in timeout surface the failure naturally.
- Never swallow assertion errors. Do not catch `AssertionError` or `TimeoutError`.

#### Code clarity requirements (QA guardrail)
- Each test function must test exactly one scenario. No branching logic inside tests.
- Extract repeated locators used more than once into a named local variable.
  Example: `submit_btn = page.get_by_role("button", name="Submit")`
- No magic strings for URLs, role names, or expected text used in more than
  one place — assign them to variables at the top of the test function.
- Function names must describe the scenario outcome, not just the action.
  Good: `test_login_shows_error_for_invalid_password`
  Bad:  `test_login_form`

#### Payload structure for API tests (QA guardrail)
- When a scenario targets an API endpoint, derive the request payload structure
  exclusively from the type annotations visible in the repository context.
- Never invent or guess field names, types, or nesting — if the payload model
  is not found in context, emit a `pytest.skip("payload model not in context")`
  and a `# TODO: resolve <ModelName>` comment instead of fabricating fields.

Never construct a raw `dict` payload with hardcoded keys unless the route
accepts `dict` / `Any` explicitly. Always prefer instantiating the typed model
and calling `.model_dump()` so type errors surface at generation time.

#### Syntax rules (QA guardrail)
- Make sure code generated is clean with no trailing commas or other syntax errors.
- CRITICAL: When defining multiline string values in your Python payloads (like `diff_text`), if you must write physical line breaks, 
  you MUST use Python's triple-quotes (`\"\"\"`) for that specific payload value.

### Output format
Respond with ONLY a JSON object — no explanation, no markdown fence:
{{
  "filename": "test_generated.py",
  "content": "import os\\nimport pytest\\nfrom playwright.sync_api import Page, expect\\n..."
}}"""


# ── Step 6 – Self-Healing ─────────────────────────────────────────────────────

def self_heal_prompt(
    old_selector: str,
    dom_snapshot: str,
    test_title: str,
    screenshot_b64: str | None = None,
) -> str:
    """
    Build the prompt for locator self-healing (Step 6 – AI assist path).
    """
    screenshot_note = (
        "\nA base64-encoded screenshot is also available showing the current page state."
        if screenshot_b64
        else ""
    )
    dom_excerpt = dom_snapshot[:3000] if len(dom_snapshot) > 3000 else dom_snapshot

    return f"""## Task: Self-Heal Broken Playwright Selector

### Failing Test
{test_title}

### Broken Selector
{old_selector}

### Current DOM Snapshot (excerpt)
{dom_excerpt}
{screenshot_note}

### Instructions
The selector above no longer matches any element in the DOM.

1. Identify the most likely element the test was targeting.
2. Return up to 5 candidate Playwright locators ranked by confidence (0.0–1.0).
3. Use modern Playwright locator API: `page.getByRole(...)`, `page.getByLabel(...)`, etc.
4. Explain briefly why each candidate matches.

Respond ONLY with:
{{
  "candidates": [
    {{
      "selector": "original CSS/XPath",
      "playwright_locator": "page.getByRole('button', {{ name: 'Login' }})",
      "confidence": 0.95,
      "match_reasons": ["aria-label matches", "text content preserved"]
    }}
  ]
}}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_context(snippets: list[str], max_chars: int = 4000) -> str:
    if not snippets:
        return "*(no repository context indexed)*"
    result: list[str] = []
    total = 0
    for i, snippet in enumerate(snippets):
        if total + len(snippet) > max_chars:
            result.append(f"[...{len(snippets) - i} more snippets truncated for length]")
            break
        result.append(f"--- snippet {i + 1} ---\n{snippet}")
        total += len(snippet)
    return "\n\n".join(result)


def _format_diff(diff: DiffResult) -> str:
    lines: list[str] = [diff.summary]
    if diff.affected_routes:
        lines.append("Affected routes: " + ", ".join(diff.affected_routes[:8]))
    if diff.affected_components:
        lines.append("Affected components: " + ", ".join(diff.affected_components[:8]))
    lines.append(f"Total: +{diff.total_additions} -{diff.total_deletions}")
    for fc in diff.files[:8]:
        symbol = {"added": "+", "deleted": "-", "renamed": "~"}.get(fc.change_type, "M")
        funcs = f" [{', '.join(fc.functions_touched[:4])}]" if fc.functions_touched else ""
        lines.append(f"  {symbol} {fc.path}{funcs}")
    return "\n".join(lines)
