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

Search backends (tried in order, all free, no API key):
  1. Wikipedia Search + Extract API  — reliable, structured, up-to-date
  2. DuckDuckGo Instant Answer API   — calculator, unit conversions, Wikipedia
     abstracts; DDG HTML is intentionally skipped (blocked in server envs)
"""

from __future__ import annotations

import html
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
# WebSearchTool
# ---------------------------------------------------------------------------

class WebSearchTool(Tool):
    """
    Perform web searches without any API key.

    Backends (tried in order):
      1. Wikipedia Search + Extract — reliable for entities, events, topics
      2. DuckDuckGo Instant Answer  — calculator answers, Wikipedia abstracts

    Registered in the tool registry and used directly by the orchestrator
    for transparent context injection.  Risk level 0 (read-only).
    """

    name = "WebSearch"

    _WIKIPEDIA_UA = "Zenus/1.0 (intent-driven OS assistant; https://github.com/Guillhermm/zenus)"
    _WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
    _DDG_API = "https://api.duckduckgo.com/"

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self._WIKIPEDIA_UA})

    # ------------------------------------------------------------------
    # Tool protocol
    # ------------------------------------------------------------------

    def dry_run(self, query: str, max_results: int = 5) -> str:
        return f"Would search Wikipedia + DuckDuckGo for: {query!r} (up to {max_results} results)"

    def execute(self, query: str, max_results: int = 5) -> str:
        results = self.search(query, max_results)
        return format_results_for_context(results)

    # ------------------------------------------------------------------
    # Public search API
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search for *query* using Wikipedia (primary) then DDG Instant Answer
        (secondary).  Returns up to *max_results* SearchResult objects.
        """
        results: List[SearchResult] = []

        # 1. Wikipedia search + extract
        results.extend(self._wikipedia_search(query, max_results))

        # 2. DDG Instant Answer for anything not covered by Wikipedia
        if len(results) < max_results:
            results.extend(self._instant_answer(query, max_results - len(results)))

        return results[:max_results]

    # ------------------------------------------------------------------
    # Internal: Wikipedia Search + Extract API
    # ------------------------------------------------------------------

    def _wikipedia_search(self, query: str, max_results: int) -> List[SearchResult]:
        """
        Full-text search on Wikipedia followed by article extract fetch.
        Returns one SearchResult per article (title + intro paragraph).
        """
        try:
            # Step 1: full-text search
            search_resp = self._session.get(
                self._WIKIPEDIA_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": max_results,
                    "srprop": "snippet",
                },
                timeout=self._timeout,
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()
        except Exception as exc:
            logger.debug("Wikipedia search failed: %s", exc)
            return []

        search_hits = search_data.get("query", {}).get("search", [])
        if not search_hits:
            return []

        titles = [h["title"] for h in search_hits[:max_results]]

        # Step 2: fetch extracts for all matched titles in one request
        try:
            extract_resp = self._session.get(
                self._WIKIPEDIA_API,
                params={
                    "action": "query",
                    "titles": "|".join(titles),
                    "prop": "extracts",
                    "exintro": "1",
                    "explaintext": "1",
                    "exsentences": "5",
                    "format": "json",
                },
                timeout=self._timeout,
            )
            extract_resp.raise_for_status()
            extract_data = extract_resp.json()
        except Exception as exc:
            logger.debug("Wikipedia extract fetch failed: %s", exc)
            # Fall back to the search snippet only
            results = []
            for h in search_hits[:max_results]:
                clean = re.sub(r"<[^>]+>", "", h.get("snippet", ""))
                if clean:
                    results.append(SearchResult(
                        title=h["title"],
                        url=f"https://en.wikipedia.org/wiki/{quote_plus(h['title'].replace(' ', '_'))}",
                        snippet=html.unescape(clean)[:300],
                        source="wikipedia:search",
                    ))
            return results

        # Build title → extract map
        pages = extract_data.get("query", {}).get("pages", {})
        extract_map: dict = {}
        for page in pages.values():
            t = page.get("title", "")
            e = page.get("extract", "").strip()
            if t and e:
                extract_map[t] = e

        results: List[SearchResult] = []
        for h in search_hits[:max_results]:
            title = h["title"]
            extract = extract_map.get(title, "")
            if not extract:
                # Use search snippet as fallback
                extract = html.unescape(re.sub(r"<[^>]+>", "", h.get("snippet", "")))
            if extract:
                results.append(SearchResult(
                    title=title,
                    url=f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
                    snippet=extract[:400],
                    source="wikipedia",
                ))
        return results

    # ------------------------------------------------------------------
    # Internal: DuckDuckGo Instant Answer API
    # ------------------------------------------------------------------

    def _instant_answer(self, query: str, max_results: int) -> List[SearchResult]:
        """DuckDuckGo Instant Answer — good for calculator/unit/simple facts."""
        try:
            resp = self._session.get(
                self._DDG_API,
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                timeout=self._timeout,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        except Exception as exc:
            logger.debug("DDG Instant Answer API failed: %s", exc)
            return []

        results: List[SearchResult] = []

        if data.get("AbstractText"):
            results.append(SearchResult(
                title=data.get("Heading", query),
                url=data.get("AbstractURL", ""),
                snippet=data["AbstractText"][:300],
                source="duckduckgo:abstract",
            ))

        if data.get("Answer") and len(results) < max_results:
            results.append(SearchResult(
                title="Answer",
                url="",
                snippet=str(data["Answer"])[:300],
                source="duckduckgo:answer",
            ))

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
