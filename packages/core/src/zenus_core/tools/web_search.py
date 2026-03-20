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

Search backends:
  Primary:  Brave Search API (full web index, configure BRAVE_SEARCH_API_KEY)
  Fallback: Parallel multi-source — Wikipedia, Hacker News, GitHub, arXiv,
            Reddit, curated RSS feeds, DuckDuckGo Instant Answer.
            No API key required for fallback mode.
"""

from __future__ import annotations

import concurrent.futures
import html
import logging
import re
from html.parser import HTMLParser
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import defusedxml.ElementTree as ET

import requests

from zenus_core.tools.base import Tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Secure HTML stripping
# ---------------------------------------------------------------------------

class _SafeHTMLStripper(HTMLParser):
    """
    Strip HTML tags while *discarding* the content of <script> and <style>
    blocks.  Plain regex tag-stripping leaves script/style text in the
    output, which then enters LLM context.
    """

    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks).strip()


def _strip_html(raw: str) -> str:
    """Strip HTML tags safely, discarding <script>/<style> content."""
    if not raw:
        return ""
    stripper = _SafeHTMLStripper()
    try:
        stripper.feed(raw)
        return stripper.get_text()
    except Exception:
        # Fall back to simple regex if parser chokes on malformed HTML
        return re.sub(r"<[^>]+>", "", raw).strip()


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
    r"\bscores?\b", r"\bstandings?\b", r"\bchampion(?:ship)?\b",
    r"\bmatch(?:es)?\b", r"\bfinals?\b", r"\bplayoffs?\b",
    r"\bfixtures?\b", r"\bupcoming\s+(?:game|match|fixture)\b",
    r"\bnext\s+(?:game|match|fixture)\b",
    # Software versions (explicit version/release asks)
    r"\blatest\s+version\b", r"\bcurrent\s+version\b",
    r"\bnew\s+(?:version|release|feature)\b",
    r"\bchangelog\b", r"\brelease\s+notes?\b",
    # News and current events
    r"\btoday\b", r"\bthis\s+week\b", r"\bthis\s+month\b", r"\brecently\b",
    r"\bnews\b", r"\bannounce[d]?\b", r"\bbreaking\b",
    # Prices and markets
    r"\bprice[s]?\b", r"\bstock\s+(?:price|market|quote)\b",
    r"\bcrypto(?:currency)?\b", r"\bbitcoin\b", r"\bethereum\b",
    r"\bexchange\s+rate\b", r"\bcurrency\s+(?:rate|value|convert)\b",
    # Weather
    r"\bweather\b", r"\bforecast\b",
    # Current-status: leadership/ownership — these change without "latest" marker
    r"\bwho\s+is\s+(?:the\s+)?(?:current\s+)?(?:ceo|cto|cfo|president|prime\s+minister|"
    r"secretary|chairman|governor|mayor|chancellor|coach|manager|captain|owner|director|head)\b",
    r"\bwho\s+(?:owns|runs|leads|heads|controls|governs|founded|represents)\s",
    r"\bcurrent\s+(?:ceo|cto|cfo|president|prime\s+minister|owner|champion|leader|"
    r"coach|manager|version|release|status)\b",
    r"\bwho\s+won\b", r"\bwho\s+is\s+(?:the\s+)?(?:lead|number\s+one|top|ranked)\b",
]

_TEMPORAL_RE = re.compile("|".join(_TEMPORAL_PATTERNS), re.IGNORECASE)


# Queries that look like action commands despite starting with "can/could you".
# These should NOT be treated as factual lookups even if temporal patterns fire.
_ACTION_REQUEST_RE = re.compile(
    r"^(?:can|could|please|would\s+you)\s+(?:you\s+)?(?:"
    r"check|run|execute|start|stop|restart|kill|"
    r"install|uninstall|upgrade|update|download|upload|"
    r"open|close|create|make|build|delete|remove|move|copy|rename|"
    r"edit|write|generate|fix|deploy|launch|configure|setup|"
    r"monitor|watch|scan|list\s+(?:my|the|all)|"
    r"show\s+(?:me\s+)?(?:my\s+)?(?:files?|disk|memory|cpu|ram|processes?|"
    r"services?|logs?|status|running|usage)|"
    r"help\s+me\s+(?:install|setup|configure|create|fix|build|run|deploy)"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# SearchDecisionEngine
# ---------------------------------------------------------------------------

class SearchDecisionEngine:
    """
    Decides whether to perform a web search before answering.

    Only queries that are genuinely time-sensitive trigger a search:
    sports schedules/scores, software versions, current leadership/ownership,
    prices, weather, news, and similar topics where training data goes stale.

    Timeless factual questions ("who are the best composers?", "what is
    photosynthesis?") and action commands ("check my disk", "install Python")
    are deliberately NOT flagged for search.
    """

    def should_search(self, query: str) -> Tuple[bool, str]:
        """
        Return (True, reason) if a web search is warranted, else (False, "").
        A search is triggered only when the query matches an explicit
        time-sensitive pattern — not just because the training data is old.
        """
        if _TEMPORAL_RE.search(query):
            return True, "query requires current information"
        return False, ""

    @staticmethod
    def _looks_factual(query: str) -> bool:
        """
        Return True if the query is a factual lookup (not an action command).

        Used by the orchestrator to decide whether to bypass plan execution
        and synthesise an answer directly from search results.  Action
        commands like "can you check my disk" or "can you install Python"
        must return False so they are routed to plan execution instead.
        """
        # Action commands starting with can/could/please/would you <verb>
        if _ACTION_REQUEST_RE.match(query.strip()):
            return False
        factual_starters = re.compile(
            r"^(?:what|who|when|where|which|how\s+(?:many|much|old)|is\s+there|"
            r"does|did|has|have|will|are|were|"
            r"tell\s+me|can\s+you\s+tell|could\s+you\s+tell|"
            r"do\s+you\s+know|find\s+(?:me|out))\b",
            re.IGNORECASE,
        )
        return bool(factual_starters.match(query.strip()))


# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Query classification patterns (used for smart source routing)
# ---------------------------------------------------------------------------

_SPORTS_QUERY_RE = re.compile(
    r"\b(soccer|football|basketball|tennis|cricket|baseball|volleyball|golf|rugby|"
    r"nba|nfl|mlb|nhl|nba|f1|formula\s*1|mls|premier\s*league|la\s*liga|bundesliga|serie\s*a|"
    r"match(?:es)?|fixture|standing|champion(?:ship)?|league|playoff|tournament|"
    r"team|club|player|coach|goal|score|half.?time|transfer|palmeiras|flamengo|"
    r"manchester|barcelona|real\s+madrid)\b",
    re.IGNORECASE,
)

_TECH_QUERY_RE = re.compile(
    r"\b(software|programming|javascript|typescript|python|rust|golang|java|kotlin|swift|"
    r"react|vue|angular|node(?:\.?js)?|docker|kubernetes|k8s|api|sdk|"
    r"framework|library|github|gitlab|npm|pip|cargo|brew|apt|"
    r"linux|ubuntu|debian|fedora|macos|windows|server|cloud|aws|gcp|azure|"
    r"llm|gpt|claude|gemini|mistral|ollama|openai|anthropic)\b",
    re.IGNORECASE,
)

_ACADEMIC_QUERY_RE = re.compile(
    r"\b(research|paper|study|journal|published?|arxiv|"
    r"algorithm|theorem|proof|benchmark|dataset|survey|"
    r"machine\s+learning|deep\s+learning|neural\s+network|"
    r"reinforcement\s+learning|natural\s+language|computer\s+vision)\b",
    re.IGNORECASE,
)

_NEWS_QUERY_RE = re.compile(
    r"\b(news|breaking|announc(?:e|ed)|today|this\s+week|this\s+month|"
    r"politic(?:s|al)?|election|economy|market|inflation|recession|"
    r"war|conflict|president|prime\s+minister|government|policy)\b",
    re.IGNORECASE,
)


class WebSearchTool(Tool):
    """
    Web search with Brave Search API (primary) and a parallel multi-source
    fallback (Wikipedia, Hacker News, GitHub, arXiv, Reddit, RSS feeds,
    DuckDuckGo Instant Answer). No API key required for fallback mode;
    configure BRAVE_SEARCH_API_KEY for full web search coverage.

    Fallback sources are selected based on query type (sports, tech,
    academic, news, general) to avoid irrelevant results.
    """

    name = "WebSearch"

    _UA = "Zenus/1.0 (intent-driven OS assistant; https://github.com/Guillhermm/zenus)"

    # API endpoints
    _BRAVE_API    = "https://api.search.brave.com/res/v1/web/search"
    _HN_API       = "http://hn.algolia.com/api/v1/search"
    _GITHUB_API   = "https://api.github.com/search/repositories"
    _ARXIV_API    = "http://export.arxiv.org/api/query"
    _REDDIT_API   = "https://www.reddit.com/search.json"
    _WIKI_API     = "https://en.wikipedia.org/w/api.php"
    _DDG_API      = "https://api.duckduckgo.com/"

    # Curated RSS/Atom feeds: (url, friendly_name)
    _RSS_FEEDS = [
        ("https://feeds.bbci.co.uk/news/rss.xml",           "BBC News"),
        ("https://techcrunch.com/feed/",                    "TechCrunch"),
        ("https://www.theverge.com/rss/index.xml",          "The Verge"),
        ("https://feeds.arstechnica.com/arstechnica/index", "Ars Technica"),
    ]

    def __init__(self, timeout: float = 8.0) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self._UA})
        self._brave_key = self._load_brave_key()

    def _load_brave_key(self) -> str:
        import os
        key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
        if not key:
            try:
                from zenus_core.config.loader import get_config
                cfg = get_config()
                key = (cfg.search.brave_api_key or "") if hasattr(cfg, "search") else ""
            except Exception:
                pass
        return key.strip()

    # ------------------------------------------------------------------
    # Tool protocol
    # ------------------------------------------------------------------

    def dry_run(self, query: str, max_results: int = 5) -> str:
        mode = "Brave Search" if self._brave_key else "multi-source fallback"
        return f"Would search ({mode}) for: {query!r} (up to {max_results} results)"

    def execute(self, query: str, max_results: int = 5) -> str:
        results = self.search(query, max_results)
        return format_results_for_context(results)

    # ------------------------------------------------------------------
    # Public search API
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Primary: Brave Search. Fallback: parallel multi-source."""
        if self._brave_key:
            results = self._brave_search(query, max_results)
            if results:
                return results
        return self._fallback_search(query, max_results)

    # ------------------------------------------------------------------
    # Primary: Brave Search
    # ------------------------------------------------------------------

    def _brave_search(self, query: str, max_results: int) -> List[SearchResult]:
        """Brave Search API — full web index, no tracking."""
        try:
            resp = self._session.get(
                self._BRAVE_API,
                params={"q": query, "count": min(max_results, 20)},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self._brave_key,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("Brave Search failed: %s", exc)
            return []

        results: List[SearchResult] = []
        for item in data.get("web", {}).get("results", []):
            snippet = item.get("description") or item.get("extra_snippets", [""])[0]
            if item.get("title"):
                results.append(SearchResult(
                    title=item["title"],
                    url=item.get("url", ""),
                    snippet=snippet[:400],
                    source="brave",
                ))
        return results[:max_results]

    # ------------------------------------------------------------------
    # Query classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_query(query: str) -> str:
        """
        Classify the query into a category for smart source routing.

        Returns one of: "sports", "tech", "academic", "news", "general".
        """
        if _SPORTS_QUERY_RE.search(query):
            return "sports"
        if _ACADEMIC_QUERY_RE.search(query):
            return "academic"
        if _TECH_QUERY_RE.search(query):
            return "tech"
        if _NEWS_QUERY_RE.search(query):
            return "news"
        return "general"

    # ------------------------------------------------------------------
    # Fallback: parallel multi-source with smart routing
    # ------------------------------------------------------------------

    def _fallback_search(self, query: str, max_results: int) -> List[SearchResult]:
        """
        Run a category-appropriate subset of sources in parallel.
        Results are merged in priority order and deduplicated by URL.

        Source map by category:
          sports   → Wikipedia, Reddit, RSS
          tech     → HackerNews, GitHub, Wikipedia, RSS
          academic → arXiv, Wikipedia, HackerNews
          news     → RSS, Reddit, HackerNews, DDG
          general  → Wikipedia, DDG, RSS
        """
        category = self._classify_query(query)

        # (priority_idx, name, callable, per_source_limit)
        _SOURCES_BY_CATEGORY: Dict[str, list] = {
            "sports":   [
                (0, "wikipedia",  self._wikipedia_search,  2),
                (1, "reddit",     self._reddit_search,     3),
                (2, "rss",        self._rss_search,        2),
            ],
            "tech":     [
                (0, "hackernews", self._hackernews_search, 3),
                (1, "github",     self._github_search,     2),
                (2, "wikipedia",  self._wikipedia_search,  2),
                (3, "rss",        self._rss_search,        2),
            ],
            "academic": [
                (0, "arxiv",      self._arxiv_search,      3),
                (1, "wikipedia",  self._wikipedia_search,  2),
                (2, "hackernews", self._hackernews_search, 2),
            ],
            "news":     [
                (0, "rss",        self._rss_search,        3),
                (1, "reddit",     self._reddit_search,     2),
                (2, "hackernews", self._hackernews_search, 2),
                (3, "ddg",        self._instant_answer,    1),
            ],
            "general":  [
                (0, "wikipedia",  self._wikipedia_search,  3),
                (1, "ddg",        self._instant_answer,    2),
                (2, "rss",        self._rss_search,        2),
            ],
        }
        SOURCES = _SOURCES_BY_CATEGORY.get(category, _SOURCES_BY_CATEGORY["general"])

        bucket: Dict[int, List[SearchResult]] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:
            fmap = {
                ex.submit(fn, query, n): idx
                for idx, _name, fn, n in SOURCES
            }
            done_iter = concurrent.futures.as_completed(fmap, timeout=self._timeout + 2)
            for future in done_iter:
                idx = fmap[future]
                try:
                    bucket[idx] = future.result()
                except Exception as exc:
                    logger.debug("Fallback source %d failed: %s", idx, exc)
                    bucket[idx] = []

        # Merge in priority order, deduplicate by URL/title
        all_results: List[SearchResult] = []
        for idx in range(len(SOURCES)):
            all_results.extend(bucket.get(idx, []))

        seen: set = set()
        deduped: List[SearchResult] = []
        for r in all_results:
            key = r.url or r.title
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        return deduped[:max_results]

    # ------------------------------------------------------------------
    # Source: Wikipedia
    # ------------------------------------------------------------------

    def _wikipedia_search(self, query: str, max_results: int) -> List[SearchResult]:
        """Wikipedia Search + Extract API."""
        try:
            search_resp = self._session.get(
                self._WIKI_API,
                params={"action": "query", "list": "search", "srsearch": query,
                        "format": "json", "srlimit": max_results, "srprop": "snippet"},
                timeout=self._timeout,
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("query", {}).get("search", [])
        except Exception as exc:
            logger.debug("Wikipedia search failed: %s", exc)
            return []

        if not hits:
            return []

        titles = [h["title"] for h in hits[:max_results]]
        try:
            ext_resp = self._session.get(
                self._WIKI_API,
                params={"action": "query", "titles": "|".join(titles),
                        "prop": "extracts", "exintro": "1", "explaintext": "1",
                        "exsentences": "5", "format": "json"},
                timeout=self._timeout,
            )
            ext_resp.raise_for_status()
            pages = ext_resp.json().get("query", {}).get("pages", {})
            extract_map = {p["title"]: p.get("extract", "").strip() for p in pages.values() if "title" in p}
        except Exception:
            extract_map = {}

        results: List[SearchResult] = []
        for h in hits[:max_results]:
            title = h["title"]
            snippet = extract_map.get(title) or _strip_html(h.get("snippet", ""))
            if snippet:
                results.append(SearchResult(
                    title=title,
                    url=f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
                    snippet=snippet[:400],
                    source="wikipedia",
                ))
        return results

    # ------------------------------------------------------------------
    # Source: Hacker News (Algolia API)
    # ------------------------------------------------------------------

    def _hackernews_search(self, query: str, max_results: int) -> List[SearchResult]:
        try:
            resp = self._session.get(
                self._HN_API,
                params={"query": query, "hitsPerPage": max_results, "tags": "story"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as exc:
            logger.debug("HackerNews search failed: %s", exc)
            return []

        results: List[SearchResult] = []
        for hit in hits[:max_results]:
            title = hit.get("title", "")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            snippet = (hit.get("story_text") or title)[:300]
            if title:
                results.append(SearchResult(title=title, url=url, snippet=snippet, source="hackernews"))
        return results

    # ------------------------------------------------------------------
    # Source: GitHub repositories
    # ------------------------------------------------------------------

    def _github_search(self, query: str, max_results: int) -> List[SearchResult]:
        try:
            resp = self._session.get(
                self._GITHUB_API,
                params={"q": query, "per_page": max_results, "sort": "stars"},
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as exc:
            logger.debug("GitHub search failed: %s", exc)
            return []

        results: List[SearchResult] = []
        for item in items[:max_results]:
            desc = item.get("description") or ""
            lang = item.get("language") or "unknown"
            stars = item.get("stargazers_count", 0)
            snippet = f"{desc} | ★{stars:,} | {lang}".strip(" |")
            results.append(SearchResult(
                title=item.get("full_name", ""),
                url=item.get("html_url", ""),
                snippet=snippet[:300],
                source="github",
            ))
        return results

    # ------------------------------------------------------------------
    # Source: arXiv
    # ------------------------------------------------------------------

    def _arxiv_search(self, query: str, max_results: int) -> List[SearchResult]:
        try:
            resp = self._session.get(
                self._ARXIV_API,
                params={"search_query": f"all:{query}", "max_results": max_results, "sortBy": "relevance"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except Exception as exc:
            logger.debug("arXiv search failed: %s", exc)
            return []

        ns = {"a": "http://www.w3.org/2005/Atom"}
        results: List[SearchResult] = []
        for entry in root.findall("a:entry", ns):
            title_el = entry.find("a:title", ns)
            summary_el = entry.find("a:summary", ns)
            link_el = entry.find("a:link[@rel='alternate']", ns)
            if link_el is None:
                link_el = entry.find("a:id", ns)
            title = title_el.text.strip() if title_el is not None else ""
            summary = (summary_el.text or "").strip()
            url = (link_el.attrib.get("href") if link_el is not None else
                   (link_el.text if link_el is not None else ""))
            if title:
                results.append(SearchResult(title=title, url=url or "", snippet=summary[:300], source="arxiv"))
        return results

    # ------------------------------------------------------------------
    # Source: Reddit
    # ------------------------------------------------------------------

    def _reddit_search(self, query: str, max_results: int) -> List[SearchResult]:
        try:
            resp = self._session.get(
                self._REDDIT_API,
                params={"q": query, "limit": max_results, "sort": "relevance", "type": "link"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
        except Exception as exc:
            logger.debug("Reddit search failed: %s", exc)
            return []

        results: List[SearchResult] = []
        for post in posts[:max_results]:
            p = post.get("data", {})
            title = p.get("title", "")
            selftext = (p.get("selftext") or "")[:200]
            sub = p.get("subreddit", "")
            url = f"https://reddit.com{p.get('permalink', '')}"
            snippet = f"r/{sub} — {selftext or title}"
            if title:
                results.append(SearchResult(title=title, url=url, snippet=snippet[:300], source="reddit"))
        return results

    # ------------------------------------------------------------------
    # Source: RSS/Atom feeds (curated)
    # ------------------------------------------------------------------

    def _rss_search(self, query: str, max_results: int) -> List[SearchResult]:
        """
        Fetch curated RSS/Atom feeds in parallel and filter items whose
        title or description contains any query keyword.
        """
        keywords = {w.lower() for w in re.split(r'\W+', query) if len(w) > 3}
        results: List[SearchResult] = []

        def _fetch_feed(feed_url: str, feed_name: str) -> List[SearchResult]:
            try:
                resp = self._session.get(feed_url, timeout=min(self._timeout, 5))
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
            except Exception:
                return []

            feed_results: List[SearchResult] = []
            # Atom feeds use {namespace}entry; RSS uses item
            ns_atom = "http://www.w3.org/2005/Atom"
            entries = root.findall(f"{{{ns_atom}}}entry") or root.findall(".//item")

            for entry in entries:
                # Title
                title_el = entry.find(f"{{{ns_atom}}}title") or entry.find("title")
                title = (title_el.text or "").strip() if title_el is not None else ""
                # Description / summary
                desc_el = (entry.find(f"{{{ns_atom}}}summary") or
                           entry.find(f"{{{ns_atom}}}content") or
                           entry.find("description"))
                desc = _strip_html(desc_el.text or "") if desc_el is not None else ""
                # Link
                link_el = entry.find(f"{{{ns_atom}}}link") or entry.find("link")
                if link_el is not None:
                    url = link_el.attrib.get("href") or (link_el.text or "").strip()
                else:
                    url = ""

                # Relevance filter: at least one keyword must appear
                combined = (title + " " + desc).lower()
                if any(kw in combined for kw in keywords):
                    feed_results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=f"[{feed_name}] {desc[:200] or title}",
                        source="rss",
                    ))
                if len(feed_results) >= max_results:
                    break
            return feed_results

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self._RSS_FEEDS)) as ex:
            futs = [ex.submit(_fetch_feed, url, name) for url, name in self._RSS_FEEDS]
            for f in concurrent.futures.as_completed(futs, timeout=self._timeout):
                try:
                    results.extend(f.result())
                except Exception:
                    pass

        return results[:max_results]

    # ------------------------------------------------------------------
    # Source: DuckDuckGo Instant Answer
    # ------------------------------------------------------------------

    def _instant_answer(self, query: str, max_results: int) -> List[SearchResult]:
        """DDG Instant Answer — good for calculator/unit/simple factual queries."""
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
            logger.debug("DDG Instant Answer failed: %s", exc)
            return []

        results: List[SearchResult] = []
        if data.get("AbstractText"):
            results.append(SearchResult(
                title=data.get("Heading", query),
                url=data.get("AbstractURL", ""),
                snippet=data["AbstractText"][:300],
                source="duckduckgo",
            ))
        if data.get("Answer") and len(results) < max_results:
            results.append(SearchResult(title="Answer", url="", snippet=str(data["Answer"])[:300], source="duckduckgo"))
        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(SearchResult(
                    title=_first_sentence(topic["Text"]),
                    url=topic.get("FirstURL", ""),
                    snippet=topic["Text"][:200],
                    source="duckduckgo",
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
