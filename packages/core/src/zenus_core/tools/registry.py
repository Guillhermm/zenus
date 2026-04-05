import inspect
from typing import Dict, Any

from zenus_core.tools.file_ops import FileOps
from zenus_core.tools.system_ops import SystemOps
from zenus_core.tools.process_ops import ProcessOps
from zenus_core.tools.text_ops import TextOps
from zenus_core.tools.browser_ops import BrowserOps
from zenus_core.tools.package_ops import PackageOps
from zenus_core.tools.service_ops import ServiceOps
from zenus_core.tools.container_ops import ContainerOps
from zenus_core.tools.git_ops import GitOps
from zenus_core.tools.network_ops import NetworkOps
try:
    from zenus_core.tools.vision_ops import VisionOps as _VisionOps
    _VISION_OPS_AVAILABLE = True
except Exception:
    _VisionOps = None
    _VISION_OPS_AVAILABLE = False
from zenus_core.tools.shell_ops import ShellOps
from zenus_core.tools.code_exec import CodeExec
from zenus_core.tools.web_search import WebSearchTool

# Agentic harness tools
from zenus_core.tools.task_ops import TaskOps
from zenus_core.tools.schedule_ops import ScheduleOps
from zenus_core.tools.worktree_ops import WorktreeOps
from zenus_core.tools.dev_ops import ToolSearch, AskUserQuestion, SleepTool
from zenus_core.tools.notebook_ops import NotebookOps

TOOLS = {
    # Core tools
    "FileOps":      FileOps(),
    "SystemOps":    SystemOps(),
    "ProcessOps":   ProcessOps(),
    "TextOps":      TextOps(),

    # Extended tools
    "BrowserOps":   BrowserOps(),
    "PackageOps":   PackageOps(),
    "ServiceOps":   ServiceOps(),
    "ContainerOps": ContainerOps(),
    "GitOps":       GitOps(),
    "NetworkOps":   NetworkOps(),
    **( {"VisionOps": _VisionOps()} if _VISION_OPS_AVAILABLE else {} ),

    # Privileged tools (require PrivilegeTier.PRIVILEGED)
    "ShellOps":     ShellOps(),
    "CodeExec":     CodeExec(),

    # Network/research tools
    "WebSearch":    WebSearchTool(),

    # Agentic harness tools
    "TaskOps":         TaskOps(),
    "ScheduleOps":     ScheduleOps(),
    "WorktreeOps":     WorktreeOps(),
    "ToolSearch":      ToolSearch(),
    "AskUserQuestion": AskUserQuestion(),
    "SleepTool":       SleepTool(),
    "NotebookOps":     NotebookOps(),
}


def describe() -> Dict[str, Any]:
    """
    Return a self-describing registry for LLM introspection.

    The result maps each tool name to its public actions with parameter
    signatures and docstrings.  This lets the LLM generate valid IntentIR
    steps without hallucinating tool or action names.

    Returns:
        Dict of {tool_name: {doc, privileged, actions: [{name, doc, params}]}}
    """
    from zenus_core.tools.privilege import PRIVILEGED_TOOLS

    registry: Dict[str, Any] = {}

    for tool_name, tool_instance in TOOLS.items():
        actions = []
        tool_cls = type(tool_instance)
        for attr_name in dir(tool_cls):
            if attr_name.startswith("_"):
                continue
            if attr_name in ("name", "dry_run", "execute"):
                continue
            # Skip properties — accessing them via getattr may trigger lazy imports
            is_property = any(
                isinstance(klass.__dict__.get(attr_name), property)
                for klass in tool_cls.__mro__
                if attr_name in klass.__dict__
            )
            if is_property:
                continue
            method = getattr(tool_instance, attr_name, None)
            if not callable(method):
                continue

            sig = inspect.signature(method)
            params = {
                name: (
                    str(param.annotation)
                    if param.annotation is not inspect.Parameter.empty
                    else "any"
                )
                for name, param in sig.parameters.items()
                if name != "self"
            }
            actions.append(
                {
                    "name": attr_name,
                    "doc": (inspect.getdoc(method) or "").split("\n")[0],
                    "params": params,
                }
            )

        registry[tool_name] = {
            "doc": (inspect.getdoc(tool_instance) or "").split("\n")[0],
            "privileged": tool_name in PRIVILEGED_TOOLS,
            "actions": actions,
        }

    return registry


def describe_compact() -> str:
    """
    Return a compact text summary of the registry for use in LLM system prompts.

    Format per tool:
        ToolName [privileged?]: brief doc
          - action(param: type, ...) — brief doc
    """
    lines: list[str] = []
    for tool_name, info in describe().items():
        tag = " [privileged]" if info["privileged"] else ""
        lines.append(f"{tool_name}{tag}: {info['doc']}")
        for action in info["actions"]:
            param_str = ", ".join(
                f"{p}: {t}" for p, t in action["params"].items()
            )
            lines.append(f"  - {action['name']}({param_str}) — {action['doc']}")
    return "\n".join(lines)
