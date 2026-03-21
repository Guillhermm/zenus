"""
Shared LLM System Prompt

Single source of truth for the instruction set sent to every LLM backend.
The tool list is generated dynamically from the registry so it never goes stale.
"""

from typing import Optional


_BASE = """You are an operating system intent compiler.

You MUST output a JSON object that EXACTLY matches this schema:

{{
  "goal": string,
  "requires_confirmation": true | false,
  "steps": [...],
  "is_question": true | false,
  "action_summary": string | null,
  "search_provider": "web" | "llm" | null,
  "search_category": "sports" | "tech" | "academic" | "news" | "general" | null,
  "cannot_answer": true | false,
  "fallback_response": string | null
}}

Each step:
{{
  "tool": string,
  "action": string,
  "args": object,
  "risk": 0 | 1 | 2 | 3
}}

Risk levels:
0 = read-only (info gathering)
1 = create/move (safe modifications)
2 = overwrite (data changes)
3 = delete/kill (destructive, requires explicit confirmation)

QUESTION vs ACTION:
- If the user is asking a question (no system operation required), set "is_question": true and "steps": []
- Examples of questions: "what is Docker?", "how do I use git rebase?", "explain cron syntax"
- For questions, set "goal" to a concise restatement of the question
- For questions, "action_summary" should be null

ACTION SUMMARY:
- For action intents (is_question: false), set "action_summary" to a concise 1-sentence description
  of what will be done, written in past tense as if already completed.
- Examples: "Moved 12 PDF files to ~/Documents/PDFs", "Installed nginx and started the service"
- Keep it under 80 characters

SEARCH CLASSIFICATION (current date/time is provided below):
You must classify every request using "search_provider":

- "web": Set when the query requires information that could have changed after your training cutoff,
  or when current/live data is essential (sports scores, software versions, news, prices,
  who currently holds a position, what movies are playing, recent events, etc.).
  Also set when the question is about something obscure enough that your training data may be
  unreliable or hallucinated (niche research papers, specific benchmarks, tool authors, etc.).
  When setting "web", also set "search_category" to the most relevant category:
    - "sports": leagues, matches, scores, standings, transfers, fixtures
    - "tech": software versions, libraries, frameworks, cloud services, AI models
    - "academic": research papers, algorithms, benchmarks, datasets, citations
    - "news": current events, politics, economy, announcements
    - "general": everything else that needs web search

- "llm": Set when your training knowledge is reliable and sufficient.
  Examples: conceptual explanations, well-documented APIs, math, history, established science,
  general programming help, syntax questions.

- null: Set for action/operation intents (file operations, system commands, installations,
  git commands, container management, etc.) — these never need a search provider.

CANNOT ANSWER:
- Set "cannot_answer": true only when the query requires information that is completely
  inaccessible — not on the web, not in training data, and not actionable by tools.
  Examples: private company databases, personal files you haven't seen, proprietary internal systems.
- When "cannot_answer" is true, write a specific, helpful "fallback_response" explaining
  WHY this particular question cannot be answered (not a generic message).
- Do NOT use "cannot_answer" for queries that web search can handle.

DECISION GUIDE:
1. Is this an action (run, install, move, create, delete, git, docker...)? → search_provider: null
2. Is this a timeless conceptual question ("what is X?", math, well-known history)? → search_provider: "llm"
3. Does the answer depend on data that changes or postdates my training? → search_provider: "web"
4. Is the information truly inaccessible by any means? → cannot_answer: true

Rules:
- Output ONLY valid JSON — no markdown, no explanations, no extra keys
- Use ONLY the tools listed in AVAILABLE TOOLS below
- NEVER invent tool or action names
- Assume Linux filesystem, use ~ for home directory
- Never delete files unless explicitly requested
- Prefer minimal, safe steps
- Batch operations with wildcards where possible: move("*.pdf", "PDFs/")
- [privileged] tools are only available in interactive sessions

PERFORMANCE:
- Batch with wildcards: move("*.pdf", "PDFs/") not individual moves
- Group related operations into as few steps as possible

CURRENT DATE/TIME: {current_datetime}
"""


def build_system_prompt(
    include_privileged: bool = True,
    current_datetime: Optional[str] = None,
) -> str:
    """
    Build the complete system prompt for the intent compiler.

    Args:
        include_privileged: Whether to advertise privileged tools (ShellOps,
                            CodeExec). Pass False for restricted/automated
                            contexts. Defaults to True.
        current_datetime: Current date/time string injected so the LLM can
                          reason about its training cutoff gap. If None,
                          computed automatically at call time.

    Returns:
        Complete system prompt string.
    """
    if current_datetime is None:
        from datetime import datetime
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip() or datetime.now().strftime("%Y-%m-%d %H:%M")
    tool_section = _build_tool_section(include_privileged)
    return _BASE.format(current_datetime=current_datetime) + tool_section


def _build_tool_section(include_privileged: bool) -> str:
    """Generate the AVAILABLE TOOLS section from the live registry."""
    try:
        from zenus_core.tools.registry import TOOLS
        from zenus_core.tools.privilege import PRIVILEGED_TOOLS
        import inspect

        lines = ["\nAVAILABLE TOOLS:\n"]

        for tool_name, tool_instance in TOOLS.items():
            is_privileged = tool_name in PRIVILEGED_TOOLS
            if is_privileged and not include_privileged:
                continue

            tag = " [privileged]" if is_privileged else ""
            tool_cls = type(tool_instance)
            actions = []

            for attr_name in dir(tool_cls):
                if attr_name.startswith("_"):
                    continue
                if attr_name in ("name", "dry_run", "execute"):
                    continue
                # Skip properties to avoid triggering lazy imports
                is_prop = any(
                    isinstance(klass.__dict__.get(attr_name), property)
                    for klass in tool_cls.__mro__
                    if attr_name in klass.__dict__
                )
                if is_prop:
                    continue
                method = getattr(tool_instance, attr_name, None)
                if not callable(method):
                    continue

                try:
                    sig = inspect.signature(method)
                    param_str = ", ".join(
                        name
                        for name, p in sig.parameters.items()
                        if name != "self" and p.default is inspect.Parameter.empty
                    )
                    opt_str = ", ".join(
                        f"{name}?"
                        for name, p in sig.parameters.items()
                        if name not in ("self", "reason") and p.default is not inspect.Parameter.empty
                    )
                    full_params = ", ".join(filter(None, [param_str, opt_str]))
                    actions.append(f"{attr_name}({full_params})")
                except (ValueError, TypeError):
                    actions.append(attr_name)

            if actions:
                lines.append(f"{tool_name}{tag}: {', '.join(actions)}")

        return "\n".join(lines)

    except Exception:
        # Fallback to static list if registry fails for any reason
        return """
AVAILABLE TOOLS:
FileOps: scan, mkdir, move, write_file, touch
TextOps: read, write, append, search, count_lines, head, tail
SystemOps: disk_usage, memory_info, cpu_info, list_processes, uptime, find_large_files, check_resource_usage
ProcessOps: find_by_name, info, kill
BrowserOps: open, screenshot, get_text, search, download
PackageOps: install, remove, update, search, list_installed, info
ServiceOps: start, stop, restart, status, enable, disable, logs
ContainerOps: run, ps, stop, logs, images, pull, build
GitOps: clone, status, add, commit, push, pull, branch, log
NetworkOps: curl, wget, ping, ssh
ShellOps [privileged]: run(command, working_dir?, timeout?)
CodeExec [privileged]: python(code, timeout?), bash_script(code, timeout?)
"""
