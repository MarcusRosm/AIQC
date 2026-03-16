"""
Step 6a – Locator Similarity Scorer.

Parses the DOM snapshot at point of failure and scores every interactive
element against the broken selector using a weighted multi-attribute
similarity algorithm. Returns a ranked list of :class:`HealCandidate` objects.

Algorithm weights:
  - id exact match:            +0.40
  - aria-label / name fuzzy:   +0.30
  - text content fuzzy:        +0.20
  - class overlap ratio:       +0.10
"""

from __future__ import annotations

import difflib
import re
from html.parser import HTMLParser
from typing import Any

from app.core.logging import get_logger
from app.core.schemas import HealCandidate

logger = get_logger(__name__)

# Interactive elements worth targeting
_INTERACTIVE_TAGS: frozenset[str] = frozenset(
    {"button", "input", "a", "select", "textarea", "label", "form", "li", "span", "div"}
)

# Playwright locator strategy builders
def _by_role(role: str, name: str | None) -> str:
    if name:
        clean_name = name.strip().replace("'", "\\'")
        return f"page.getByRole('{role}', {{ name: '{clean_name}' }})"
    return f"page.getByRole('{role}')"


def _by_label(label: str) -> str:
    return f"page.getByLabel('{label.strip()}')"


def _by_text(text: str) -> str:
    return f"page.getByText('{text.strip()[:60]}')"


def _by_placeholder(ph: str) -> str:
    return f"page.getByPlaceholder('{ph.strip()}')"


def _by_test_id(tid: str) -> str:
    return f"page.getByTestId('{tid.strip()}')"


# ARIA implicit roles for HTML tags
_TAG_TO_ROLE: dict[str, str] = {
    "button": "button",
    "a": "link",
    "input": "textbox",
    "select": "combobox",
    "textarea": "textbox",
    "form": "form",
    "li": "listitem",
    "h1": "heading", "h2": "heading", "h3": "heading",
    "h4": "heading", "h5": "heading", "h6": "heading",
}


class _Element:
    """Lightweight representation of a DOM element."""

    __slots__ = ("tag", "attrs", "text")

    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag.lower()
        self.attrs = attrs
        self.text = ""

    @property
    def elem_id(self) -> str:
        return self.attrs.get("id", "")

    @property
    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()

    @property
    def aria_label(self) -> str:
        return self.attrs.get("aria-label", "") or self.attrs.get("name", "")

    @property
    def placeholder(self) -> str:
        return self.attrs.get("placeholder", "")

    @property
    def data_testid(self) -> str:
        return self.attrs.get("data-testid", "") or self.attrs.get("data-test-id", "")

    @property
    def role(self) -> str:
        explicit = self.attrs.get("role", "")
        return explicit or _TAG_TO_ROLE.get(self.tag, self.tag)

    def best_playwright_locator(self) -> str:
        if self.data_testid:
            return _by_test_id(self.data_testid)
        if self.aria_label:
            return _by_role(self.role, self.aria_label)
        if self.text.strip():
            label = self.text.strip()[:60]
            if self.tag == "a":
                return _by_role("link", label)
            if self.tag == "button":
                return _by_role("button", label)
            return _by_text(label)
        if self.placeholder:
            return _by_placeholder(self.placeholder)
        if self.elem_id:
            return f"page.locator('#{self.elem_id}')"
        return _by_role(self.role, None)


class _DOMParser(HTMLParser):
    """Collects all interactive elements into a flat list."""

    def __init__(self) -> None:
        super().__init__()
        self._elements: list[_Element] = []
        self._current: _Element | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _INTERACTIVE_TAGS:
            self._current = _Element(tag, {k: (v or "") for k, v in attrs})
            self._elements.append(self._current)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _INTERACTIVE_TAGS:
            self._current = None

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current.text += data

    @property
    def elements(self) -> list[_Element]:
        return self._elements


class LocatorScorer:
    """
    Computes confidence scores for DOM element candidates against a broken selector.

    Implements the SRP: only responsible for scoring logic.
    """

    def score_candidates(
        self,
        old_selector: str,
        dom_snapshot: str,
        top_n: int = 5,
    ) -> list[HealCandidate]:
        """
        Score all interactive elements in ``dom_snapshot`` against ``old_selector``.

        Args:
            old_selector: The failing CSS/XPath/Playwright selector string.
            dom_snapshot: Raw HTML of the page at the point of failure.
            top_n: Maximum candidates to return.

        Returns:
            Ranked :class:`HealCandidate` list (highest confidence first).
        """
        elements = self._parse_dom(dom_snapshot)
        if not elements:
            logger.warning("No interactive elements found in DOM snapshot.")
            return []

        parsed = self._parse_selector(old_selector)
        candidates: list[HealCandidate] = []

        for elem in elements:
            score, reasons = self._score(elem, parsed)
            if score > 0.05:
                candidates.append(
                    HealCandidate(
                        selector=old_selector,
                        playwright_locator=elem.best_playwright_locator(),
                        confidence=round(min(score, 1.0), 4),
                        match_reasons=reasons,
                    )
                )

        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:top_n]

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_dom(snapshot: str) -> list[_Element]:
        parser = _DOMParser()
        try:
            parser.feed(snapshot)
        except Exception as exc:
            logger.warning("DOM parse error (partial results may exist): %s", exc)
        return parser.elements

    @staticmethod
    def _parse_selector(selector: str) -> dict[str, str]:
        """Extract heuristic component parts from a CSS/XPath/PW selector string."""
        result: dict[str, str] = {"raw": selector}
        # id
        m = re.search(r"#([\w-]+)", selector)
        if m:
            result["id"] = m.group(1)
        # classes
        classes = re.findall(r"\.([\w-]+)", selector)
        if classes:
            result["classes"] = " ".join(classes)
        # text / name from PW selectors  getByText('Login')
        m2 = re.search(r"""(?:getByText|getByRole|getByLabel)\(['"]([^'"]+)['"]""", selector)
        if m2:
            result["text"] = m2.group(1)
        # aria-label attr  [aria-label="Login"]
        m3 = re.search(r"""aria-label=['"]([^'"]+)['"]""", selector)
        if m3:
            result["aria"] = m3.group(1)
        # placeholder
        m4 = re.search(r"""placeholder=['"]([^'"]+)['"]""", selector)
        if m4:
            result["placeholder"] = m4.group(1)
        # data-testid
        m5 = re.search(r"""data-testid=['"]([^'"]+)['"]""", selector)
        if m5:
            result["testid"] = m5.group(1)
        return result

    @staticmethod
    def _fuzzy(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _score(
        self, elem: _Element, parsed: dict[str, str]
    ) -> tuple[float, list[str]]:
        total = 0.0
        reasons: list[str] = []

        # id exact match (+0.40)
        if parsed.get("id") and elem.elem_id:
            if parsed["id"].lower() == elem.elem_id.lower():
                total += 0.40
                reasons.append(f"id exact match: #{elem.elem_id}")

        # aria-label / name fuzzy (+0.30)
        aria_target = parsed.get("aria") or parsed.get("text") or ""
        aria_score = self._fuzzy(aria_target, elem.aria_label)
        if aria_score > 0.6:
            weight = 0.30 * aria_score
            total += weight
            reasons.append(f"aria-label fuzzy ({aria_score:.2f}): '{elem.aria_label}'")

        # text content fuzzy (+0.20)
        text_target = parsed.get("text", "")
        text_score = self._fuzzy(text_target, elem.text.strip())
        if text_score > 0.5:
            weight = 0.20 * text_score
            total += weight
            reasons.append(f"text content fuzzy ({text_score:.2f}): '{elem.text.strip()[:40]}'")

        # placeholder fuzzy (+0.10 contribution from aria slot)
        if parsed.get("placeholder"):
            ph_score = self._fuzzy(parsed["placeholder"], elem.placeholder)
            if ph_score > 0.6:
                total += 0.20 * ph_score
                reasons.append(f"placeholder fuzzy ({ph_score:.2f})")

        # class overlap (+0.10)
        target_classes = set(parsed.get("classes", "").split())
        elem_classes = set(elem.classes)
        if target_classes and elem_classes:
            overlap = len(target_classes & elem_classes) / max(len(target_classes), 1)
            if overlap > 0:
                total += 0.10 * overlap
                reasons.append(f"class overlap ({overlap:.2f}): {target_classes & elem_classes}")

        # data-testid exact match (bonus)
        if parsed.get("testid") and elem.data_testid == parsed["testid"]:
            total += 0.50
            reasons.append(f"data-testid exact: {elem.data_testid}")

        return total, reasons
