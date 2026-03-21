"""
Git Operations

Advanced git operations beyond basic commands, plus GitHub Issues API.
"""

import subprocess
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests
from zenus_core.tools.base import Tool


GITHUB_API = "https://api.github.com"


class GitOps(Tool):
    """
    Advanced git operations plus GitHub Issues API.

    Capabilities:
    - Clone repositories
    - Commit with smart messages
    - Branch management
    - Push/pull operations
    - View history and diffs
    - Stash operations
    - GitHub Issues: create, list, close
    - Create issues from ROADMAP.md
    """

    def _github_token(self) -> Optional[str]:
        """Read GitHub token from environment only.

        Tokens must never be stored in config.yaml (risk of accidental VCS
        exposure). Use a .env file or the GITHUB_TOKEN / GH_TOKEN environment
        variables instead — or HashiCorp Vault via SecretsManager.
        """
        # Explicitly load .env files before reading env vars — do not rely on
        # the LLM factory having been imported first (tools can run without LLM)
        try:
            from dotenv import load_dotenv, find_dotenv
            dotenv_path = find_dotenv(usecwd=True)
            if dotenv_path:
                load_dotenv(dotenv_path, override=False)
            zenus_env = Path.home() / ".zenus" / ".env"
            if zenus_env.exists():
                load_dotenv(zenus_env, override=False)
        except ImportError:
            pass

        return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def _github_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a GitHub API request"""
        token = token or self._github_token()
        if not token:
            return {"error": "No GitHub token found. Set GITHUB_TOKEN or GH_TOKEN environment variable (or add it to ~/.zenus/.env)."}

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"{GITHUB_API}{path}"
        try:
            resp = requests.request(method, url, headers=headers, json=data, timeout=15)
            resp.raise_for_status()
            if resp.status_code == 204:
                return {"success": True}
            return resp.json()
        except requests.HTTPError as e:
            try:
                detail = e.response.json().get("message", str(e))
            except Exception:
                detail = str(e)
            return {"error": f"GitHub API error {e.response.status_code}: {detail}"}
        except Exception as e:
            return {"error": str(e)}

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
        milestone: Optional[int] = None,
    ) -> str:
        """
        Create a GitHub issue.

        Args:
            repo: Repository in 'owner/name' format
            title: Issue title
            body: Issue body (Markdown supported)
            labels: List of label names
            milestone: Milestone number
        """
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if milestone:
            payload["milestone"] = milestone

        result = self._github_request("POST", f"/repos/{repo}/issues", data=payload)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Created issue #{result['number']}: {result['html_url']}"

    def list_issues(
        self,
        repo: str,
        state: str = "open",
        labels: Optional[str] = None,
        limit: int = 30,
    ) -> str:
        """
        List GitHub issues.

        Args:
            repo: Repository in 'owner/name' format
            state: 'open', 'closed', or 'all'
            labels: Comma-separated label filter
            limit: Max issues to return (default 30)
        """
        params = f"?state={state}&per_page={min(limit, 100)}"
        if labels:
            params += f"&labels={labels}"
        result = self._github_request("GET", f"/repos/{repo}/issues{params}")
        if isinstance(result, dict) and "error" in result:
            return f"Error: {result['error']}"
        if not isinstance(result, list):
            return "Unexpected response from GitHub API"
        if not result:
            return f"No {state} issues found in {repo}"
        lines = [f"Issues in {repo} ({state}):"]
        for issue in result:
            label_str = ", ".join(lbl["name"] for lbl in issue.get("labels", []))
            label_part = f" [{label_str}]" if label_str else ""
            lines.append(f"  #{issue['number']}: {issue['title']}{label_part}")
        return "\n".join(lines)

    def close_issue(self, repo: str, issue_number: int, comment: str = "") -> str:
        """
        Close a GitHub issue.

        Args:
            repo: Repository in 'owner/name' format
            issue_number: Issue number to close
            comment: Optional comment to add before closing
        """
        if comment:
            self._github_request(
                "POST",
                f"/repos/{repo}/issues/{issue_number}/comments",
                data={"body": comment},
            )
        result = self._github_request(
            "PATCH",
            f"/repos/{repo}/issues/{issue_number}",
            data={"state": "closed"},
        )
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Closed issue #{issue_number} in {repo}"

    def create_issues_from_roadmap(
        self,
        repo: str,
        roadmap_path: str = "ROADMAP.md",
        phase_filter: Optional[str] = None,
        dry_run: bool = True,
    ) -> str:
        """
        Parse ROADMAP.md and create GitHub issues for unchecked items.

        Args:
            repo: Repository in 'owner/name' format
            roadmap_path: Path to ROADMAP.md (default: project root)
            phase_filter: Only create issues for items containing this string in their phase header
            dry_run: If True, show what would be created without creating (default True)
        """
        roadmap_path = os.path.expanduser(roadmap_path)
        if not os.path.exists(roadmap_path):
            return f"Error: Roadmap not found at {roadmap_path}"

        with open(roadmap_path) as f:
            content = f.read()

        issues_to_create = []
        current_phase = ""
        current_section = ""

        for line in content.splitlines():
            # Track phase headers (## Phase N: ...)
            if line.startswith("## "):
                current_phase = line.lstrip("# ").strip()
                current_section = ""
            elif line.startswith("### "):
                current_section = line.lstrip("# ").strip()
            # Unchecked todo items: - [ ] ...
            elif line.strip().startswith("- [ ] "):
                if phase_filter and phase_filter.lower() not in current_phase.lower():
                    continue
                task = line.strip()[6:].strip()  # Remove "- [ ] "
                body_parts = [f"**Phase**: {current_phase}"]
                if current_section:
                    body_parts.append(f"**Section**: {current_section}")
                body_parts.append(f"\nFrom [ROADMAP.md]({roadmap_path})")
                issues_to_create.append({
                    "title": task,
                    "body": "\n".join(body_parts),
                    "labels": ["roadmap"],
                })

        if not issues_to_create:
            return "No unchecked roadmap items found" + (f" matching '{phase_filter}'" if phase_filter else "")

        if dry_run:
            lines = [f"[DRY RUN] Would create {len(issues_to_create)} issues in {repo}:"]
            for i, issue in enumerate(issues_to_create[:20], 1):
                lines.append(f"  {i}. {issue['title']}")
            if len(issues_to_create) > 20:
                lines.append(f"  ... and {len(issues_to_create) - 20} more")
            lines.append("\nRun with dry_run=False to create issues.")
            return "\n".join(lines)

        created = []
        errors = []
        for issue in issues_to_create:
            result = self._github_request("POST", f"/repos/{repo}/issues", data=issue)
            if "error" in result:
                errors.append(f"  Failed '{issue['title']}': {result['error']}")
            else:
                created.append(f"  #{result['number']}: {issue['title']}")

        lines = [f"Created {len(created)}/{len(issues_to_create)} issues in {repo}:"]
        lines.extend(created[:10])
        if len(created) > 10:
            lines.append(f"  ... and {len(created) - 10} more")
        if errors:
            lines.append(f"\nErrors ({len(errors)}):")
            lines.extend(errors)
        return "\n".join(lines)

    def _run_git(self, args: List[str], cwd: Optional[str] = None) -> str:
        """Run git command"""
        cmd = ["git"] + args
        
        if cwd:
            cwd = os.path.expanduser(cwd)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=60
            )
            
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            
            return result.stdout
        except Exception as e:
            return f"Error: {str(e)}"
    
    def clone(self, url: str, directory: Optional[str] = None) -> str:
        """Clone a repository"""
        args = ["clone", url]
        if directory:
            args.append(directory)
        return self._run_git(args)
    
    def status(self, path: str = ".") -> str:
        """Check repository status"""
        return self._run_git(["status"], cwd=path)
    
    def add(self, files, path: str = ".") -> str:
        """
        Stage files

        Args:
            files: Files to stage ("." for all, a single path, or a list of paths)
            path: Repository path
        """
        if isinstance(files, list):
            args = ["add"] + files
        else:
            args = ["add", files]
        return self._run_git(args, cwd=path)
    
    def commit(self, message: str, path: str = ".") -> str:
        """Commit staged changes"""
        return self._run_git(["commit", "-m", message], cwd=path)
    
    def push(self, remote: str = "origin", branch: Optional[str] = None, path: str = ".") -> str:
        """Push to remote"""
        args = ["push", remote]
        if branch:
            args.append(branch)
        return self._run_git(args, cwd=path)
    
    def pull(self, remote: str = "origin", branch: Optional[str] = None, path: str = ".") -> str:
        """Pull from remote"""
        args = ["pull", remote]
        if branch:
            args.append(branch)
        return self._run_git(args, cwd=path)
    
    def branch(self, name: Optional[str] = None, delete: bool = False, path: str = ".") -> str:
        """
        Branch operations
        
        Args:
            name: Branch name (None to list branches)
            delete: Delete branch
            path: Repository path
        """
        if name is None:
            return self._run_git(["branch"], cwd=path)
        
        if delete:
            return self._run_git(["branch", "-d", name], cwd=path)

        result = self._run_git(["branch", name], cwd=path)
        if result.startswith("Error:"):
            return result
        return f"Branch '{name}' created"
    
    def checkout(self, branch: str, create: bool = False, path: str = ".") -> str:
        """
        Checkout branch
        
        Args:
            branch: Branch name
            create: Create new branch
            path: Repository path
        """
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(branch)
        result = self._run_git(args, cwd=path)
        if result.startswith("Error:"):
            return result
        # git checkout writes "Switched to branch '...'" to stderr (not stdout)
        prefix = "new branch" if create else "branch"
        return result or f"Switched to {prefix} '{branch}'"
    
    def log(self, limit: int = 10, path: str = ".") -> str:
        """View commit history"""
        return self._run_git(["log", f"-{limit}", "--oneline"], cwd=path)
    
    def diff(self, file: Optional[str] = None, path: str = ".") -> str:
        """Show changes"""
        args = ["diff"]
        if file:
            args.append(file)
        return self._run_git(args, cwd=path)
    
    def stash(self, action: str = "push", path: str = ".") -> str:
        """
        Stash operations
        
        Args:
            action: push, pop, list, apply
            path: Repository path
        """
        return self._run_git(["stash", action], cwd=path)
    
    def remote(self, action: str = "show", path: str = ".") -> str:
        """
        Remote operations
        
        Args:
            action: show, add, remove
            path: Repository path
        """
        args = ["remote"]
        if action != "show":
            args.append(action)
        args.append("-v")
        return self._run_git(args, cwd=path)
