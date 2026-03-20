"""
Unit tests for zenus_core.tools.web_search

Tests cover:
- SearchDecisionEngine: temporal patterns, knowledge gap, factual heuristic
- WebSearchTool: DDG Instant Answer parsing, HTML fallback, dry_run, execute
- format_results_for_context: formatting and edge cases
- _first_sentence helper
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta

import pytest

from zenus_core.tools.web_search import (
    SearchResult,
    SearchDecisionEngine,
    WebSearchTool,
    format_results_for_context,
    _first_sentence,
    _TEMPORAL_RE,
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
        return SearchDecisionEngine(training_cutoff="2020-01-01", gap_threshold_months=6)

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
        "how to install Docker latest",
        "who is the CEO of Tesla",
        "match results this month",
        "release date of macOS",
        "exchange rate USD to EUR",
        "playoff standings",
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
# SearchDecisionEngine — knowledge gap (Signal 2)
# ---------------------------------------------------------------------------

class TestSearchDecisionEngineKnowledgeGap:
    def test_large_gap_factual_query_triggers_search(self):
        engine = SearchDecisionEngine(training_cutoff="2020-01-01", gap_threshold_months=6)
        should, reason = engine.should_search("what is the population of France")
        assert should is True
        assert "out of date" in reason

    def test_small_gap_does_not_trigger_on_factual(self):
        # Set cutoff to yesterday — gap is 0 months
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        engine = SearchDecisionEngine(training_cutoff=yesterday, gap_threshold_months=6)
        should, _ = engine.should_search("what is the capital of France")
        assert should is False

    def test_large_gap_non_factual_does_not_trigger(self):
        engine = SearchDecisionEngine(training_cutoff="2020-01-01", gap_threshold_months=6)
        # Not a factual starter, not temporal
        should, _ = engine.should_search("create a directory named projects")
        assert should is False

    def test_gap_reason_includes_months(self):
        engine = SearchDecisionEngine(training_cutoff="2020-01-01", gap_threshold_months=6)
        should, reason = engine.should_search("who is the president of the US")
        assert should
        assert "months" in reason

    def test_invalid_cutoff_returns_zero_gap(self):
        engine = SearchDecisionEngine(training_cutoff="not-a-date", gap_threshold_months=6)
        gap = engine._knowledge_gap_months()
        assert gap == 0

    def test_gap_threshold_boundary(self):
        # Gap exactly at threshold — should trigger
        engine = SearchDecisionEngine(training_cutoff="2020-01-01", gap_threshold_months=6)
        gap = engine._knowledge_gap_months()
        assert gap >= 6  # 5+ years old training data

    def test_high_threshold_prevents_gap_trigger(self):
        engine = SearchDecisionEngine(training_cutoff="2020-01-01", gap_threshold_months=9999)
        # Gap is large but threshold is unreachably high — no trigger for non-temporal
        should, _ = engine.should_search("what is the capital of France")
        assert should is False


# ---------------------------------------------------------------------------
# SearchDecisionEngine — _looks_factual
# ---------------------------------------------------------------------------

class TestLooksFactual:
    @pytest.mark.parametrize("query,expected", [
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
        ("can you help me", True),
        ("will it rain tomorrow", True),
        ("are you ready", True),
        ("were they successful", True),
        # Non-factual starters
        ("create a directory", False),
        ("open my browser", False),
        ("move the file", False),
        ("hello there", False),
    ])
    def test_looks_factual(self, query, expected):
        result = SearchDecisionEngine._looks_factual(query)
        assert result == expected


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
    def test_dry_run_message(self):
        tool = WebSearchTool()
        result = tool.dry_run("python async")
        assert "python async" in result
        assert "DuckDuckGo" in result

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
        assert results[0].source == "duckduckgo:abstract"

    def test_answer_box_extracted(self, tool):
        data = {
            "AbstractText": "",
            "Answer": "42",
            "RelatedTopics": [],
        }
        with patch.object(tool._session, "get", return_value=self._mock_response(data)):
            results = tool._instant_answer("6 times 7", max_results=5)
        assert any(r.source == "duckduckgo:answer" for r in results)
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
        assert all(r.source == "duckduckgo:related" for r in results)

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
# WebSearchTool — _wikipedia_search
# ---------------------------------------------------------------------------

def _make_wiki_search_resp(titles: list) -> MagicMock:
    hits = [{"title": t, "snippet": f"Snippet for {t}"} for t in titles]
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"query": {"search": hits}}
    return mock


def _make_wiki_extract_resp(pages: dict) -> MagicMock:
    """pages: {title: extract_text}"""
    page_data = {str(i): {"title": t, "extract": e} for i, (t, e) in enumerate(pages.items())}
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"query": {"pages": page_data}}
    return mock


class TestWebSearchToolWikipedia:
    @pytest.fixture
    def tool(self):
        return WebSearchTool()

    def test_wikipedia_returns_results_with_extract(self, tool):
        search_resp = _make_wiki_search_resp(["Python (programming language)"])
        extract_resp = _make_wiki_extract_resp({"Python (programming language)": "Python is a high-level language."})
        with patch.object(tool._session, "get", side_effect=[search_resp, extract_resp]):
            results = tool._wikipedia_search("python language", max_results=5)
        assert len(results) == 1
        assert results[0].title == "Python (programming language)"
        assert "Python is a high-level language." in results[0].snippet
        assert results[0].source == "wikipedia"

    def test_wikipedia_url_uses_title(self, tool):
        search_resp = _make_wiki_search_resp(["Test Title"])
        extract_resp = _make_wiki_extract_resp({"Test Title": "Some content."})
        with patch.object(tool._session, "get", side_effect=[search_resp, extract_resp]):
            results = tool._wikipedia_search("test", max_results=5)
        assert "wikipedia.org/wiki/Test_Title" in results[0].url

    def test_wikipedia_empty_search_returns_empty(self, tool):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"query": {"search": []}}
        with patch.object(tool._session, "get", return_value=mock):
            results = tool._wikipedia_search("xyzzy12345", max_results=5)
        assert results == []

    def test_wikipedia_search_failure_returns_empty(self, tool):
        with patch.object(tool._session, "get", side_effect=Exception("timeout")):
            results = tool._wikipedia_search("query", max_results=5)
        assert results == []

    def test_wikipedia_extract_failure_falls_back_to_snippet(self, tool):
        search_resp = _make_wiki_search_resp(["Fallback Page"])
        with patch.object(tool._session, "get", side_effect=[search_resp, Exception("extract failed")]):
            results = tool._wikipedia_search("fallback", max_results=5)
        assert len(results) == 1
        assert results[0].source == "wikipedia:search"


# ---------------------------------------------------------------------------
# WebSearchTool — search() ordering (Wikipedia primary, DDG secondary)
# ---------------------------------------------------------------------------

class TestWebSearchFallback:
    def test_wikipedia_is_tried_first(self):
        tool = WebSearchTool()
        wiki_results = [SearchResult(title="W", url="u", snippet="s", source="wikipedia")]
        with patch.object(tool, "_wikipedia_search", return_value=wiki_results) as mock_wiki, \
             patch.object(tool, "_instant_answer", return_value=[]) as mock_ddg:
            results = tool.search("query")
        mock_wiki.assert_called_once()
        assert results == wiki_results

    def test_ddg_fills_remaining_slots(self):
        tool = WebSearchTool()
        wiki_results = [SearchResult(title="W", url="u", snippet="s", source="wikipedia")]
        ddg_results = [SearchResult(title="D", url="u", snippet="s", source="duckduckgo:abstract")]
        with patch.object(tool, "_wikipedia_search", return_value=wiki_results), \
             patch.object(tool, "_instant_answer", return_value=ddg_results) as mock_ddg:
            results = tool.search("query", max_results=5)
        mock_ddg.assert_called_once_with("query", 4)  # 5 - 1 wiki result = 4 remaining
        assert len(results) == 2

    def test_ddg_not_called_when_wikipedia_fills_quota(self):
        tool = WebSearchTool()
        wiki_results = [SearchResult(title=f"W{i}", url="u", snippet="s", source="wikipedia") for i in range(5)]
        with patch.object(tool, "_wikipedia_search", return_value=wiki_results), \
             patch.object(tool, "_instant_answer") as mock_ddg:
            results = tool.search("query", max_results=5)
        mock_ddg.assert_not_called()
        assert len(results) == 5

    def test_search_respects_max_results(self):
        tool = WebSearchTool()
        wiki_results = [SearchResult(title=f"W{i}", url="u", snippet="s", source="wikipedia") for i in range(10)]
        with patch.object(tool, "_wikipedia_search", return_value=wiki_results), \
             patch.object(tool, "_instant_answer", return_value=[]):
            results = tool.search("query", max_results=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# _TEMPORAL_RE — pattern completeness spot-check
# ---------------------------------------------------------------------------

class TestTemporalPatterns:
    @pytest.mark.parametrize("text", [
        "scores", "standings", "champion", "league",
        "match", "game", "final", "playoff",
        "latest version", "current version", "released",
        "changelog", "updated", "new feature",
        "today", "this week", "this month", "recently",
        "news", "announced", "breaking",
        "price", "stock", "crypto", "bitcoin",
        "exchange rate", "currency",
        "weather", "forecast", "temperature",
    ])
    def test_pattern_matches(self, text):
        assert _TEMPORAL_RE.search(text) is not None, f"Expected match for: {text!r}"
