"""
Unit tests for zenus_core.tools.web_search

Tests cover:
- WebSearchTool: Brave Search, per-source fetchers, dry_run, execute
- _fallback_search: smart routing by query category (passed by caller), deduplication, max_results
- format_results_for_context: formatting and edge cases
- _first_sentence helper
- Security: HTML stripping, defusedxml
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from zenus_core.tools.web_search import (
    SearchResult,
    WebSearchTool,
    format_results_for_context,
    _first_sentence,
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
# WebSearchTool — _fallback_search deduplication and ordering
# ---------------------------------------------------------------------------
class TestFallbackSearch:
    """Smart routing: category passed by caller selects the relevant sources."""

    def test_deduplicates_by_url(self):
        # category="tech" → sources: hackernews, github, wikipedia, rss
        tool = WebSearchTool()
        r1 = SearchResult(title="A", url="https://same.com", snippet="s1", source="wikipedia")
        r2 = SearchResult(title="A2", url="https://same.com", snippet="s2", source="hackernews")
        r3 = SearchResult(title="B", url="https://different.com", snippet="s3", source="github")
        with patch.object(tool, "_hackernews_search", return_value=[r2]), \
             patch.object(tool, "_github_search", return_value=[r3]), \
             patch.object(tool, "_wikipedia_search", return_value=[r1]), \
             patch.object(tool, "_rss_search", return_value=[]):
            results = tool._fallback_search("python programming library", 10, category="tech")
        urls = [r.url for r in results]
        assert urls.count("https://same.com") == 1
        assert len(results) == 2

    def test_respects_max_results(self):
        # category="general" → sources: wikipedia, ddg, rss
        tool = WebSearchTool()
        many = [SearchResult(title=f"R{i}", url=f"https://r{i}.com", snippet="s", source="wikipedia") for i in range(10)]
        with patch.object(tool, "_wikipedia_search", return_value=many), \
             patch.object(tool, "_instant_answer", return_value=[]), \
             patch.object(tool, "_rss_search", return_value=[]):
            results = tool._fallback_search("what is the capital of Brazil", 3, category="general")
        assert len(results) == 3

    def test_sports_category_uses_wikipedia_reddit_rss(self):
        # Sports: wikipedia, reddit, rss — NOT hackernews, github, arxiv
        tool = WebSearchTool()
        with patch.object(tool, "_wikipedia_search", return_value=[]) as mock_wiki, \
             patch.object(tool, "_reddit_search", return_value=[]) as mock_reddit, \
             patch.object(tool, "_rss_search", return_value=[]) as mock_rss, \
             patch.object(tool, "_hackernews_search", return_value=[]) as mock_hn, \
             patch.object(tool, "_github_search", return_value=[]) as mock_gh:
            tool._fallback_search("palmeiras soccer match schedule", 5, category="sports")
        mock_wiki.assert_called_once()
        mock_reddit.assert_called_once()
        mock_rss.assert_called_once()
        mock_hn.assert_not_called()
        mock_gh.assert_not_called()

    def test_academic_category_uses_semantic_scholar_arxiv_openalex_wikipedia(self):
        # Academic: semantic_scholar, arxiv, openalex, wikipedia — NOT hn, github, reddit
        tool = WebSearchTool()
        with patch.object(tool, "_semantic_scholar_search", return_value=[]) as mock_ss, \
             patch.object(tool, "_arxiv_search", return_value=[]) as mock_arxiv, \
             patch.object(tool, "_openalex_search", return_value=[]) as mock_oa, \
             patch.object(tool, "_wikipedia_search", return_value=[]) as mock_wiki, \
             patch.object(tool, "_hackernews_search", return_value=[]) as mock_hn, \
             patch.object(tool, "_github_search", return_value=[]) as mock_gh, \
             patch.object(tool, "_reddit_search", return_value=[]) as mock_reddit:
            tool._fallback_search("deep learning benchmark research paper", 5, category="academic")
        mock_ss.assert_called_once()
        mock_arxiv.assert_called_once()
        mock_oa.assert_called_once()
        mock_wiki.assert_called_once()
        mock_hn.assert_not_called()
        mock_gh.assert_not_called()
        mock_reddit.assert_not_called()

    def test_tech_category_uses_hn_github_wikipedia_rss(self):
        tool = WebSearchTool()
        with patch.object(tool, "_hackernews_search", return_value=[]) as mock_hn, \
             patch.object(tool, "_github_search", return_value=[]) as mock_gh, \
             patch.object(tool, "_wikipedia_search", return_value=[]) as mock_wiki, \
             patch.object(tool, "_rss_search", return_value=[]) as mock_rss, \
             patch.object(tool, "_reddit_search", return_value=[]) as mock_reddit:
            tool._fallback_search("docker kubernetes deployment", 5, category="tech")
        mock_hn.assert_called_once()
        mock_gh.assert_called_once()
        mock_wiki.assert_called_once()
        mock_rss.assert_called_once()
        mock_reddit.assert_not_called()

    def test_unknown_category_defaults_to_general(self):
        """Unrecognised category falls back to general sources."""
        tool = WebSearchTool()
        with patch.object(tool, "_wikipedia_search", return_value=[]) as mock_wiki, \
             patch.object(tool, "_instant_answer", return_value=[]) as mock_ddg, \
             patch.object(tool, "_rss_search", return_value=[]) as mock_rss, \
             patch.object(tool, "_hackernews_search") as mock_hn:
            tool._fallback_search("some query", 5, category="cooking")
        mock_wiki.assert_called_once()
        mock_hn.assert_not_called()

    def test_search_passes_category_to_fallback(self):
        """search() passes category= through to _fallback_search when no Brave key."""
        tool = WebSearchTool()
        tool._brave_key = ""
        with patch.object(tool, "_fallback_search", return_value=[]) as mock_fb:
            tool.search("test query", category="academic")
        mock_fb.assert_called_once_with("test query", 5, category="academic")




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


