"""
Unit tests for GitOps tool (subprocess and requests fully mocked)
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open

from zenus_core.tools.git_ops import GitOps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(stdout="", stderr="", returncode=0):
    """Build a fake subprocess.CompletedProcess"""
    return Mock(stdout=stdout, stderr=stderr, returncode=returncode)


# ---------------------------------------------------------------------------
# _run_git
# ---------------------------------------------------------------------------

class TestRunGit:
    """Tests for GitOps._run_git internal helper"""

    def setup_method(self):
        self.tool = GitOps()

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_returns_stdout_on_success(self, mock_run):
        """Success returns stdout string"""
        mock_run.return_value = _make_proc(stdout="on branch main\n")
        result = self.tool._run_git(["status"])
        assert "on branch main" in result

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_returns_error_on_nonzero(self, mock_run):
        """Non-zero returncode returns 'Error: <stderr>'"""
        mock_run.return_value = _make_proc(stderr="not a git repo", returncode=128)
        result = self.tool._run_git(["status"])
        assert result.startswith("Error:")
        assert "not a git repo" in result

    @patch("zenus_core.tools.git_ops.subprocess.run", side_effect=Exception("timeout"))
    def test_exception_returns_error(self, mock_run):
        """Any exception is caught and returned as 'Error: ...'"""
        result = self.tool._run_git(["status"])
        assert result.startswith("Error:")
        assert "timeout" in result

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_expands_tilde_in_cwd(self, mock_run):
        """~ in cwd is expanded before passing to subprocess"""
        mock_run.return_value = _make_proc(stdout="ok")
        self.tool._run_git(["status"], cwd="~/projects/repo")
        _, kwargs = mock_run.call_args
        assert not kwargs["cwd"].startswith("~")

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_git_is_first_arg(self, mock_run):
        """'git' is prepended to provided args"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool._run_git(["log", "-1"])
        args = mock_run.call_args[0][0]
        assert args[0] == "git"
        assert "log" in args


# ---------------------------------------------------------------------------
# clone / status / add / commit
# ---------------------------------------------------------------------------

class TestGitBasicOps:
    """Tests for clone, status, add, and commit"""

    def setup_method(self):
        self.tool = GitOps()

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_clone_passes_url(self, mock_run):
        """clone forwards URL to git clone"""
        mock_run.return_value = _make_proc()
        self.tool.clone("https://github.com/user/repo.git")
        args = mock_run.call_args[0][0]
        assert "clone" in args
        assert "https://github.com/user/repo.git" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_clone_with_directory(self, mock_run):
        """clone with a target directory includes it in args"""
        mock_run.return_value = _make_proc()
        self.tool.clone("https://github.com/user/repo.git", directory="/tmp/myrepo")
        args = mock_run.call_args[0][0]
        assert "/tmp/myrepo" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_status_calls_git_status(self, mock_run):
        """status calls git status with given path as cwd"""
        mock_run.return_value = _make_proc(stdout="nothing to commit")
        result = self.tool.status("/tmp/repo")
        args = mock_run.call_args[0][0]
        assert "status" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_add_single_file(self, mock_run):
        """add with a single filename calls git add <file>"""
        mock_run.return_value = _make_proc()
        self.tool.add("README.md")
        args = mock_run.call_args[0][0]
        assert "add" in args
        assert "README.md" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_add_list_of_files(self, mock_run):
        """add with a list calls git add with all files"""
        mock_run.return_value = _make_proc()
        self.tool.add(["a.py", "b.py"])
        args = mock_run.call_args[0][0]
        assert "a.py" in args
        assert "b.py" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_add_dot_stages_all(self, mock_run):
        """add('.') stages everything"""
        mock_run.return_value = _make_proc()
        self.tool.add(".")
        args = mock_run.call_args[0][0]
        assert "." in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_commit_includes_message(self, mock_run):
        """commit passes -m flag with message"""
        mock_run.return_value = _make_proc(stdout="[main abc1234] feat: add x")
        self.tool.commit("feat: add x")
        args = mock_run.call_args[0][0]
        assert "-m" in args
        assert "feat: add x" in args


# ---------------------------------------------------------------------------
# push / pull
# ---------------------------------------------------------------------------

class TestGitPushPull:
    """Tests for push and pull operations"""

    def setup_method(self):
        self.tool = GitOps()

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_push_default_remote(self, mock_run):
        """push defaults to origin remote"""
        mock_run.return_value = _make_proc()
        self.tool.push()
        args = mock_run.call_args[0][0]
        assert "push" in args
        assert "origin" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_push_with_branch(self, mock_run):
        """push with branch includes branch name"""
        mock_run.return_value = _make_proc()
        self.tool.push(branch="feature/x")
        args = mock_run.call_args[0][0]
        assert "feature/x" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_pull_default_remote(self, mock_run):
        """pull defaults to origin remote"""
        mock_run.return_value = _make_proc(stdout="Already up to date.")
        self.tool.pull()
        args = mock_run.call_args[0][0]
        assert "pull" in args
        assert "origin" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_pull_with_branch(self, mock_run):
        """pull with branch includes branch name"""
        mock_run.return_value = _make_proc()
        self.tool.pull(branch="main")
        args = mock_run.call_args[0][0]
        assert "main" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_push_error_propagated(self, mock_run):
        """push error from git is returned as 'Error: ...'"""
        mock_run.return_value = _make_proc(stderr="rejected", returncode=1)
        result = self.tool.push()
        assert "Error:" in result


# ---------------------------------------------------------------------------
# branch / checkout
# ---------------------------------------------------------------------------

class TestGitBranchCheckout:
    """Tests for branch and checkout operations"""

    def setup_method(self):
        self.tool = GitOps()

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_branch_list_no_name(self, mock_run):
        """branch() without a name lists branches"""
        mock_run.return_value = _make_proc(stdout="* main\n  develop\n")
        result = self.tool.branch()
        args = mock_run.call_args[0][0]
        assert "branch" in args
        # No name argument after 'branch'
        assert len([a for a in args if a not in ("git", "branch")]) == 0

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_branch_create(self, mock_run):
        """branch with name creates a new branch"""
        mock_run.return_value = _make_proc()
        result = self.tool.branch("feature/new")
        assert "feature/new" in result

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_branch_delete(self, mock_run):
        """branch with delete=True passes -d flag"""
        mock_run.return_value = _make_proc()
        self.tool.branch("old-branch", delete=True)
        args = mock_run.call_args[0][0]
        assert "-d" in args
        assert "old-branch" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_branch_create_error_returned(self, mock_run):
        """branch create failure is returned as-is"""
        mock_run.return_value = _make_proc(stderr="already exists", returncode=128)
        result = self.tool.branch("existing")
        assert "Error:" in result

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_checkout_existing(self, mock_run):
        """checkout without create switches to existing branch"""
        mock_run.return_value = _make_proc()
        result = self.tool.checkout("develop")
        args = mock_run.call_args[0][0]
        assert "checkout" in args
        assert "develop" in args
        assert "-b" not in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_checkout_create_adds_b_flag(self, mock_run):
        """checkout with create=True adds -b flag"""
        mock_run.return_value = _make_proc()
        self.tool.checkout("new-branch", create=True)
        args = mock_run.call_args[0][0]
        assert "-b" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_checkout_error_returned_as_is(self, mock_run):
        """checkout error returns 'Error: ...' string"""
        mock_run.return_value = _make_proc(stderr="not found", returncode=1)
        result = self.tool.checkout("ghost-branch")
        assert "Error:" in result


# ---------------------------------------------------------------------------
# log / diff / stash / remote
# ---------------------------------------------------------------------------

class TestGitHistoryOps:
    """Tests for log, diff, stash, and remote operations"""

    def setup_method(self):
        self.tool = GitOps()

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_log_default_limit_10(self, mock_run):
        """log defaults to last 10 commits"""
        mock_run.return_value = _make_proc(stdout="abc1234 commit msg\n")
        self.tool.log()
        args = mock_run.call_args[0][0]
        assert "-10" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_log_custom_limit(self, mock_run):
        """log with custom limit passes correct -N flag"""
        mock_run.return_value = _make_proc(stdout="")
        self.tool.log(limit=5)
        args = mock_run.call_args[0][0]
        assert "-5" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_log_uses_oneline(self, mock_run):
        """log always uses --oneline format"""
        mock_run.return_value = _make_proc()
        self.tool.log()
        args = mock_run.call_args[0][0]
        assert "--oneline" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_diff_no_file(self, mock_run):
        """diff without file calls git diff"""
        mock_run.return_value = _make_proc(stdout="diff output")
        result = self.tool.diff()
        args = mock_run.call_args[0][0]
        assert "diff" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_diff_with_file(self, mock_run):
        """diff with file includes file in args"""
        mock_run.return_value = _make_proc()
        self.tool.diff("README.md")
        args = mock_run.call_args[0][0]
        assert "README.md" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_stash_push(self, mock_run):
        """stash push saves current changes"""
        mock_run.return_value = _make_proc(stdout="Saved working directory")
        result = self.tool.stash("push")
        args = mock_run.call_args[0][0]
        assert "stash" in args
        assert "push" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_stash_pop(self, mock_run):
        """stash pop restores saved changes"""
        mock_run.return_value = _make_proc()
        self.tool.stash("pop")
        args = mock_run.call_args[0][0]
        assert "pop" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_remote_show_uses_v(self, mock_run):
        """remote show uses -v flag"""
        mock_run.return_value = _make_proc(stdout="origin  https://...\n")
        self.tool.remote("show")
        args = mock_run.call_args[0][0]
        assert "-v" in args

    @patch("zenus_core.tools.git_ops.subprocess.run")
    def test_remote_non_show_action_included(self, mock_run):
        """remote with non-show action includes the action in args"""
        mock_run.return_value = _make_proc()
        self.tool.remote("add")
        args = mock_run.call_args[0][0]
        assert "add" in args


# ---------------------------------------------------------------------------
# GitHub token resolution
# ---------------------------------------------------------------------------

class TestGitHubToken:
    """Tests for GitOps._github_token resolution"""

    def setup_method(self):
        self.tool = GitOps()

    def test_reads_github_token_env(self):
        """GITHUB_TOKEN env var is returned"""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123"}, clear=False):
            token = self.tool._github_token()
        assert token == "ghp_test123"

    def test_reads_gh_token_env(self):
        """GH_TOKEN env var is used when GITHUB_TOKEN is absent"""
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
        env["GH_TOKEN"] = "ghp_fallback"
        with patch.dict(os.environ, env, clear=True):
            token = self.tool._github_token()
        assert token == "ghp_fallback"

    def test_returns_none_when_no_token(self):
        """Returns None when no token is found"""
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            with patch("dotenv.find_dotenv", return_value=""):
                with patch("dotenv.load_dotenv"):
                    fake_env_path = MagicMock()
                    fake_env_path.exists.return_value = False
                    with patch("zenus_core.tools.git_ops.Path") as mock_path:
                        mock_path.home.return_value.__truediv__.return_value.__truediv__.return_value = fake_env_path
                        with patch("zenus_core.tools.git_ops.os.path.exists", return_value=False):
                            token = self.tool._github_token()
        assert token is None


# ---------------------------------------------------------------------------
# _github_request
# ---------------------------------------------------------------------------

class TestGitHubRequest:
    """Tests for GitOps._github_request"""

    def setup_method(self):
        self.tool = GitOps()

    def test_returns_error_when_no_token(self):
        """Returns error dict when no token is available"""
        with patch.object(self.tool, "_github_token", return_value=None):
            result = self.tool._github_request("GET", "/repos/owner/repo/issues")
        assert "error" in result

    @patch("zenus_core.tools.git_ops.requests.request")
    def test_get_returns_json(self, mock_req):
        """Successful GET returns parsed JSON"""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"number": 1, "title": "Test"}]
        mock_resp.raise_for_status = Mock()
        mock_req.return_value = mock_resp
        with patch.object(self.tool, "_github_token", return_value="tok"):
            result = self.tool._github_request("GET", "/repos/x/y/issues")
        assert isinstance(result, list)

    @patch("zenus_core.tools.git_ops.requests.request")
    def test_204_returns_success(self, mock_req):
        """HTTP 204 response returns {'success': True}"""
        import requests
        mock_resp = Mock()
        mock_resp.status_code = 204
        mock_resp.raise_for_status = Mock()
        mock_req.return_value = mock_resp
        with patch.object(self.tool, "_github_token", return_value="tok"):
            result = self.tool._github_request("DELETE", "/repos/x/y/issues/1")
        assert result == {"success": True}

    @patch("zenus_core.tools.git_ops.requests.request")
    def test_http_error_returns_error_dict(self, mock_req):
        """HTTPError is caught and returned as error dict"""
        import requests
        mock_resp = Mock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"message": "Not Found"}
        http_err = requests.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        mock_req.return_value = mock_resp
        with patch.object(self.tool, "_github_token", return_value="tok"):
            result = self.tool._github_request("GET", "/repos/x/y")
        assert "error" in result

    @patch("zenus_core.tools.git_ops.requests.request", side_effect=Exception("conn refused"))
    def test_generic_exception_returns_error_dict(self, mock_req):
        """Generic exception is caught and returned as error dict"""
        with patch.object(self.tool, "_github_token", return_value="tok"):
            result = self.tool._github_request("GET", "/repos/x/y")
        assert "error" in result


# ---------------------------------------------------------------------------
# create_issue / list_issues / close_issue
# ---------------------------------------------------------------------------

class TestGitHubIssues:
    """Tests for GitHub Issues API methods"""

    def setup_method(self):
        self.tool = GitOps()

    def test_create_issue_returns_url(self):
        """create_issue returns formatted URL on success"""
        with patch.object(
            self.tool,
            "_github_request",
            return_value={"number": 42, "html_url": "https://github.com/x/y/issues/42"},
        ):
            result = self.tool.create_issue("owner/repo", "Test issue")
        assert "#42" in result
        assert "https://github.com" in result

    def test_create_issue_propagates_error(self):
        """create_issue propagates API error message"""
        with patch.object(self.tool, "_github_request", return_value={"error": "no token"}):
            result = self.tool.create_issue("owner/repo", "Test")
        assert "Error" in result

    def test_list_issues_formats_output(self):
        """list_issues formats issues with numbers and titles"""
        issues = [
            {"number": 1, "title": "Bug fix", "labels": []},
            {"number": 2, "title": "Feature", "labels": [{"name": "enhancement"}]},
        ]
        with patch.object(self.tool, "_github_request", return_value=issues):
            result = self.tool.list_issues("owner/repo")
        assert "#1" in result
        assert "Bug fix" in result
        assert "#2" in result
        assert "enhancement" in result

    def test_list_issues_empty_returns_message(self):
        """list_issues with no results returns descriptive message"""
        with patch.object(self.tool, "_github_request", return_value=[]):
            result = self.tool.list_issues("owner/repo", state="closed")
        assert "No" in result and "closed" in result

    def test_list_issues_api_error(self):
        """list_issues with API error returns error string"""
        with patch.object(self.tool, "_github_request", return_value={"error": "forbidden"}):
            result = self.tool.list_issues("owner/repo")
        assert "Error" in result

    def test_list_issues_unexpected_response(self):
        """list_issues with unexpected non-list response returns message"""
        with patch.object(self.tool, "_github_request", return_value={"weird": "data"}):
            result = self.tool.list_issues("owner/repo")
        assert "Unexpected" in result

    def test_close_issue_success(self):
        """close_issue returns confirmation message"""
        with patch.object(self.tool, "_github_request", return_value={"state": "closed", "number": 5}):
            result = self.tool.close_issue("owner/repo", 5)
        assert "Closed" in result and "5" in result

    def test_close_issue_with_comment_posts_comment_first(self):
        """close_issue with comment calls API twice (comment then close)"""
        calls = []
        def fake_request(method, path, data=None, token=None):
            calls.append((method, path))
            return {"state": "closed", "number": 3}
        with patch.object(self.tool, "_github_request", side_effect=fake_request):
            self.tool.close_issue("owner/repo", 3, comment="Resolved in v2")
        assert len(calls) == 2
        assert "comments" in calls[0][1]

    def test_close_issue_error(self):
        """close_issue propagates API error"""
        with patch.object(self.tool, "_github_request", return_value={"error": "not found"}):
            result = self.tool.close_issue("owner/repo", 99)
        assert "Error" in result


# ---------------------------------------------------------------------------
# create_issues_from_roadmap
# ---------------------------------------------------------------------------

class TestCreateIssuesFromRoadmap:
    """Tests for GitOps.create_issues_from_roadmap"""

    def setup_method(self):
        self.tool = GitOps()

    def test_returns_error_when_roadmap_not_found(self):
        """Returns error when roadmap file does not exist"""
        result = self.tool.create_issues_from_roadmap(
            "owner/repo", roadmap_path="/tmp/nonexistent_roadmap_xyz.md"
        )
        assert "Error" in result

    def test_dry_run_shows_preview(self, tmp_path):
        """Dry run shows items that would be created"""
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text("## Phase 1: Start\n- [ ] Build feature A\n- [x] Done already\n")
        result = self.tool.create_issues_from_roadmap(
            "owner/repo", roadmap_path=str(roadmap), dry_run=True
        )
        assert "DRY RUN" in result
        assert "Build feature A" in result
        assert "Done already" not in result

    def test_phase_filter_excludes_other_phases(self, tmp_path):
        """phase_filter only includes matching phases"""
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text(
            "## Phase 1: Alpha\n- [ ] Task A\n\n## Phase 2: Beta\n- [ ] Task B\n"
        )
        result = self.tool.create_issues_from_roadmap(
            "owner/repo", roadmap_path=str(roadmap), phase_filter="Alpha", dry_run=True
        )
        assert "Task A" in result
        assert "Task B" not in result

    def test_no_unchecked_items_returns_message(self, tmp_path):
        """All checked items yields a 'No unchecked' message"""
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text("## Phase 1\n- [x] Already done\n")
        result = self.tool.create_issues_from_roadmap(
            "owner/repo", roadmap_path=str(roadmap), dry_run=True
        )
        assert "No unchecked" in result

    def test_live_run_creates_issues(self, tmp_path):
        """dry_run=False calls _github_request for each item"""
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text("## Phase 1\n- [ ] Task X\n- [ ] Task Y\n")
        call_count = {"n": 0}

        def fake_request(method, path, data=None, token=None):
            call_count["n"] += 1
            return {"number": call_count["n"], "title": data.get("title", "")}

        with patch.object(self.tool, "_github_request", side_effect=fake_request):
            result = self.tool.create_issues_from_roadmap(
                "owner/repo", roadmap_path=str(roadmap), dry_run=False
            )
        assert call_count["n"] == 2
        assert "Created 2/2" in result

    def test_live_run_handles_partial_errors(self, tmp_path):
        """Partial API failures are reported in output"""
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text("## Phase 1\n- [ ] Task OK\n- [ ] Task Fail\n")
        responses = [
            {"number": 1, "title": "Task OK"},
            {"error": "rate limited"},
        ]

        with patch.object(self.tool, "_github_request", side_effect=responses):
            result = self.tool.create_issues_from_roadmap(
                "owner/repo", roadmap_path=str(roadmap), dry_run=False
            )
        assert "Created 1/2" in result
        assert "Errors" in result
