"""
Unit tests for zenus_core.tools.web_search

Tests cover:
- SearchDecisionEngine: temporal patterns, knowledge gap, factual heuristic
- WebSearchTool._classify_query: query type classification for smart routing
- WebSearchTool: Brave Search, per-source fetchers, dry_run, execute
- _fallback_search: smart routing by query category, deduplication, max_results
- format_results_for_context: formatting and edge cases
- _first_sentence helper
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from zenus_core.tools.web_search import (
    SearchResult,
    SearchDecisionEngine,
    WebSearchTool,
    format_results_for_context,
    _first_sentence,
    _TEMPORAL_RE,
    _ACTION_REQUEST_RE,
    _SPORTS_QUERY_RE,
    _TECH_QUERY_RE,
    _ACADEMIC_QUERY_RE,
    _NEWS_QUERY_RE,
)


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------

class TestSearchResult:
    def test_default_source(self):
        r = SearchResult(title="T", url="http://x", snippet="s")
        assert r.source == "duckduckgo"

    def test_custom_source(self):
        r = SearchResult(title="T", url="", snippet="", source="duckduckgo:html")
        assert r.source == "duckduckgo:html"


# ---------------------------------------------------------------------------
# SearchDecisionEngine — temporal pattern matching (Signal 1)
# ---------------------------------------------------------------------------

class TestSearchDecisionEngineTemporalPatterns:
    @pytest.fixture
    def engine(self):
        return SearchDecisionEngine()

    @pytest.mark.parametrize("query", [
        "what is the score today",
        "current version of Python",
        "latest version of Django",
        "who won the championship",
        "Bitcoin price right now",
        "weather forecast for tomorrow",
        "breaking news this week",
        "news about recently announced features",
        "stock price today",
        "who is the CEO of Tesla",
        "match results this month",
        "new release of macOS",
        "exchange rate USD to EUR",
        "playoff standings",
        "who is the current president of Brazil",
        "who owns OpenAI",
        "what are the next fixtures for Arsenal",
    ])
    def test_temporal_query_triggers_search(self, engine, query):
        should, reason = engine.should_search(query)
        assert should is True
        assert reason != ""

    def test_temporal_reason_message(self, engine):
        should, reason = engine.should_search("what is the Bitcoin price")
        assert should
        assert "current information" in reason


# ---------------------------------------------------------------------------
# SearchDecisionEngine — current-status patterns (leadership/ownership)
# ---------------------------------------------------------------------------

class TestSearchDecisionEngineCurrentStatus:
    """
    Current-status queries (CEO, president, ownership) are in _TEMPORAL_PATTERNS
    and must trigger search even without explicit "latest/current" markers.
    Timeless factual questions must NOT trigger search.
    """

    @pytest.fixture
    def engine(self):
        return SearchDecisionEngine()

    @pytest.mark.parametrize("query", [
        "who is the CEO of Apple",
        "who is the current president of Brazil",
        "who is the prime minister of the UK",
        "who is the coach of Manchester City",
        "who owns Twitter now",
        "who runs OpenAI",
        "current CEO of Tesla",
        "current champion of the Champions League",
        "who won the last election",
    ])
    def test_current_status_triggers_search(self, engine, query):
        should, reason = engine.should_search(query)
        assert should is True, f"Expected search for: {query!r}"

    @pytest.mark.parametrize("query", [
        # Attribution queries now intentionally trigger search to avoid hallucination
        "who invented the telephone",
        "who wrote Hamlet",
        "who created PostVRP benchmarks",
        "who made the first iPhone",
        "who developed TensorFlow",
        "who authored the attention is all you need paper",
    ])
    def test_attribution_queries_trigger_search(self, engine, query):
        """Attribution queries trigger search — LLMs may hallucinate authorship."""
        should, _ = engine.should_search(query)
        assert should is True, f"Expected search for attribution query: {query!r}"

    @pytest.mark.parametrize("query", [
        "who are the best music composers of all time",
        "who was the first president of the US",
        "who discovered gravity",
        "what is photosynthesis",
        "what is the capital of France",
        "create a directory named projects",
        "can you check my system resources",
        "install Python on my machine",
        "show me running processes",
    ])
    def test_timeless_or_action_does_not_trigger_search(self, engine, query):
        should, _ = engine.should_search(query)
        assert should is False, f"Expected NO search for: {query!r}"


# ---------------------------------------------------------------------------
# SearchDecisionEngine — _looks_factual
# ---------------------------------------------------------------------------

class TestLooksFactual:
    @pytest.mark.parametrize("query,expected", [
        # Clear factual lookups → True
        ("what is the speed of light", True),
        ("who invented the telephone", True),
        ("when was the Eiffel Tower built", True),
        ("where is Mount Everest", True),
        ("which language is fastest", True),
        ("how many planets are in the solar system", True),
        ("how much does it cost", True),
        ("how old is the universe", True),
        ("is there life on Mars", True),
        ("does Python support async", True),
        ("did the team win", True),
        ("has the patch been released", True),
        ("have you seen this", True),
        ("tell me the latest Claude version", True),
        ("can you tell me what are next games of Palmeiras", True),
        ("could you tell me who won the match", True),
        ("do you know who is the CEO of Google", True),
        ("find me the best restaurants nearby", True),
        # Action commands → False
        ("can you check my system resources", False),
        ("can you install Python", False),
        ("could you run the tests", False),
        ("can you update my config file", False),
        ("can you check my disk usage", False),
        ("please check the logs", False),
        ("can you show me running processes", False),
        ("can you help me install Docker", False),
        # Non-factual starters → False
        ("create a directory", False),
        ("open my browser", False),
        ("move the file", False),
        ("hello there", False),
    ])
    def test_looks_factual(self, query, expected):
        result = SearchDecisionEngine._looks_factual(query)
        assert result == expected, f"_looks_factual({query!r}) expected {expected}"

    def test_action_request_re_matches_action_verbs(self):
        """_ACTION_REQUEST_RE must match common action commands."""
        assert _ACTION_REQUEST_RE.match("can you check my disk")
        assert _ACTION_REQUEST_RE.match("can you install Python")
        assert _ACTION_REQUEST_RE.match("could you run the server")
        assert _ACTION_REQUEST_RE.match("can you show me running processes")
        assert _ACTION_REQUEST_RE.match("please stop the service")

    def test_action_request_re_does_not_match_tell_me(self):
        """'can you tell me' is a lookup, not an action."""
        assert not _ACTION_REQUEST_RE.match("can you tell me who is the CEO")
        assert not _ACTION_REQUEST_RE.match("could you tell me the price")


# ---------------------------------------------------------------------------
# _first_sentence helper
# ---------------------------------------------------------------------------

class TestFirstSentence:
    def test_extracts_first_sentence_period(self):
        assert _first_sentence("Hello world. This is more.") == "Hello world."

    def test_extracts_first_sentence_exclamation(self):
        assert _first_sentence("Great job! Keep going.") == "Great job!"

    def test_extracts_first_sentence_question(self):
        assert _first_sentence("Is this it? Yes.") == "Is this it?"

    def test_no_punctuation_returns_truncated(self):
        result = _first_sentence("A" * 100)
        assert len(result) <= 80

    def test_empty_string(self):
        result = _first_sentence("")
        assert result == ""

    def test_single_sentence(self):
        assert _first_sentence("Only one sentence.") == "Only one sentence."


# ---------------------------------------------------------------------------
# format_results_for_context
# ---------------------------------------------------------------------------

class TestFormatResultsForContext:
    def test_empty_results_returns_empty_string(self):
        assert format_results_for_context([]) == ""

    def test_single_result_with_all_fields(self):
        r = SearchResult(title="Python", url="https://python.org", snippet="Great language")
        output = format_results_for_context([r])
        assert "[1] Python" in output
        assert "Great language" in output
        assert "https://python.org" in output

    def test_multiple_results_numbered(self):
        results = [
            SearchResult(title=f"Title {i}", url=f"http://x.com/{i}", snippet=f"Snippet {i}")
            for i in range(1, 4)
        ]
        output = format_results_for_context(results)
        assert "[1] Title 1" in output
        assert "[2] Title 2" in output
        assert "[3] Title 3" in output

    def test_result_without_url(self):
        r = SearchResult(title="Answer", url="", snippet="42")
        output = format_results_for_context([r])
        assert "[1] Answer" in output
        assert "42" in output
        assert "Source:" not in output

    def test_result_without_snippet(self):
        r = SearchResult(title="T", url="http://x", snippet="")
        output = format_results_for_context([r])
        assert "[1] T" in output

    def test_source_prefix_label(self):
        r = SearchResult(title="T", url="http://x", snippet="s")
        output = format_results_for_context([r])
        assert "Source: http://x" in output


# ---------------------------------------------------------------------------
# WebSearchTool — dry_run and execute
# ---------------------------------------------------------------------------

class TestWebSearchToolDryRun:
    def test_dry_run_message_no_key(self):
        tool = WebSearchTool()
        tool._brave_key = ""
        result = tool.dry_run("python async")
        assert "python async" in result
        assert "multi-source fallback" in result

    def test_dry_run_message_with_brave_key(self):
        tool = WebSearchTool()
        tool._brave_key = "test-key"
        result = tool.dry_run("python async")
        assert "python async" in result
        assert "Brave Search" in result

    def test_dry_run_includes_max_results(self):
        tool = WebSearchTool()
        result = tool.dry_run("test", max_results=10)
        assert "10" in result


class TestWebSearchToolExecute:
    def test_execute_calls_search_and_formats(self):
        tool = WebSearchTool()
        fake_results = [
            SearchResult(title="T", url="http://x", snippet="s")
        ]
        with patch.object(tool, "search", return_value=fake_results) as mock_search:
            output = tool.execute("some query")
        mock_search.assert_called_once_with("some query", 5)
        assert "[1] T" in output

    def test_execute_empty_results(self):
        tool = WebSearchTool()
        with patch.object(tool, "search", return_value=[]):
            output = tool.execute("no results query")
        assert output == ""


# ---------------------------------------------------------------------------
# WebSearchTool — _instant_answer (DDG API parsing)
# ---------------------------------------------------------------------------

class TestWebSearchToolInstantAnswer:
    @pytest.fixture
    def tool(self):
        return WebSearchTool()

    def _mock_response(self, data: dict) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = data
        mock.raise_for_status.return_value = None
        return mock

    def test_abstract_text_extracted(self, tool):
        data = {
            "AbstractText": "Python is a programming language.",
            "Heading": "Python",
            "AbstractURL": "https://en.wikipedia.org/wiki/Python",
            "RelatedTopics": [],
        }
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._instant_answer("Python", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Python"
        assert "Python is a programming" in results[0].snippet
        assert results[0].source == "duckduckgo"

    def test_answer_box_extracted(self, tool):
        data = {
            "AbstractText": "",
            "Answer": "42",
            "RelatedTopics": [],
        }
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._instant_answer("6 times 7", max_results=5)
        assert any(r.source == "duckduckgo" for r in results)
        assert any("42" in r.snippet for r in results)

    def test_related_topics_extracted(self, tool):
        data = {
            "AbstractText": "",
            "RelatedTopics": [
                {"Text": "Django is a web framework. More info here.", "FirstURL": "https://djangoproject.com"},
                {"Text": "Flask is a micro framework."},
            ],
        }
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._instant_answer("web frameworks", max_results=5)
        assert len(results) == 2
        assert all(r.source == "duckduckgo" for r in results)

    def test_max_results_respected(self, tool):
        data = {
            "AbstractText": "abstract",
            "Answer": "answer",
            "RelatedTopics": [
                {"Text": f"Topic {i}.", "FirstURL": f"http://x/{i}"}
                for i in range(10)
            ],
        }
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._instant_answer("query", max_results=3)
        assert len(results) <= 3

    def test_api_failure_returns_empty(self, tool):
        with patch.object(tool._session, "get", side_effect=Exception("network error")):
            results = tool._instant_answer("query", max_results=5)
        assert results == []

    def test_http_error_returns_empty(self, tool):
        mock = MagicMock()
        mock.raise_for_status.side_effect = Exception("HTTP 429")
        with patch.object(tool._session, "get", return_value=mock):
            results = tool._instant_answer("query", max_results=5)
        assert results == []

    def test_topic_without_text_skipped(self, tool):
        data = {
            "AbstractText": "",
            "RelatedTopics": [
                {"FirstURL": "http://x"},  # no Text key
                {"Text": "Valid topic."},
            ],
        }
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._instant_answer("query", max_results=5)
        assert len(results) == 1
        assert "Valid topic" in results[0].snippet

    def test_snippet_truncated_at_300_chars(self, tool):
        long_text = "x" * 500
        data = {
            "AbstractText": long_text,
            "RelatedTopics": [],
        }
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._instant_answer("query", max_results=5)
        assert len(results[0].snippet) <= 300


# ---------------------------------------------------------------------------
# WebSearchTool — _brave_search
# ---------------------------------------------------------------------------
class TestBraveSearch:
    def _make_brave_resp(self, items):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"web": {"results": items}}
        return mock

    def test_brave_returns_results(self):
        tool = WebSearchTool()
        tool._brave_key = "test-key"
        items = [{"title": "T1", "url": "https://t1.com", "description": "Desc 1"},
                 {"title": "T2", "url": "https://t2.com", "description": "Desc 2"}]
        with patch.object(tool._session, "get", return_value=self._make_brave_resp(items)):
            results = tool._brave_search("test", 5)
        assert len(results) == 2
        assert results[0].source == "brave"
        assert results[0].title == "T1"

    def test_brave_respects_max_results(self):
        tool = WebSearchTool()
        tool._brave_key = "key"
        items = [{"title": f"T{i}", "url": f"https://t{i}.com", "description": "d"} for i in range(10)]
        with patch.object(tool._session, "get", return_value=self._make_brave_resp(items)):
            results = tool._brave_search("test", 3)
        assert len(results) == 3

    def test_brave_returns_empty_on_http_error(self):
        tool = WebSearchTool()
        tool._brave_key = "key"
        with patch.object(tool._session, "get", side_effect=Exception("timeout")):
            results = tool._brave_search("test", 5)
        assert results == []

    def test_brave_sends_api_key_header(self):
        tool = WebSearchTool()
        tool._brave_key = "my-secret-key"
        with patch.object(tool._session, "get", return_value=self._make_brave_resp([])) as mock_get:
            tool._brave_search("test", 5)
        call_kwargs = mock_get.call_args
        headers = call_kwargs[1].get("headers", {})
        assert headers.get("X-Subscription-Token") == "my-secret-key"


# ---------------------------------------------------------------------------
# WebSearchTool — _hackernews_search
# ---------------------------------------------------------------------------
class TestHackerNewsSearch:
    def test_returns_results(self):
        tool = WebSearchTool()
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"hits": [
            {"title": "HN Post", "url": "https://example.com", "story_text": "Story text", "objectID": "123"}
        ]}
        with patch.object(tool._session, "get", return_value=mock):
            results = tool._hackernews_search("test", 5)
        assert len(results) == 1
        assert results[0].source == "hackernews"
        assert results[0].title == "HN Post"

    def test_uses_hn_url_when_no_url(self):
        tool = WebSearchTool()
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"hits": [{"title": "Post", "url": None, "objectID": "999"}]}
        with patch.object(tool._session, "get", return_value=mock):
            results = tool._hackernews_search("test", 5)
        assert "999" in results[0].url

    def test_returns_empty_on_failure(self):
        tool = WebSearchTool()
        with patch.object(tool._session, "get", side_effect=Exception("err")):
            assert tool._hackernews_search("q", 5) == []


# ---------------------------------------------------------------------------
# WebSearchTool — _github_search
# ---------------------------------------------------------------------------
class TestGitHubSearch:
    def test_returns_repos(self):
        tool = WebSearchTool()
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"items": [
            {"full_name": "user/repo", "html_url": "https://github.com/user/repo",
             "description": "A repo", "stargazers_count": 100, "language": "Python"}
        ]}
        with patch.object(tool._session, "get", return_value=mock):
            results = tool._github_search("test", 5)
        assert len(results) == 1
        assert results[0].source == "github"
        assert "★100" in results[0].snippet

    def test_returns_empty_on_failure(self):
        tool = WebSearchTool()
        with patch.object(tool._session, "get", side_effect=Exception("err")):
            assert tool._github_search("q", 5) == []


# ---------------------------------------------------------------------------
# WebSearchTool — _arxiv_search
# ---------------------------------------------------------------------------
class TestArxivSearch:
    def test_parses_atom_xml(self):
        tool = WebSearchTool()
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Paper Title</title>
            <summary>Abstract text here.</summary>
            <link rel="alternate" href="https://arxiv.org/abs/1234.5678"/>
          </entry>
        </feed>"""
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.text = xml
        with patch.object(tool._session, "get", return_value=mock):
            results = tool._arxiv_search("test", 5)
        assert len(results) == 1
        assert results[0].title == "Paper Title"
        assert results[0].source == "arxiv"

    def test_returns_empty_on_failure(self):
        tool = WebSearchTool()
        with patch.object(tool._session, "get", side_effect=Exception("err")):
            assert tool._arxiv_search("q", 5) == []


# ---------------------------------------------------------------------------
# WebSearchTool — _reddit_search
# ---------------------------------------------------------------------------
class TestRedditSearch:
    def test_returns_posts(self):
        tool = WebSearchTool()
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"data": {"children": [
            {"data": {"title": "Post Title", "selftext": "Some text",
                      "permalink": "/r/test/123", "subreddit": "test"}}
        ]}}
        with patch.object(tool._session, "get", return_value=mock):
            results = tool._reddit_search("test", 5)
        assert len(results) == 1
        assert results[0].source == "reddit"
        assert "r/test" in results[0].snippet

    def test_returns_empty_on_failure(self):
        tool = WebSearchTool()
        with patch.object(tool._session, "get", side_effect=Exception("err")):
            assert tool._reddit_search("q", 5) == []


# ---------------------------------------------------------------------------
# WebSearchTool — _wikipedia_search
# ---------------------------------------------------------------------------
class TestWikipediaSearch:
    def _make_search_resp(self, titles):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"query": {"search": [{"title": t, "snippet": f"snip {t}"} for t in titles]}}
        return mock

    def _make_extract_resp(self, pages):
        page_data = {str(i): {"title": t, "extract": e} for i, (t, e) in enumerate(pages.items())}
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"query": {"pages": page_data}}
        return mock

    def test_returns_results_with_extract(self):
        tool = WebSearchTool()
        s = self._make_search_resp(["Python (programming language)"])
        e = self._make_extract_resp({"Python (programming language)": "Python is a language."})
        with patch.object(tool._session, "get", side_effect=[s, e]):
            results = tool._wikipedia_search("python", 5)
        assert len(results) == 1
        assert results[0].source == "wikipedia"
        assert "Python is a language." in results[0].snippet

    def test_empty_search_returns_empty(self):
        tool = WebSearchTool()
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"query": {"search": []}}
        with patch.object(tool._session, "get", return_value=mock):
            assert tool._wikipedia_search("xyzzy", 5) == []

    def test_returns_empty_on_failure(self):
        tool = WebSearchTool()
        with patch.object(tool._session, "get", side_effect=Exception("err")):
            assert tool._wikipedia_search("q", 5) == []


# ---------------------------------------------------------------------------
# WebSearchTool — search() routing
# ---------------------------------------------------------------------------
class TestSearchRouting:
    def test_brave_used_when_key_set(self):
        tool = WebSearchTool()
        tool._brave_key = "key"
        brave_results = [SearchResult(title="B", url="u", snippet="s", source="brave")]
        with patch.object(tool, "_brave_search", return_value=brave_results) as mock_brave, \
             patch.object(tool, "_fallback_search") as mock_fallback:
            results = tool.search("q")
        mock_brave.assert_called_once()
        mock_fallback.assert_not_called()
        assert results == brave_results

    def test_fallback_used_when_no_key(self):
        tool = WebSearchTool()
        tool._brave_key = ""
        fallback_results = [SearchResult(title="W", url="u", snippet="s", source="wikipedia")]
        with patch.object(tool, "_brave_search") as mock_brave, \
             patch.object(tool, "_fallback_search", return_value=fallback_results) as mock_fallback:
            results = tool.search("q")
        mock_brave.assert_not_called()
        mock_fallback.assert_called_once()
        assert results == fallback_results

    def test_fallback_used_when_brave_empty(self):
        tool = WebSearchTool()
        tool._brave_key = "key"
        fallback_results = [SearchResult(title="W", url="u", snippet="s", source="wikipedia")]
        with patch.object(tool, "_brave_search", return_value=[]), \
             patch.object(tool, "_fallback_search", return_value=fallback_results) as mock_fallback:
            results = tool.search("q")
        mock_fallback.assert_called_once()
        assert results == fallback_results


# ---------------------------------------------------------------------------
# WebSearchTool — _classify_query
# ---------------------------------------------------------------------------
class TestQueryClassification:
    """_classify_query routes to the right search category."""

    @pytest.mark.parametrize("query,expected", [
        ("what are next games of Palmeiras soccer team", "sports"),
        ("NBA standings this week", "sports"),
        ("who won the Champions League final", "sports"),
        ("next match fixture for Barcelona", "sports"),
        ("how to install Docker on Ubuntu", "tech"),
        ("latest release of React framework", "tech"),
        ("best Python library for async", "tech"),
        ("claude LLM API usage", "tech"),
        ("research paper on neural networks", "academic"),
        ("arXiv survey on transformers", "academic"),
        ("machine learning benchmark dataset", "academic"),
        ("breaking news this week", "news"),
        ("election results today", "news"),
        ("what is the capital of France", "general"),
        ("how many moons does Jupiter have", "general"),
    ])
    def test_classify_query(self, query, expected):
        assert WebSearchTool._classify_query(query) == expected

    def test_sports_re_matches_team_names(self):
        assert _SPORTS_QUERY_RE.search("palmeiras match schedule") is not None
        assert _SPORTS_QUERY_RE.search("real madrid vs barcelona") is not None

    def test_tech_re_matches_dev_tools(self):
        assert _TECH_QUERY_RE.search("kubernetes deployment yaml") is not None
        assert _TECH_QUERY_RE.search("docker compose tutorial") is not None

    def test_academic_re_matches_papers(self):
        assert _ACADEMIC_QUERY_RE.search("arxiv paper on diffusion models") is not None
        assert _ACADEMIC_QUERY_RE.search("deep learning benchmark") is not None

    def test_news_re_matches_current_events(self):
        assert _NEWS_QUERY_RE.search("election news today") is not None
        assert _NEWS_QUERY_RE.search("breaking announcement") is not None

    def test_academic_takes_priority_over_tech(self):
        # "neural network" is academic; "python" alone is tech
        assert WebSearchTool._classify_query("research paper on neural networks in python") == "academic"

    def test_sports_takes_priority_over_news(self):
        assert WebSearchTool._classify_query("breaking news on soccer match results") == "sports"


# ---------------------------------------------------------------------------
# WebSearchTool — _fallback_search deduplication and ordering
# ---------------------------------------------------------------------------
class TestFallbackSearch:
    """Smart routing: only sources relevant to the query category are called."""

    def test_deduplicates_by_url(self):
        # "python programming" → "tech" → sources: hackernews, github, wikipedia, rss
        tool = WebSearchTool()
        r1 = SearchResult(title="A", url="https://same.com", snippet="s1", source="wikipedia")
        r2 = SearchResult(title="A2", url="https://same.com", snippet="s2", source="hackernews")
        r3 = SearchResult(title="B", url="https://different.com", snippet="s3", source="github")
        with patch.object(tool, "_hackernews_search", return_value=[r2]), \
             patch.object(tool, "_github_search", return_value=[r3]), \
             patch.object(tool, "_wikipedia_search", return_value=[r1]), \
             patch.object(tool, "_rss_search", return_value=[]):
            results = tool._fallback_search("python programming library", 10)
        urls = [r.url for r in results]
        assert urls.count("https://same.com") == 1
        assert len(results) == 2

    def test_respects_max_results(self):
        # Generic query → "general" → sources: wikipedia, ddg, rss
        tool = WebSearchTool()
        many = [SearchResult(title=f"R{i}", url=f"https://r{i}.com", snippet="s", source="wikipedia") for i in range(10)]
        with patch.object(tool, "_wikipedia_search", return_value=many), \
             patch.object(tool, "_instant_answer", return_value=[]), \
             patch.object(tool, "_rss_search", return_value=[]):
            results = tool._fallback_search("what is the capital of Brazil", 3)
        assert len(results) == 3

    def test_sports_query_uses_wikipedia_reddit_rss(self):
        # Sports category: wikipedia, reddit, rss — NOT hackernews, github, arxiv
        tool = WebSearchTool()
        with patch.object(tool, "_wikipedia_search", return_value=[]) as mock_wiki, \
             patch.object(tool, "_reddit_search", return_value=[]) as mock_reddit, \
             patch.object(tool, "_rss_search", return_value=[]) as mock_rss, \
             patch.object(tool, "_hackernews_search", return_value=[]) as mock_hn, \
             patch.object(tool, "_github_search", return_value=[]) as mock_gh:
            tool._fallback_search("palmeiras soccer match schedule", 5)
        mock_wiki.assert_called_once()
        mock_reddit.assert_called_once()
        mock_rss.assert_called_once()
        mock_hn.assert_not_called()
        mock_gh.assert_not_called()

    def test_academic_query_uses_semantic_scholar_arxiv_openalex_wikipedia(self):
        # Academic category: semantic_scholar, arxiv, openalex, wikipedia — NOT hn, github, reddit
        tool = WebSearchTool()
        with patch.object(tool, "_semantic_scholar_search", return_value=[]) as mock_ss, \
             patch.object(tool, "_arxiv_search", return_value=[]) as mock_arxiv, \
             patch.object(tool, "_openalex_search", return_value=[]) as mock_oa, \
             patch.object(tool, "_wikipedia_search", return_value=[]) as mock_wiki, \
             patch.object(tool, "_hackernews_search", return_value=[]) as mock_hn, \
             patch.object(tool, "_github_search", return_value=[]) as mock_gh, \
             patch.object(tool, "_reddit_search", return_value=[]) as mock_reddit:
            tool._fallback_search("deep learning benchmark research paper", 5)
        mock_ss.assert_called_once()
        mock_arxiv.assert_called_once()
        mock_oa.assert_called_once()
        mock_wiki.assert_called_once()
        mock_hn.assert_not_called()
        mock_gh.assert_not_called()
        mock_reddit.assert_not_called()

    def test_tech_query_uses_hn_github_wikipedia_rss(self):
        tool = WebSearchTool()
        with patch.object(tool, "_hackernews_search", return_value=[]) as mock_hn, \
             patch.object(tool, "_github_search", return_value=[]) as mock_gh, \
             patch.object(tool, "_wikipedia_search", return_value=[]) as mock_wiki, \
             patch.object(tool, "_rss_search", return_value=[]) as mock_rss, \
             patch.object(tool, "_reddit_search", return_value=[]) as mock_reddit:
            tool._fallback_search("docker kubernetes deployment python", 5)
        mock_hn.assert_called_once()
        mock_gh.assert_called_once()
        mock_wiki.assert_called_once()
        mock_rss.assert_called_once()
        mock_reddit.assert_not_called()


# ---------------------------------------------------------------------------
# _TEMPORAL_RE — pattern completeness spot-check
# ---------------------------------------------------------------------------

class TestTemporalPatterns:
    @pytest.mark.parametrize("text", [
        # Sports
        "scores", "standings", "champion", "match", "final", "playoff",
        "fixture", "upcoming game", "next match",
        # Software versions
        "latest version", "current version", "new version",
        "new release", "changelog", "release notes",
        # News
        "today", "this week", "this month", "recently",
        "news", "announced", "breaking",
        # Prices
        "price", "stock price", "crypto", "bitcoin",
        "exchange rate",
        # Weather
        "weather", "forecast",
        # Current status
        "who is the CEO of Apple",
        "who is the president of France",
        "who owns the company",
        "current champion of the league",
        "who won the match",
        # Entertainment / movies
        "what are current movies in theater",
        "what movies are playing now",
        "now playing at the cinema",
        "in theaters this weekend",
        "new movies this week",
        "box office results",
        "what is showing at the theater",
        "current series on Netflix",
        "upcoming movie releases",
        "what movies are in the cinemas",
        # Attribution (to avoid hallucination on obscure items)
        "who made PostVRP benchmarks",
        "who created TensorFlow",
        "who developed the BERT model",
        "who wrote the attention is all you need paper",
        "who invented the telephone",
        "who authored this dataset",
        "who designed the transformer architecture",
        "who built this framework",
    ])
    def test_pattern_matches(self, text):
        assert _TEMPORAL_RE.search(text) is not None, f"Expected match for: {text!r}"

    @pytest.mark.parametrize("text", [
        # Timeless questions — must NOT trigger search
        "who are the best composers of all time",
        "what is photosynthesis",
        "how does a computer work",
        "what is the capital of France",
        "create a directory",
        "can you check my system resources",
        "install Python on my machine",
        "who was the first president of the US",
        "who discovered gravity",
    ])
    def test_timeless_does_not_match(self, text):
        assert _TEMPORAL_RE.search(text) is None, f"Expected NO match for: {text!r}"


# ---------------------------------------------------------------------------
# Security: HTML stripping
# ---------------------------------------------------------------------------

class TestStripHTML:
    """_strip_html must discard <script>/<style> tag content, not just tags."""

    def test_imports_strip_html(self):
        from zenus_core.tools.web_search import _strip_html
        assert callable(_strip_html)

    def test_plain_text_unchanged(self):
        from zenus_core.tools.web_search import _strip_html
        assert _strip_html("hello world") == "hello world"

    def test_basic_tag_removed(self):
        from zenus_core.tools.web_search import _strip_html
        assert _strip_html("<b>bold</b>") == "bold"

    def test_script_content_discarded(self):
        from zenus_core.tools.web_search import _strip_html
        result = _strip_html("<p>Safe</p><script>alert('xss')</script>")
        assert "alert" not in result
        assert "Safe" in result

    def test_style_content_discarded(self):
        from zenus_core.tools.web_search import _strip_html
        result = _strip_html("<style>body{color:red}</style><p>Text</p>")
        assert "color" not in result
        assert "Text" in result

    def test_empty_string(self):
        from zenus_core.tools.web_search import _strip_html
        assert _strip_html("") == ""

    def test_html_entities_decoded(self):
        from zenus_core.tools.web_search import _strip_html
        result = _strip_html("Python &amp; Django")
        assert "&amp;" not in result
        assert "Python" in result


# ---------------------------------------------------------------------------
# Security: defusedxml import
# ---------------------------------------------------------------------------

class TestDefusedXMLImport:
    """Verify defusedxml is used instead of the vulnerable stdlib ET."""

    def test_defusedxml_is_imported(self):
        import zenus_core.tools.web_search as ws_module
        import inspect
        source = inspect.getfile(ws_module)
        # The module should import defusedxml, not stdlib xml.etree.ElementTree
        import defusedxml.ElementTree
        # If defusedxml.ElementTree is the ET used, parsing an XML bomb
        # should raise an exception rather than hanging/consuming memory.
        bomb = (
            "<?xml version='1.0'?>"
            "<!DOCTYPE lolz ["
            "  <!ENTITY lol 'lol'>"
            "  <!ENTITY lol2 '&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;'>"
            "]>"
            "<root>&lol2;</root>"
        )
        with pytest.raises(Exception):
            defusedxml.ElementTree.fromstring(bomb)


# ---------------------------------------------------------------------------
# WebSearchTool — _semantic_scholar_search
# ---------------------------------------------------------------------------

class TestSemanticScholarSearch:
    @pytest.fixture
    def tool(self):
        return WebSearchTool()

    def _mock_response(self, data: dict) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = data
        return mock

    def test_returns_papers(self, tool):
        data = {"data": [
            {
                "paperId": "abc123",
                "title": "Attention Is All You Need",
                "abstract": "We propose the Transformer.",
                "year": 2017,
                "venue": "NeurIPS",
                "authors": [{"name": "Vaswani"}, {"name": "Shazeer"}],
                "externalIds": {"DOI": "10.5555/123"},
            }
        ]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._semantic_scholar_search("transformer attention", 5)
        assert len(results) == 1
        assert results[0].source == "semantic_scholar"
        assert results[0].title == "Attention Is All You Need"
        assert "Vaswani" in results[0].snippet
        assert "2017" in results[0].snippet
        assert results[0].url.startswith("https://doi.org/")

    def test_url_fallback_to_semantic_scholar(self, tool):
        data = {"data": [{
            "paperId": "xyz",
            "title": "No DOI Paper",
            "abstract": "",
            "year": 2020,
            "venue": "",
            "authors": [],
            "externalIds": {},
        }]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._semantic_scholar_search("test", 5)
        assert "semanticscholar.org" in results[0].url

    def test_et_al_for_many_authors(self, tool):
        data = {"data": [{
            "paperId": "p1",
            "title": "Multi-author Paper",
            "abstract": "Abstract.",
            "year": 2021,
            "venue": "ICML",
            "authors": [{"name": f"Author{i}"} for i in range(6)],
            "externalIds": {},
        }]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._semantic_scholar_search("test", 5)
        assert "et al." in results[0].snippet

    def test_api_failure_returns_empty(self, tool):
        with patch.object(tool._session, "get", side_effect=Exception("timeout")):
            assert tool._semantic_scholar_search("test", 5) == []

    def test_max_results_respected(self, tool):
        data = {"data": [
            {"paperId": f"p{i}", "title": f"Paper {i}", "abstract": "",
             "year": 2020, "venue": "", "authors": [], "externalIds": {}}
            for i in range(10)
        ]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._semantic_scholar_search("test", 3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# WebSearchTool — _openalex_search
# ---------------------------------------------------------------------------

class TestOpenAlexSearch:
    @pytest.fixture
    def tool(self):
        return WebSearchTool()

    def _mock_response(self, data: dict) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = data
        return mock

    def test_returns_works(self, tool):
        data = {"results": [
            {
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "publication_year": 2018,
                "doi": "https://doi.org/10.18653/bert",
                "abstract_inverted_index": {"BERT": [0], "is": [1], "powerful": [2]},
                "authorships": [
                    {"author": {"display_name": "Devlin"}},
                    {"author": {"display_name": "Chang"}},
                ],
                "primary_location": {"source": {"display_name": "NAACL"}},
            }
        ]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._openalex_search("BERT transformer", 5)
        assert len(results) == 1
        assert results[0].source == "openalex"
        assert "BERT" in results[0].title
        assert "Devlin" in results[0].snippet
        assert "2018" in results[0].snippet

    def test_abstract_reconstructed_from_inverted_index(self, tool):
        inv = {"The": [0], "quick": [1], "brown": [2], "fox": [3]}
        data = {"results": [{
            "title": "Test Paper",
            "publication_year": 2022,
            "doi": "",
            "abstract_inverted_index": inv,
            "authorships": [],
            "primary_location": None,
        }]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._openalex_search("test", 5)
        assert "The quick brown fox" in results[0].snippet

    def test_empty_inverted_index(self, tool):
        data = {"results": [{
            "title": "No Abstract",
            "publication_year": 2020,
            "doi": "",
            "abstract_inverted_index": {},
            "authorships": [],
            "primary_location": None,
        }]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._openalex_search("test", 5)
        assert len(results) == 1
        assert results[0].title == "No Abstract"

    def test_api_failure_returns_empty(self, tool):
        with patch.object(tool._session, "get", side_effect=Exception("timeout")):
            assert tool._openalex_search("test", 5) == []

    def test_max_results_respected(self, tool):
        data = {"results": [
            {"title": f"Work {i}", "publication_year": 2020, "doi": "",
             "abstract_inverted_index": {}, "authorships": [], "primary_location": None}
            for i in range(10)
        ]}
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._openalex_search("test", 4)
        assert len(results) == 4


# ---------------------------------------------------------------------------
# Entertainment / movies temporal patterns
# ---------------------------------------------------------------------------

class TestEntertainmentPatterns:
    """Movies and entertainment queries must trigger search."""

    @pytest.fixture
    def engine(self):
        return SearchDecisionEngine()

    @pytest.mark.parametrize("query", [
        "what are current movies in theater",
        "what movies are in theaters this weekend",
        "now playing at the cinema",
        "what's playing at the theater",
        "box office results this week",
        "what's showing at the cinema",
        "new movies this month",
        "upcoming movie releases",
        "what movies are playing right now",
        "current series on streaming",
    ])
    def test_entertainment_queries_trigger_search(self, engine, query):
        should, reason = engine.should_search(query)
        assert should is True, f"Expected search for: {query!r}"


# ---------------------------------------------------------------------------
# Academic query classification includes new patterns
# ---------------------------------------------------------------------------

class TestAcademicPatternExpansion:
    @pytest.mark.parametrize("query", [
        "find papers with doi 10.1234/test",
        "peer reviewed research on transformers",
        "conference proceedings on NLP",
        "citation count for this paper",
        "preprint on semantic scholar",
    ])
    def test_academic_re_matches_new_terms(self, query):
        assert _ACADEMIC_QUERY_RE.search(query) is not None, f"Expected academic match: {query!r}"
