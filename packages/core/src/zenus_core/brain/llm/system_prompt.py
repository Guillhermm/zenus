"""
Shared LLM System Prompt

Single source of truth for the instruction set sent to every LLM backend.
The tool list is generated dynamically from the registry so it never goes stale.
"""



_BASE = """You are an operating system intent compiler.

You MUST output a JSON object that EXACTLY matches this schema:

{
  "goal": string,
  "requires_confirmation": true | false,
  "steps": [...],
  "is_question": true | false,
  "action_summary": string | null
}

Each step:
{
  "tool": string,
  "action": string,
  "args": object,
  "risk": 0 | 1 | 2 | 3
}

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
"""


def build_system_prompt(include_privileged: bool = True) -> str:
    """
    Build the complete system prompt for the intent compiler.

    Args:
        include_privileged: Whether to advertise privileged tools (ShellOps,
                            CodeExec). Pass False for restricted/automated
                            contexts. Defaults to True.

    Returns:
        Complete system prompt string.
    """
    tool_section = _build_tool_section(include_privileged)
    return _BASE + tool_section


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
