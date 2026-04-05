"""
Plan Executor

Executes IntentIR plans by dispatching steps to registered tools.
Does NOT handle display or confirmation, that is the orchestrator's job.
"""

from typing import List
from zenus_core.tools.registry import TOOLS
from zenus_core.tools.privilege import PrivilegeTier, check_privilege
from zenus_core.safety.policy import check_step, SafetyError
from zenus_core.brain.llm.schemas import IntentIR
from zenus_core.execution.error_handler import get_error_handler
from zenus_core.debug import get_debug_flags


def execute_plan(
    intent: IntentIR,
    logger=None,
    parallel: bool = True,
    privilege_tier: PrivilegeTier = PrivilegeTier.STANDARD,
) -> List[str]:
    """
    Execute a validated IntentIR plan
    
    Responsibilities:
    - Safety checks (via policy)
    - Tool dispatch
    - Step by step execution (or parallel if enabled)
    
    Does NOT:
    - Display plan details (orchestrator's job)
    - Ask for confirmation (orchestrator's job)
    - Handle high level errors (orchestrator catches them)
    
    Args:
        intent: The validated IntentIR to execute
        logger: Optional audit logger for recording step results
        parallel: Enable parallel execution for independent steps
    
    Returns:
        List of step results (one per step)
    """
    from zenus_core.execution.error_recovery import get_error_recovery
    
    # Try parallel execution if enabled and multiple steps
    if parallel and len(intent.steps) > 1:
        try:
            from zenus_core.execution.parallel_executor import ParallelExecutor
            from zenus_core.brain.dependency_analyzer import DependencyAnalyzer
            
            # Analyze dependencies
            analyzer = DependencyAnalyzer()
            graph = analyzer.build_dependency_graph(intent.steps)
            
            # Execute in parallel if there are independent steps
            if analyzer.can_parallelize(graph):
                executor = ParallelExecutor()
                results = executor.execute_parallel(intent.steps, graph)
                
                # Log results
                if logger:
                    for step, result in zip(intent.steps, results):
                        logger.log_step_result(step.tool, step.action, str(result), True)
                
                return results
        except ImportError:
            # Parallel executor not available, fall back to sequential
            pass
        except Exception as e:
            # Parallel execution failed, fall back to sequential
            if get_debug_flags().execution:
                print(f"  [Parallel execution failed, using sequential: {e}]")
    
    # Sequential execution (fallback or by choice)
    results = []
    error_recovery = get_error_recovery()
    
    for step in intent.steps:
        # Safety check
        try:
            check_step(step)
        except SafetyError as e:
            error_msg = f"Safety check failed for {step.tool}.{step.action}: {e}"
            if logger:
                logger.log_step_result(step.tool, step.action, error_msg, False)
            raise
        
        # Privilege check (before tool lookup so the error is clear)
        try:
            check_privilege(step.tool, privilege_tier)
        except PermissionError as e:
            error_msg = str(e)
            if logger:
                logger.log_step_result(step.tool, step.action, error_msg, False)
            raise SafetyError(error_msg) from e

        # Get tool
        tool = TOOLS.get(step.tool)
        if not tool:
            error_msg = f"Tool not found: {step.tool}"
            if logger:
                logger.log_step_result(step.tool, step.action, error_msg, False)
            raise ValueError(error_msg)
        
        # Get action method
        action = getattr(tool, step.action, None)
        if not action:
            error_msg = f"Action not found: {step.tool}.{step.action}"
            if logger:
                logger.log_step_result(step.tool, step.action, error_msg, False)
            raise ValueError(error_msg)
        
        # PreToolUse hook — deny if hook exits non-zero
        try:
            from zenus_core.hooks.pipeline import get_hook_pipeline
            hook_result = get_hook_pipeline().execute_pre(step.tool, step.action)
            if not hook_result.allowed:
                deny_msg = (
                    f"[hook denied] {step.tool}.{step.action} — "
                    f"hook '{hook_result.hook_match}' exited {hook_result.exit_code}"
                    + (f": {hook_result.stderr}" if hook_result.stderr else "")
                )
                if logger:
                    logger.log_step_result(step.tool, step.action, deny_msg, False)
                results.append(deny_msg)
                continue
        except Exception:
            pass  # Never let a hook crash abort the whole pipeline

        # Execute with error recovery
        try:
            result = action(**step.args)
            if get_debug_flags().execution:
                print(f"  Done: {step.tool}.{step.action}: {result}")

            # PostToolUse hook (fire-and-forget in daemon thread)
            try:
                from zenus_core.hooks.pipeline import get_hook_pipeline
                get_hook_pipeline().execute_post(step.tool, step.action, str(result))
            except Exception:
                pass

            if logger:
                logger.log_step_result(step.tool, step.action, str(result), True)

            results.append(str(result))
                
        except Exception as e:
            # Attempt error recovery
            context = {
                "tool": step.tool,
                "action": step.action,
                "args": step.args
            }
            
            recovery_result = error_recovery.recover(
                e, context, action, **step.args
            )
            
            if recovery_result.success:
                # Recovery succeeded
                result_msg = f"Recovered: {recovery_result.message}"
                print(f"  {result_msg}")
                results.append(result_msg)
                
                if logger:
                    logger.log_step_result(step.tool, step.action, result_msg, True)
            else:
                # Recovery failed - provide enhanced error message
                error_handler = get_error_handler()
                enhanced_error = error_handler.handle(
                    e, step.tool, step.action, step.args, context
                )
                
                # Log with enhanced message
                if logger:
                    logger.log_step_result(step.tool, step.action, enhanced_error.user_friendly, False)
                
                # Print enhanced error (user-friendly)
                from rich.console import Console
                console = Console()
                console.print(enhanced_error.format())
                
                raise RuntimeError(enhanced_error.user_friendly) from e
    
    return results
