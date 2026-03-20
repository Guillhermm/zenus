"""
Web Search Tool

Zenus automatically decides when to search the web based on three signals:

  1. Knowledge gap  — calculates the months between the LLM's training cutoff
                      and today; queries about time-sensitive topics trigger
                      a search when the gap is large enough.
  2. Query type     — pattern-matching for topics that inherently require
                      current data (sports scores, software versions, news,
                      prices, weather).
  3. Q&A intent     — when the LLM flagged the request as a question
                      (is_question=True) the answer may benefit from fresh data.

The user never has to ask Zenus to search — it happens transparently and the
results are injected into the LLM context before intent translation.

Search backend:
  Primary:  DuckDuckGo Instant Answer API (free, no key)
  Fallback: DuckDuckGo HTML scraping via stdlib html.parser
"""

from __future__ import annotations

import html
import html.parser
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from urllib.parse import quote_plus

import requests

from zenus_core.tools.base import Tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"


# ---------------------------------------------------------------------------
# Time-sensitive topic patterns
# ---------------------------------------------------------------------------

_TEMPORAL_PATTERNS = [
    # Sports and live events (singular and plural)
    r"\bscores?\b", r"\bstandings?\b", r"\bchampion(?:ship)?\b", r"\bleagues?\b",
    r"\bmatch(?:es)?\b", r"\bgames?\b", r"\bfinals?\b", r"\bplayoffs?\b",
    r"\bfixtures?\b", r"\bschedules?\b", r"\bupcoming\s+(?:game|match|fixture)\b",
    r"\bnext\s+(?:game|match|fixture)\b",
    # Software versions
    r"\blatest\s+version\b", r"\bcurrent\s+version\b", r"\brelease[d]?\b",
    r"\bchangelog\b", r"\bupdate[d]?\b", r"\bnew\s+feature\b",
    # News and current events
    r"\btoday\b", r"\bthis\s+week\b", r"\bthis\s+month\b", r"\brecently\b",
    r"\bnews\b", r"\bannounce[d]?\b", r"\bbreaking\b",
    # Prices and markets
    r"\bprice[s]?\b", r"\bstock[s]?\b", r"\bcrypto\b", r"\bbitcoin\b",
    r"\bexchange\s+rate\b", r"\bcurrency\b",
    # Weather
    r"\bweather\b", r"\bforecast\b", r"\btemperature\b",
    # People and companies
    r"\bwho\s+is\s+(the\s+)?ceo\b", r"\bwho\s+owns\b", r"\bwho\s+won\b",
    # How-to for actively developed tech
    r"\bhow\s+to\s+(?:install|use|configure|setup|upgrade)\b",
]

_TEMPORAL_RE = re.compile("|".join(_TEMPORAL_PATTERNS), re.IGNORECASE)


# ---------------------------------------------------------------------------
# SearchDecisionEngine
# ---------------------------------------------------------------------------

class SearchDecisionEngine:
    """
    Decides whether to perform a web search before answering.

    Args:
        training_cutoff: ISO date string of LLM knowledge cutoff,
                         e.g. "2024-04-01". Passed from LLM config.
        gap_threshold_months: Minimum gap (in months) between cutoff and today
                              to consider a query "potentially stale".
    """

    def __init__(
        self,
        training_cutoff: str = "2024-04-01",
        gap_threshold_months: int = 6,
    ) -> None:
        self._cutoff = training_cutoff
        self._gap_threshold = gap_threshold_months

    def should_search(self, query: str) -> Tuple[bool, str]:
        """
        Return (True, reason) if a web search is warranted, else (False, "").
        """
        # Signal 1: query pattern is inherently time-sensitive
        if _TEMPORAL_RE.search(query):
            return True, "query requires current information"

        # Signal 2: knowledge gap is large enough to risk stale answers
        gap = self._knowledge_gap_months()
        if gap >= self._gap_threshold and self._looks_factual(query):
            return True, f"LLM knowledge may be {gap} months out of date"

        return False, ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _knowledge_gap_months(self) -> int:
        """Months elapsed since the LLM training cutoff."""
        try:
            cutoff = datetime.fromisoformat(self._cutoff).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - cutoff
            return int(delta.days / 30)
        except Exception:
            return 0

    @staticmethod
    def _looks_factual(query: str) -> bool:
        """Heuristic: does the query look like it's asking for a fact?"""
        factual_starters = re.compile(
            r"^(?:what|who|when|where|which|how\s+(?:many|much|old)|is\s+there|"
            r"does|did|has|have|can|will|are|were|could|tell\s+me|"
            r"can\s+you|could\s+you|do\s+you\s+know|find\s+(?:me|out))\b",
            re.IGNORECASE,
        )
        return bool(factual_starters.match(query.strip()))


# ---------------------------------------------------------------------------
# HTML snippet extractor for fallback scraping
# ---------------------------------------------------------------------------

class _SnippetExtractor(html.parser.HTMLParser):
    """Extract visible text from a small HTML fragment."""

    def __init__(self) -> None:
        super().__init__()
        self._text: List[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._text.append(stripped)

    def text(self) -> str:
        return " ".join(self._text)


# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------

class WebSearchTool(Tool):
    """
    Perform web searches via DuckDuckGo (no API key required).

    Registered in the tool registry but also used directly by the orchestrator
    for transparent context injection.  Risk level 0 (read-only).
    """

    name = "WebSearch"

    def __init__(self, timeout: float = 8.0) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Zenus/1.0 (intent-driven OS assistant; +https://github.com/Guillhermm/zenus)"
        })

    # ------------------------------------------------------------------
    # Tool protocol
    # ------------------------------------------------------------------

    def dry_run(self, query: str, max_results: int = 5) -> str:
        return f"Would search DuckDuckGo for: {query!r} (up to {max_results} results)"

    def execute(self, query: str, max_results: int = 5) -> str:
        results = self.search(query, max_results)
        return format_results_for_context(results)

    # ------------------------------------------------------------------
    # Public search API
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search the web for *query* and return up to *max_results* results.
        Falls back to HTML scraping if the Instant Answer API returns nothing.
        """
        results = self._instant_answer(query, max_results)
        if not results:
            results = self._html_fallback(query, max_results)
        return results

    # ------------------------------------------------------------------
    # Internal: DuckDuckGo Instant Answer API
    # ------------------------------------------------------------------

    def _instant_answer(self, query: str, max_results: int) -> List[SearchResult]:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        try:
            resp = self._session.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("DDG Instant Answer API failed: %s", exc)
            return []

        results: List[SearchResult] = []

        # Abstract (main answer)
        if data.get("AbstractText"):
            results.append(SearchResult(
                title=data.get("Heading", query),
                url=data.get("AbstractURL", ""),
                snippet=data["AbstractText"][:300],
                source="duckduckgo:abstract",
            ))

        # Answer box (e.g. calculator, unit conversions)
        if data.get("Answer") and len(results) < max_results:
            results.append(SearchResult(
                title="Answer",
                url="",
                snippet=str(data["Answer"])[:300],
                source="duckduckgo:answer",
            ))

        # Related topics
        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(SearchResult(
                    title=_first_sentence(topic["Text"]),
                    url=topic.get("FirstURL", ""),
                    snippet=topic["Text"][:200],
                    source="duckduckgo:related",
                ))

        return results

    # ------------------------------------------------------------------
    # Internal: HTML fallback scraping
    # ------------------------------------------------------------------

    def _html_fallback(self, query: str, max_results: int) -> List[SearchResult]:
        """Scrape DuckDuckGo HTML search results as fallback."""
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            resp = self._session.get(url, timeout=self._timeout)
            resp.raise_for_status()
            body = resp.text
        except Exception as exc:
            logger.debug("DDG HTML fallback failed: %s", exc)
            return []

        results: List[SearchResult] = []

        # DDG's HTML lite structure has changed over time.  Try several known
        # patterns in order of preference so the scraper stays resilient.
        def _find_blocks(pattern: str) -> List[str]:
            return re.findall(pattern, body, re.DOTALL | re.IGNORECASE)

        # Snippet candidates — closing tag varies (<a> or <span>)
        result_blocks = (
            _find_blocks(r'class="result__snippet"[^>]*>(.*?)</a>')
            or _find_blocks(r'class="result__snippet"[^>]*>(.*?)</span>')
            or _find_blocks(r'class="[^"]*snippet[^"]*"[^>]*>(.*?)</(?:a|span|div)>')
        )
        title_blocks = (
            _find_blocks(r'class="result__a"[^>]*>(.*?)</a>')
            or _find_blocks(r'class="[^"]*result[^"]*a[^"]*"[^>]*>(.*?)</a>')
        )
        url_blocks = (
            _find_blocks(r'class="result__url"[^>]*>(.*?)</span>')
            or _find_blocks(r'class="result__url"[^>]*>(.*?)</a>')
        )

        for i in range(min(max_results, len(result_blocks))):
            extractor = _SnippetExtractor()
            extractor.feed(result_blocks[i])
            snippet = html.unescape(extractor.text())[:300]

            title_ext = _SnippetExtractor()
            title_ext.feed(title_blocks[i] if i < len(title_blocks) else "")
            title = html.unescape(title_ext.text())

            url_text = ""
            if i < len(url_blocks):
                url_ext = _SnippetExtractor()
                url_ext.feed(url_blocks[i])
                url_text = html.unescape(url_ext.text()).strip()

            if snippet:
                results.append(SearchResult(
                    title=title or query,
                    url=url_text,
                    snippet=snippet,
                    source="duckduckgo:html",
                ))

        return results


# ---------------------------------------------------------------------------
# Context formatter
# ---------------------------------------------------------------------------

def format_results_for_context(results: List[SearchResult]) -> str:
    """
    Format search results as a compact block suitable for injection into
    the LLM context string before intent translation.
    """
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}")
        if r.snippet:
            lines.append(f"    {r.snippet}")
        if r.url:
            lines.append(f"    Source: {r.url}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_sentence(text: str) -> str:
    m = re.match(r"([^.!?]+[.!?])", text)
    return m.group(1).strip() if m else text[:80]
