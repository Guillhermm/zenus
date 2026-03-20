"""
Command Orchestrator

High-level orchestration of:
- Intent translation
- Memory management
- Plan execution
- Audit logging
"""

import asyncio
from typing import Optional, Dict
from zenus_core.brain.llm.factory import get_llm
from zenus_core.brain.planner import execute_plan
from zenus_core.brain.adaptive_planner import AdaptivePlanner
from zenus_core.brain.sandboxed_planner import SandboxedAdaptivePlanner
from zenus_core.brain.task_analyzer import TaskAnalyzer
from zenus_core.brain.failure_analyzer import FailureAnalyzer
from zenus_core.brain.dependency_analyzer import DependencyAnalyzer
from zenus_core.brain.suggestion_engine import get_suggestion_engine
from zenus_core.brain.model_router import get_router
from zenus_core.brain.llm.schemas import IntentIR
from zenus_core.brain.tree_of_thoughts import get_tree_of_thoughts
from zenus_core.brain.prompt_evolution import get_prompt_evolution
from zenus_core.brain.goal_inference import get_goal_inference
from zenus_core.brain.multi_agent import get_multi_agent_system
from zenus_core.brain.self_reflection import get_self_reflection
from zenus_core.monitoring import get_proactive_monitor

# Optional visualization (requires matplotlib)
try:
    from zenus_core.visualization import get_visualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    get_visualizer = None
    VISUALIZATION_AVAILABLE = False
from zenus_core.memory.action_tracker import get_action_tracker
from zenus_core.execution.parallel_executor import get_parallel_executor
from zenus_core.execution.intent_cache import get_intent_cache
from zenus_core.feedback import get_feedback_collector
from zenus_core.observability import get_metrics_collector
from zenus_core.output import get_formatter
from zenus_core.audit.logger import get_logger
from zenus_core.memory.session_memory import SessionMemory
from zenus_core.memory.world_model import WorldModel
from zenus_core.memory.intent_history import IntentHistory
from zenus_core.context.context_manager import get_context_manager
from zenus_core.output.progress import ProgressIndicator
from zenus_core.shell.response_generator import ResponseGenerator
from zenus_core.shell.explain import ExplainMode
from zenus_core.output.console import (
    print_success, print_error, print_goal,
    print_step, console
)
from zenus_core.tools.privilege import PrivilegeTier
from zenus_core.brain.knowledge_graph import get_knowledge_graph
from zenus_core.output.execution_summary import build_execution_summary
from zenus_core.tools.web_search import WebSearchTool, SearchDecisionEngine, format_results_for_context


class IntentTranslationError(Exception):
    """Raised when LLM fails to translate user intent"""
    pass


class OrchestratorError(Exception):
    """Raised for orchestration failures"""
    pass


class Orchestrator:
    """
    Orchestrates the full Zenus pipeline
    
    Responsibilities:
    1. Translate natural language → Intent IR
    2. Build context from memory
    3. Execute plan (with retry if adaptive)
    4. Update memory with results
    5. Log everything for audit
    """
    
    def __init__(
        self, 
        adaptive: bool = True, 
        use_memory: bool = True,
        use_sandbox: bool = True,
        show_progress: bool = True,
        enable_parallel: bool = True,
        enable_tree_of_thoughts: bool = True,
        enable_prompt_evolution: bool = True,
        enable_goal_inference: bool = True,
        enable_multi_agent: bool = False,  # Experimental feature
        enable_proactive_monitoring: bool = False,  # Experimental feature
        enable_self_reflection: bool = True,
        enable_visualization: bool = True,
        privilege_tier: PrivilegeTier = PrivilegeTier.STANDARD,
    ):
        self.llm = get_llm()
        self.logger = get_logger()
        self.adaptive = adaptive
        self.use_memory = use_memory
        self.use_sandbox = use_sandbox
        self.show_progress = show_progress
        self.privilege_tier = privilege_tier
        
        if adaptive:
            if use_sandbox:
                # Use sandboxed adaptive planner
                self.adaptive_planner = SandboxedAdaptivePlanner(self.logger)
            else:
                # Use basic adaptive planner
                self.adaptive_planner = AdaptivePlanner(self.logger)
        
        if use_memory:
            self.session_memory = SessionMemory()
            self.world_model = WorldModel()
            self.intent_history = IntentHistory()
        
        self.progress = ProgressIndicator() if show_progress else None
        self.feedback = ResponseGenerator(self.llm)
        self.failure_analyzer = FailureAnalyzer()
        self.action_tracker = get_action_tracker()
        self.enable_parallel = enable_parallel
        self.dependency_analyzer = DependencyAnalyzer() if enable_parallel else None
        self.parallel_executor = get_parallel_executor() if enable_parallel else None
        self.suggestion_engine = get_suggestion_engine()
        
        # Model router for intelligent LLM selection
        self.router = get_router()
        
        # Intent cache for memoization (2-3x speedup)
        self.intent_cache = get_intent_cache()
        
        # Feedback collector for learning
        self.feedback_collector = get_feedback_collector()
        
        # Metrics collector for observability
        self.metrics = get_metrics_collector()
        
        # Output formatter for rich display
        self.formatter = get_formatter()
        
        # Semantic search for command history (lazy import)
        self.semantic_search = None
        try:
            from zenus_core.memory.semantic_search import SemanticSearch
            self.semantic_search = SemanticSearch()
        except ImportError:
            # sentence-transformers not installed, semantic search disabled
            pass
        except Exception as e:
            # Other error, log it
            self.logger.log_error(f"Semantic search unavailable: {e}")
        
        self.explain_mode = ExplainMode(self.semantic_search)
        
        # Task analyzer for auto-detecting iterative vs one-shot
        self.task_analyzer = TaskAnalyzer(self.llm)
        
        # Revolutionary features (can be toggled)
        self.enable_tree_of_thoughts = enable_tree_of_thoughts
        self.enable_prompt_evolution = enable_prompt_evolution
        self.enable_goal_inference = enable_goal_inference
        self.enable_multi_agent = enable_multi_agent
        self.enable_proactive_monitoring = enable_proactive_monitoring
        self.enable_self_reflection = enable_self_reflection
        self.enable_visualization = enable_visualization
        
        # 🌳 Tree of Thoughts - Explore multiple solution paths
        self.tree_of_thoughts = get_tree_of_thoughts(self.llm, self.logger) if enable_tree_of_thoughts else None
        
        # 📈 Prompt Evolution - Self-improving prompts
        self.prompt_evolution = get_prompt_evolution() if enable_prompt_evolution else None
        
        # 🔮 Goal Inference - Understand high-level intent
        self.goal_inference = get_goal_inference(self.llm, self.logger) if enable_goal_inference else None
        
        # 🤖 Multi-Agent System - Collaborative problem solving
        self.multi_agent = get_multi_agent_system(self.llm, self.logger, self) if enable_multi_agent else None
        
        # 🔍 Proactive Monitor - Prevent problems before they occur
        self.proactive_monitor = get_proactive_monitor(self.logger, self) if enable_proactive_monitoring else None
        if self.proactive_monitor and enable_proactive_monitoring:
            # Start monitoring session
            self.proactive_monitor.start_monitoring()
        
        # 🤔 Self-Reflection - Critique plans before execution
        self.self_reflection = get_self_reflection(self.llm, self.logger) if enable_self_reflection else None
        
        # 📊 Visualizer - Auto-generate charts and tables
        if enable_visualization and VISUALIZATION_AVAILABLE:
            self.visualizer = get_visualizer()
        else:
            self.visualizer = None
            if enable_visualization and not VISUALIZATION_AVAILABLE:
                self.logger.log_error("Visualization requested but matplotlib not installed. Install with: poetry add matplotlib numpy")

        # Web search — transparent context enrichment (no API key required)
        self.web_search = WebSearchTool()
        self.search_engine = SearchDecisionEngine()
    
    def execute_command(
        self,
        user_input: str,
        dry_run: bool = False,
        explain: bool = False,
        force_oneshot: bool = False,
        force_provider: Optional[str] = None,
    ) -> str:
        """
        Execute a natural language command

        Automatically detects if task needs iterative execution.
        Pass force_provider to bypass complexity-based routing and use a
        specific LLM provider for this single command without changing defaults.
        Inline directives (@deepseek:, --provider X, use claude:, etc.) are
        parsed automatically from user_input before routing.


        Args:
            user_input: Natural language command
            dry_run: If True, show plan without executing
            explain: If True, show detailed explanation before executing
            force_oneshot: If True, skip iterative detection and use one-shot
        
        Returns:
            Human-readable result
        """
        import time
        start_time = time.time()

        try:
            # Parse inline provider/model override directives from user input
            # e.g. "@deepseek: do X", "--provider openai do X", "use claude: do X"
            from zenus_core.brain.provider_override import parse_provider_override, describe_override
            _clean, _detected_provider, _detected_model = parse_provider_override(user_input)
            if _detected_provider or _detected_model:
                user_input = _clean
                if not force_provider and _detected_provider:
                    force_provider = _detected_provider
                label = describe_override(force_provider, _detected_model)
                console.print(f"[dim cyan]↳ Using {label} for this command[/dim cyan]")

            # Step 0a: Web search — must run before complexity routing.
            # A query that triggers `should_search` is inherently a lookup
            # (sports schedules, news, prices, versions, etc.), not a multi-step
            # execution task.  Force oneshot regardless of whether DDG returned
            # results so the LLM answers from context (or training knowledge when
            # no results) instead of spinning in the iterative loop.
            _pre_search_context = ""
            _search_reason = ""
            if not force_oneshot:
                _should_search, _search_reason = self.search_engine.should_search(user_input)
                if _should_search:
                    _search_results = self.web_search.search(user_input)
                    _pre_search_context = format_results_for_context(_search_results)
                    if self.show_progress:
                        if _pre_search_context:
                            console.print(f"[dim cyan]↳ Web search: {_search_reason}[/dim cyan]")
                        else:
                            console.print(f"[dim yellow]↳ Web search attempted — no results (will answer from training data)[/dim yellow]")
                    # Always force oneshot for search-triggered queries.
                    # Iterative mode produces empty observations for lookups.
                    force_oneshot = True

            # Step 0: Analyze task complexity (auto-detect iterative need)
            if not force_oneshot:
                task_complexity = self.task_analyzer.analyze(user_input)

                if task_complexity.needs_iteration:
                    # Automatically use iterative mode for complex tasks
                    console.print(f"[dim]Detected complex task (confidence: {task_complexity.confidence:.0%})[/dim]")
                    console.print(f"[dim]Using iterative execution ({task_complexity.reasoning})[/dim]\n")
                    return self.execute_iterative(
                        user_input,
                        max_iterations=task_complexity.estimated_steps * 2,  # Dynamic max
                        dry_run=dry_run,
                        force_provider=force_provider,
                    )
            
            # Step 1: Build context from memory
            context = ""
            if self.use_memory:
                context = self._build_context(user_input)

            # Step 1.4: Inject pre-fetched web search results (done in Step 0a to
            # inform routing; reuse here rather than searching a second time).
            if _pre_search_context:
                context = (
                    f"{context}\n\n[Web Search Results - {_search_reason}]\n{_pre_search_context}"
                    if context
                    else f"[Web Search Results - {_search_reason}]\n{_pre_search_context}"
                )

            # Step 1.5: Goal Inference - Understand high-level intent
            if self.enable_goal_inference:
                goal_suggestion = self.goal_inference.infer_goal(user_input, context)
                
                # Show goal inference result
                if goal_suggestion.implicit_steps and not dry_run:
                    console.print(f"\n[cyan bold]🔮 Goal Inference:[/cyan bold] Detected {goal_suggestion.goal_type.value} workflow")
                    console.print(f"[dim]{goal_suggestion.reasoning}[/dim]\n")
                    
                    # Show complete workflow suggestion
                    if len(goal_suggestion.implicit_steps) > 0:
                        console.print("[yellow]💡 Suggested workflow includes:[/yellow]")
                        for step in goal_suggestion.complete_workflow[:5]:  # Show first 5
                            console.print(f"  • {step}")
                        if len(goal_suggestion.complete_workflow) > 5:
                            console.print(f"  ... and {len(goal_suggestion.complete_workflow) - 5} more steps")
                        console.print()
                        
                        # Ask if user wants to use suggested workflow
                        import os
                        if not os.environ.get('ZENUS_AUTO_ACCEPT_SUGGESTIONS'):
                            console.print("[cyan]Use suggested workflow? (y/n, default=y):[/cyan] ", end="")
                            try:
                                response = input().strip().lower()
                                if response and response != 'y' and response != 'yes':
                                    console.print("[dim]Using original command only[/dim]\n")
                                else:
                                    # Enhance user input with suggested steps
                                    user_input = f"{user_input} [SUGGESTED WORKFLOW: {', '.join(goal_suggestion.complete_workflow)}]"
                                    console.print("[green]✓[/green] Using enhanced workflow\n")
                            except Exception:
                                console.print("[dim]Auto-accepting suggested workflow[/dim]\n")
            
            # Step 1.6: Route to appropriate model based on complexity
            selected_model, complexity = self.router.route(user_input, iterative=False, force_model=force_provider)
            
            # Show routing decision (if not simple)
            if complexity.score > 0.5 and self.show_progress:
                console.print(f"[dim]Task complexity: {complexity.score:.2f} → Using {selected_model}[/dim]")
            
            # Step 1.7: Tree of Thoughts - Explore multiple solution paths
            use_tree_of_thoughts = self.enable_tree_of_thoughts and complexity.score > 0.6
            
            if use_tree_of_thoughts:
                console.print("[cyan]🌳 Tree of Thoughts:[/cyan] Exploring multiple solution paths...\n")
                
                tree = self.tree_of_thoughts.explore(user_input, context, num_paths=3)
                
                # Show explored paths
                console.print(f"[bold]Explored {len(tree.paths)} alternative approaches:[/bold]\n")
                for path in tree.paths:
                    quality_color = {
                        "excellent": "green",
                        "good": "cyan",
                        "acceptable": "yellow",
                        "risky": "red"
                    }.get(path.quality.value, "white")
                    
                    console.print(f"[{quality_color}]Path {path.path_id}:[/{quality_color}] {path.description}")
                    console.print(f"  Confidence: {path.confidence:.0%} | Risk: {path.risk_level} | Time: {path.estimated_time}")
                    console.print(f"  ✓ Pros: {', '.join(path.pros[:2])}")
                    if path.cons:
                        console.print(f"  ✗ Cons: {', '.join(path.cons[:2])}")
                    console.print()
                
                # Show selected path
                best_path = tree.get_best_path()
                console.print(f"[green bold]✓ Selected Path {best_path.path_id}:[/green bold] {best_path.description}")
                console.print(f"[dim]{tree.selection_reasoning}[/dim]\n")
                
                # Use selected path's intent
                intent = best_path.intent
                
                # Skip normal intent translation since we have it from tree
                # Cache the result
                self.intent_cache.set(user_input, context, intent)
            else:
                # Normal execution path
                # Step 2: Translate intent with context using selected model
                # Check cache first for instant response
                if context:
                    enhanced_input = f"{user_input}\n{context}"
                else:
                    enhanced_input = user_input
                
                intent = self.intent_cache.get(user_input, context)
                
                if intent:
                    # Cache hit! Instant response, zero tokens
                    if self.show_progress:
                        console.print("[dim green]✓ Cache hit (instant, $0.00)[/dim green]")
                    
                    # Update router stats (cache hit counts as using selected model but zero tokens)
                    self.router.track_tokens(selected_model, 0)
                else:
                    # Cache miss, call LLM
                    # IMPORTANT: Always use streaming to avoid Anthropic timeouts
                    try:
                        # Use the routed provider for this request
                        self.llm = get_llm(force_provider=selected_model)

                        # Show thinking indicator
                        if self.progress:
                            with self.progress.thinking("Understanding your request"):
                                intent = self.llm.translate_intent(enhanced_input, stream=True)
                        else:
                            intent = self.llm.translate_intent(enhanced_input, stream=True)

                        # Cache the result
                        self.intent_cache.set(user_input, context, intent)

                    except Exception as e:
                        error_msg = f"Failed to understand command: {str(e)}"
                        self.logger.log_error(error_msg, {"user_input": user_input})
                        raise IntentTranslationError(error_msg) from e
            
            # Step 2.4: Q&A short-circuit — no execution needed
            if intent.is_question:
                if self.show_progress:
                    console.print()
                context_for_answer = ""
                if self.use_memory:
                    context_for_answer = self._build_context(user_input)
                answer = self.llm.ask(user_input, context_for_answer)
                console.print(answer)
                return answer

            # Step 2.5: Analyze for potential failures (learning from past mistakes)
            pre_analysis = self.failure_analyzer.analyze_before_execution(user_input, intent)
            
            if pre_analysis["has_warnings"] and not dry_run:
                console.print("\n[yellow]📚 Learning from past experience:[/yellow]")
                
                # Show warnings
                for warning in pre_analysis["warnings"]:
                    console.print(f"  {warning}")
                
                # Show suggestions
                if pre_analysis["suggestions"]:
                    console.print("\n[cyan]💡 Suggestions based on past failures:[/cyan]")
                    for suggestion in pre_analysis["suggestions"]:
                        console.print(f"  • {suggestion}")
                
                # Show success probability
                prob = pre_analysis["success_probability"]
                if prob < 0.7:
                    console.print(f"\n  [yellow]Success probability: {prob:.0%}[/yellow]")
                    
                    if not explain:  # If not already in explain mode, ask for confirmation
                        response = console.input("\n[bold]Proceed anyway?[/bold] (y/n): ")
                        if response.lower() not in ('y', 'yes'):
                            return "Execution cancelled due to high failure risk"
            
            # Step 2.6: Self-Reflection - Critique plan before execution
            if self.enable_self_reflection and self.self_reflection and not dry_run:
                reflection = self.self_reflection.reflect_on_plan(user_input, intent, {"context": context})
                
                # Check if reflection found critical issues
                should_proceed, reason = self.self_reflection.should_proceed(reflection)
                
                # Show reflection to user if confidence is low or has critical issues
                if not should_proceed or reflection.overall_confidence_score < 0.7:
                    reflection_output = self.self_reflection.format_reflection_for_user(reflection)
                    console.print(reflection_output)
                    
                    # If critical issues, don't proceed
                    if not should_proceed:
                        console.print(f"\n[red bold]⚠️  {reason}[/red bold]")
                        
                        # Ask user if they want to proceed anyway
                        if reflection.should_ask_user and reflection.questions_for_user:
                            console.print("\n[cyan bold]❓ Please answer these questions:[/cyan bold]")
                            for q in reflection.questions_for_user:
                                answer = console.input(f"  {q}: ")
                                console.print(f"    → {answer}")
                        
                        response = console.input("\n[bold]Proceed anyway?[/bold] (y/n): ")
                        if response.lower() not in ('y', 'yes'):
                            return "Execution cancelled after self-reflection"
            
            # Step 2.7: Show proactive suggestions
            ctx_mgr = get_context_manager()
            suggestions = self.suggestion_engine.analyze(
                user_input, 
                intent, 
                ctx_mgr.get_full_context()
            )
            
            if suggestions and not dry_run:
                # Filter to only high-confidence suggestions
                shown_suggestions = [s for s in suggestions if self.suggestion_engine.should_show(s)]
                
                if shown_suggestions:
                    console.print("\n[cyan]💡 Suggestions:[/cyan]")
                    for suggestion in shown_suggestions:
                        console.print(f"  {self.suggestion_engine.format_suggestion(suggestion)}")
                    console.print()  # Blank line for spacing
            
            # Auto-explain high-risk operations
            if not explain:
                max_risk = max([step.risk for step in intent.steps])
                if max_risk >= 3 and not dry_run:
                    console.print("\n[yellow]⚠️  High-risk operation detected[/yellow]")
                    from zenus_core.shell.explain import get_explainer
                    explainer = get_explainer()
                    explainer.explain_intent(user_input, intent)
                    
                    if not explainer.confirm("This operation is destructive. Proceed?"):
                        return "Execution cancelled by user (high-risk operation)"
            
            # Step 3: Show explanation if requested
            if explain:
                from zenus_core.shell.explain import get_explainer
                explainer = get_explainer()
                
                # Show detailed explanation
                explainer.explain_intent(user_input, intent)
                
                # Show environmental context
                ctx_mgr = get_context_manager()
                explainer.explain_context(ctx_mgr.get_full_context())
                
                # Ask for confirmation
                if not explainer.confirm():
                    return "Execution cancelled by user"
            
            # Step 4: Log intent
            self.logger.log_intent(user_input, intent)
            
            # Step 5: Store context in memory
            if self.use_memory:
                self.session_memory.add_intent(intent)
            
            # Step 6: Execute plan
            if dry_run:
                return self._format_dry_run(intent)
            
            # Show goal
            print_goal(intent.goal)
            
            # Start transaction for rollback capability
            transaction_id = self.action_tracker.start_transaction(user_input, intent.goal)
            
            execution_success = False
            step_results = []
            
            try:
                # Show execution progress
                if self.progress and len(intent.steps) > 1:
                    with self.progress.step(f"Executing {len(intent.steps)} steps", total=len(intent.steps)) as update:
                        if self.adaptive:
                            step_results = self.adaptive_planner.execute_with_retry(
                                intent, max_retries=2
                            )
                        else:
                            step_results = execute_plan(intent, self.logger, privilege_tier=self.privilege_tier)
                        update(len(intent.steps))  # Mark all complete
                    execution_success = True
                else:
                    # Single step or no progress - execute directly
                    if self.adaptive:
                        step_results = self.adaptive_planner.execute_with_retry(
                            intent, max_retries=2
                        )
                    else:
                        step_results = execute_plan(intent, self.logger, privilege_tier=self.privilege_tier)
                    execution_success = True
                
                # Track each action for rollback
                for step, result in zip(intent.steps, step_results):
                    self.action_tracker.track_action(
                        tool=step.tool,
                        operation=step.action,
                        params=step.args,
                        result=result,
                        transaction_id=transaction_id
                    )
                
                # Step 6.5: Update knowledge graph with observed relationships
                try:
                    kg = get_knowledge_graph()
                    for step in intent.steps:
                        kg.ingest_action(step.tool, step.action, step.args)
                except Exception:
                    pass  # Non-critical

                # End transaction successfully
                self.action_tracker.end_transaction(transaction_id, "completed")
            
            except Exception:
                # End transaction with failure status
                self.action_tracker.end_transaction(transaction_id, "failed")
                raise
            
            # Print steps with formatting  
            for i, (step, result) in enumerate(zip(intent.steps, step_results), 1):
                print_step(i, step.tool, step.action, step.risk, result)
            
            # Step 7: Update memory with results
            if self.use_memory:
                # Extract paths from results
                for result in step_results:
                    if "path" in str(result).lower():
                        # Simple heuristic: extract file paths
                        words = str(result).split()
                        for word in words:
                            if "/" in word and not word.startswith("http"):
                                self.world_model.update_path_frequency(word)
                
                self.intent_history.record(user_input, intent, step_results)
            
            # Step 8: Add to semantic search
            if self.semantic_search and execution_success:
                try:
                    self.semantic_search.add_command(
                        user_input=user_input,
                        goal=intent.goal,
                        steps=[s.model_dump() for s in intent.steps],
                        success=True
                    )
                except Exception as e:
                    # Non-critical, just log
                    self.logger.log_error(f"Failed to add to semantic search: {e}")
            
            _summary_text = build_execution_summary(intent, step_results)
            print_success(_summary_text)

            # Build result string that includes actual tool output (used by TUI / workflow recorder)
            _step_output_parts = []
            for _step, _res in zip(intent.steps, step_results):
                _res_str = str(_res).strip() if _res is not None else ""
                if _res_str:
                    _step_output_parts.append(f"{_step.tool}.{_step.action}:\n{_res_str}")
            execution_summary = "\n\n".join(_step_output_parts) if _step_output_parts else "Plan executed successfully"

            # Record metrics
            execution_time_ms = (time.time() - start_time) * 1000
            try:
                # Get primary tool
                tool = intent.steps[0].tool if intent.steps else "unknown"
                
                # Get cache info
                cache_hit = (intent == self.intent_cache.get(user_input, context))
                
                # Get token/cost info from router
                router_stats = self.router.get_stats()
                tokens = router_stats['session']['tokens_used']
                cost = router_stats['session']['estimated_cost']
                
                self.metrics.record_command(
                    latency_ms=execution_time_ms,
                    model=selected_model,
                    tool=tool,
                    tokens=tokens,
                    cost=cost,
                    cache_hit=cache_hit,
                    success=True
                )
            except Exception:
                pass  # Non-critical
            
            # Collect feedback (non-blocking)
            try:
                self.feedback_collector.collect(
                    user_input, intent, execution_time_ms, success=True
                )
            except Exception:
                pass  # Non-critical
            
            # Record prompt evolution result (for self-improvement)
            if self.enable_prompt_evolution and hasattr(self, '_prompt_version_used'):
                try:
                    self.prompt_evolution.record_result(
                        version_id=self._prompt_version_used,
                        user_input=user_input,
                        intent_ir=intent.to_dict(),
                        success=True,
                        result="Executed successfully"
                    )
                except Exception:
                    pass  # Non-critical
            
            return execution_summary
        
        except IntentTranslationError as e:
            error_msg = str(e)
            self.logger.log_error(error_msg, {"user_input": user_input})
            
            # Record failure in semantic search
            if self.semantic_search:
                try:
                    self.semantic_search.add_command(
                        user_input=user_input,
                        goal="Translation failed",
                        steps=[],
                        success=False
                    )
                except Exception:
                    pass
            
            print_error(f"Failed to understand command: {error_msg}")
            return f"Error: {error_msg}"
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.log_error(error_msg, {"user_input": user_input})
            
            # Record prompt evolution failure
            if self.enable_prompt_evolution and hasattr(self, '_prompt_version_used') and 'intent' in locals():
                try:
                    self.prompt_evolution.record_result(
                        version_id=self._prompt_version_used,
                        user_input=user_input,
                        intent_ir=intent.to_dict(),
                        success=False,
                        result=None
                    )
                except Exception:
                    pass  # Non-critical
            
            # Analyze failure and provide intelligent suggestions
            ctx_mgr = get_context_manager()
            failure_analysis = self.failure_analyzer.analyze_failure(
                user_input=user_input,
                intent_goal=intent.goal if 'intent' in locals() else "Unknown",
                tool="orchestrator",
                error_message=str(e),
                context=ctx_mgr.get_full_context()
            )
            
            # Show intelligent error message
            console.print(f"\n[red]❌ Execution failed:[/red] {error_msg}")
            
            # Show recovery suggestions
            if failure_analysis["suggestions"]:
                console.print("\n[cyan]💡 Suggestions to fix this:[/cyan]")
                for i, suggestion in enumerate(failure_analysis["suggestions"], 1):
                    console.print(f"  {i}. {suggestion}")
            
            # Show similar failures
            if failure_analysis["is_recurring"]:
                console.print("\n[yellow]⚠️  This failure has occurred before[/yellow]")
                console.print("  Consider reviewing the suggestions above carefully")
            
            # Show recovery plan if available
            if failure_analysis["similar_failures"]:
                most_recent = failure_analysis["similar_failures"][0]
                recovery_plan = self.failure_analyzer.generate_recovery_plan(most_recent)
                if recovery_plan:
                    console.print("\n[cyan]📋 Recovery plan:[/cyan]")
                    console.print(f"  {recovery_plan}")
            
            # Record failure in semantic search
            if self.semantic_search:
                try:
                    self.semantic_search.add_command(
                        user_input=user_input,
                        goal="Execution failed",
                        steps=[],
                        success=False
                    )
                except Exception:
                    pass
            
            print_error(error_msg)
            return error_msg
    
    def execute_iterative(
        self,
        user_input: str,
        max_iterations: int = 12,
        dry_run: bool = False,
        force_provider: Optional[str] = None,
    ) -> str:
        """
        Execute a command with iterative ReAct loop

        This method implements the ReAct (Reasoning + Acting) pattern:
        1. Plan based on current context
        2. Execute plan
        3. Observe results
        4. Check if goal achieved
        5. If not, re-plan with new observations
        6. Repeat until goal achieved (automatically continues in batches of max_iterations)

        Args:
            user_input: Natural language command
            max_iterations: Batch size for iterations (default: 12)
            dry_run: If True, show plan without executing
            force_provider: Override routing and use this provider for all iterations

        Returns:
            Human-readable result
        """
        from zenus_core.brain.goal_tracker import GoalTracker

        # Parse inline provider override directives
        from zenus_core.brain.provider_override import parse_provider_override, describe_override
        _clean, _detected_provider, _detected_model = parse_provider_override(user_input)
        if _detected_provider or _detected_model:
            user_input = _clean
            if not force_provider and _detected_provider:
                force_provider = _detected_provider
            label = describe_override(force_provider, _detected_model)
            console.print(f"[dim cyan]↳ Using {label} for this command[/dim cyan]")

        # Accumulator for observations
        all_observations = []

        # Initial context from memory
        context = ""
        if self.use_memory:
            context = self._build_context(user_input)

        # Web search injection — same gate as execute_command Step 0a.
        # Ensures each iterative session starts with fresh data when the query
        # is time-sensitive (sports schedules, versions, news, etc.).
        should_search, search_reason = self.search_engine.should_search(user_input)
        if should_search:
            search_results = self.web_search.search(user_input)
            search_context = format_results_for_context(search_results)
            if search_context:
                context = (
                    f"{context}\n\n[Web Search Results - {search_reason}]\n{search_context}"
                    if context
                    else f"[Web Search Results - {search_reason}]\n{search_context}"
                )
                console.print(f"[dim cyan]↳ Web search: {search_reason}[/dim cyan]")
            else:
                # Search attempted but returned nothing — tell LLM so it
                # doesn't waste iterations trying tool-based web fetches.
                _no_results = (
                    "[Web Search attempted but returned no current results. "
                    "Answer from training knowledge and acknowledge the limitation.]"
                )
                context = f"{context}\n\n{_no_results}" if context else _no_results
                console.print("[dim yellow]↳ Web search returned no results[/dim yellow]")

        # Route to appropriate model (iterative = likely complex)
        selected_model, complexity = self.router.route(user_input, iterative=True, force_model=force_provider)

        # Instantiate the chosen LLM for this execution
        self.llm = get_llm(force_provider=selected_model)

        print_goal(f"Starting iterative execution: {user_input}")
        console.print(f"[dim]Batch size: {max_iterations} iterations per batch[/dim]")
        console.print(f"[dim]Using model: {selected_model} (complexity: {complexity.score:.2f})[/dim]\n")
        
        iteration = 0
        goal_achieved = False
        batch_number = 1
        max_total_iterations = 50  # Absolute safety limit
        stuck_count = 0  # Track repeated failures
        last_goal = None  # Track if we're repeating the same goal
        
        try:
            # Continue until goal is achieved (with safety limit)
            while not goal_achieved and iteration < max_total_iterations:
                # Initialize goal tracker for this batch
                batch_max = iteration + max_iterations
                goal_tracker = GoalTracker(max_iterations=batch_max)
                
                # Run batch of iterations
                batch_start = iteration
                while not goal_achieved and iteration < batch_max:
                    iteration += 1
                    iteration_in_batch = iteration - batch_start
                    console.print(f"\n[bold cyan]═══ Iteration {iteration} (Batch {batch_number}, {iteration_in_batch}/{max_iterations}) ═══[/bold cyan]")
                
                    # Build enhanced input with context and observations
                    enhanced_input = user_input
                    if context:
                        enhanced_input += f"\n\nContext: {context}"
                    if all_observations:
                        obs_text = "\n".join([f"- {obs}" for obs in all_observations[-5:]])  # Last 5 observations
                        enhanced_input += f"\n\nPrevious observations:\n{obs_text}"
                    
                    # Step 1: Translate intent with accumulated context
                    # Use streaming to avoid timeouts on complex planning
                    if self.progress:
                        with self.progress.thinking("Planning next steps"):
                            intent = self.llm.translate_intent(enhanced_input, stream=True)
                    else:
                        intent = self.llm.translate_intent(enhanced_input, stream=True)
                    
                    # Log intent
                    self.logger.log_intent(user_input, intent)

                    # Show goal for this iteration
                    console.print(f"[yellow]→ Goal:[/yellow] {intent.goal}")

                    # Q&A short-circuit — if the LLM treated this as a question
                    # (e.g. because search results were injected into context),
                    # answer directly and exit the loop immediately.
                    if intent.is_question:
                        answer = self.llm.ask(enhanced_input)
                        console.print(f"\n[green]{answer}[/green]")
                        return answer

                    if dry_run:
                        console.print(self._format_dry_run(intent))
                        continue

                    # Step 2: Execute plan
                    step_results = []
                    iteration_observations = []
                    
                    if self.adaptive:
                        step_results = self.adaptive_planner.execute_with_retry(
                            intent, max_retries=2
                        )
                    else:
                        step_results = execute_plan(intent, self.logger, privilege_tier=self.privilege_tier)
                    
                    # Step 3: Collect observations
                    for i, (step, result) in enumerate(zip(intent.steps, step_results), 1):
                        print_step(i, step.tool, step.action, step.risk, result)
                        
                        # Create observation with better formatting
                        # Handle empty/None results gracefully
                        result_str = str(result).strip() if result else "(no output)"
                        
                        # If result is very short or generic, add context
                        if not result_str or result_str in ["None", "(no output)", ""]:
                            result_str = "(command executed, no visible output)"
                        elif len(result_str) < 10:
                            result_str = f"(output: {result_str})"
                        else:
                            # Truncate long results but keep MUCH more content
                            # For file reads, we need substantial content to make sense of the data
                            # Increased from 300 to 2000 to capture meaningful file content
                            max_obs_length = 2000
                            if len(result_str) > max_obs_length:
                                # For very long results, show beginning and end
                                half = (max_obs_length - 20) // 2
                                result_str = result_str[:half] + "\n...(truncated)...\n" + result_str[-half:]
                        
                        observation = f"{step.tool}.{step.action}({', '.join(f'{k}={v}' for k, v in step.args.items())}) → {result_str}"
                        iteration_observations.append(observation)
                    
                    # Add to all observations
                    all_observations.extend(iteration_observations)
                    
                    # Step 4: Update memory
                    if self.use_memory:
                        self.session_memory.add_intent(intent)
                        for result in step_results:
                            if "path" in str(result).lower():
                                words = str(result).split()
                                for word in words:
                                    if "/" in word and not word.startswith("http"):
                                        self.world_model.update_path_frequency(word)
                        
                        self.intent_history.record(user_input, intent, step_results)
                    
                    # Step 5: Check if goal achieved
                    console.print("\n")  # Blank line before reflection
                    
                    goal_status = goal_tracker.check_goal(
                        user_goal=user_input,
                        original_intent=intent,
                        observations=iteration_observations,
                        stream=True  # Enable streaming for real-time reflection
                    )
                    
                    # Display reflection
                    if goal_status.achieved:
                        console.print("\n[bold green]✓ Goal Achieved![/bold green]")
                        console.print(f"[dim]{goal_status.reasoning}[/dim]")
                        goal_achieved = True
                    else:
                        console.print("\n[yellow]⟳ Goal not yet achieved[/yellow]")
                        console.print(f"[dim]Confidence: {goal_status.confidence:.0%}[/dim]")
                        console.print(f"[dim]Reasoning: {goal_status.reasoning}[/dim]")
                        
                        # Detect stuck state (repeating same goal with low confidence)
                        if intent.goal == last_goal and goal_status.confidence < 0.4:
                            stuck_count += 1
                        else:
                            stuck_count = 0
                        
                        last_goal = intent.goal
                        
                        # If stuck for 3+ iterations, warn user
                        if stuck_count >= 3:
                            console.print(f"\n[red]⚠️  Appears to be stuck (same goal repeated {stuck_count} times with low progress)[/red]")
                            console.print("[yellow]Consider:[/yellow]")
                            console.print("  • Breaking down the task into smaller steps")
                            console.print("  • Trying a different approach")
                            console.print("  • Checking if manual intervention is needed")
                            
                            response = console.input("\n[bold]Continue trying? (y/n):[/bold] ")
                            if response.lower() not in ('y', 'yes'):
                                console.print("[yellow]Stopping iterations by user request[/yellow]")
                                return f"Task stopped after {iteration} iteration(s) - appears stuck"
                            
                            # Reset stuck count after user confirms
                            stuck_count = 0
                        
                        if goal_status.next_steps:
                            console.print("\n[cyan]Next steps suggested:[/cyan]")
                            for step in goal_status.next_steps:
                                console.print(f"  • {step}")
                        
                        # Update context for next iteration
                        context = f"Previous attempt: {intent.goal}. Observations: {', '.join(iteration_observations[-3:])}"
            
                # Check if batch completed without achieving goal
                if iteration >= batch_max and not goal_achieved:
                    batch_number += 1
                    console.print(f"\n[yellow]⟳ Batch {batch_number - 1} complete ({max_iterations} iterations)[/yellow]")
                    console.print(f"[dim]Goal not yet achieved. {iteration}/{max_total_iterations} total iterations used.[/dim]")
                    
                    # Ask user to continue after each batch (safety check)
                    if batch_number > 1:  # After first batch
                        response = console.input(f"\n[bold]Continue with batch {batch_number}? (y/n):[/bold] ")
                        if response.lower() not in ('y', 'yes'):
                            console.print("[yellow]Stopping iterations by user request[/yellow]")
                            return f"Task stopped after {iteration} iteration(s) - goal not achieved"
                    
                    console.print(f"[dim]Continuing with batch {batch_number}...[/dim]\n")
            
            # Check if we hit the absolute limit
            if iteration >= max_total_iterations and not goal_achieved:
                console.print(f"\n[red]⚠️  Maximum iterations reached ({max_total_iterations})[/red]")
                console.print("[yellow]Goal was not achieved. Task may be:[/yellow]")
                console.print("  • Too complex for iterative approach")
                console.print("  • Requires manual intervention")
                console.print("  • Blocked by permissions or system constraints")
                return f"Task stopped after {iteration} iteration(s) - maximum iterations reached"
            
            # Final result (goal achieved)
            print_success(f"Task completed in {iteration} iteration(s) across {batch_number} batch(es)")
            
            # Add to semantic search
            if self.semantic_search:
                try:
                    self.semantic_search.add_command(
                        user_input=user_input,
                        goal=intent.goal,
                        steps=[s.model_dump() for s in intent.steps],
                        success=True
                    )
                except Exception:
                    pass
            
            return f"Task completed successfully in {iteration} iteration(s)"
        
        except Exception as e:
            error_msg = f"Iterative execution error: {str(e)}"
            self.logger.log_error(error_msg, {"user_input": user_input})
            print_error(error_msg)
            return error_msg

    def _build_context(self, user_input: str) -> str:
        """Build context string from memory and environment"""
        context_parts = []
        
        # Environmental context (new!)
        ctx_mgr = get_context_manager()
        env_context = ctx_mgr.get_contextual_prompt()
        if env_context:
            context_parts.append("=== Current Environment ===")
            context_parts.append(env_context)
        
        # Recent intents
        if self.use_memory:
            summary = self.session_memory.get_context_summary(max_intents=3)
            if summary:
                context_parts.append(f"\n=== Recent Activity ===\n{summary}")
        
        # Frequent paths (if query mentions files/directories)
        if any(word in user_input.lower() for word in ["file", "folder", "directory", "path"]):
            if self.use_memory:
                frequent_paths = self.world_model.get_frequent_paths(limit=5)
                if frequent_paths:
                    context_parts.append(f"\n=== Frequent Paths ===\n{', '.join(frequent_paths)}")
        
        return "\n".join(context_parts)
    
    def execute_with_multi_agent(self, task: str, context: Dict = None) -> str:
        """
        Execute task using multi-agent collaboration
        
        This uses specialized agents (Researcher, Planner, Executor, Validator)
        working together for complex tasks.
        
        Args:
            task: Complex task to solve
            context: Additional context
        
        Returns:
            Human-readable result
        """
        if not self.enable_multi_agent or not self.multi_agent:
            return "Multi-agent collaboration is not enabled"
        
        try:
            console.print("[cyan bold]🤖 Multi-Agent Collaboration:[/cyan bold] Deploying specialized agents...\n")
            
            # Run collaboration
            session = self.multi_agent.collaborate(task, context or {})
            
            # Display results from each agent
            console.print("[bold]Collaboration Summary:[/bold]")
            console.print(f"Session ID: {session.session_id}")
            console.print(f"Agents Involved: {', '.join([a.value for a in session.agents_involved])}")
            console.print(f"Duration: {session.total_duration:.2f}s\n")
            
            for result in session.results:
                agent_name = result.agent.value.capitalize()
                status = "✓" if result.success else "✗"
                color = "green" if result.success else "red"
                
                console.print(f"[{color}]{status} {agent_name} Agent[/{color}]")
                console.print(f"  Confidence: {result.confidence:.0%}")
                console.print(f"  Reasoning: {result.reasoning}")
                console.print(f"  Duration: {result.duration:.2f}s\n")
            
            # Final result
            if session.success:
                console.print("[green bold]✓ Collaboration successful![/green bold]")
                console.print(f"[dim]{session.final_result}[/dim]")
                return session.final_result
            else:
                console.print("[red bold]✗ Collaboration failed[/red bold]")
                console.print(f"[dim]{session.final_result}[/dim]")
                return f"Error: {session.final_result}"
                
        except Exception as e:
            error_msg = f"Multi-agent collaboration failed: {e}"
            self.logger.log_error(error_msg, {"task": task})
            return error_msg
    
    def run_health_check(self) -> Dict:
        """
        Run proactive monitoring health check
        
        Returns:
            Health check status and any alerts
        """
        if not self.enable_proactive_monitoring or not self.proactive_monitor:
            return {"status": "disabled", "message": "Proactive monitoring is not enabled"}
        
        try:
            alerts = self.proactive_monitor.run_checks()
            status = self.proactive_monitor.get_status()
            
            if alerts:
                console.print(f"\n[yellow bold]🔍 Proactive Monitor:[/yellow bold] Found {len(alerts)} issue(s)\n")
                
                for alert in alerts:
                    level_color = {
                        "critical": "red",
                        "warning": "yellow",
                        "info": "cyan"
                    }.get(alert.level.value, "white")
                    
                    console.print(f"[{level_color}]{alert.level.value.upper()}[/{level_color}]: {alert.message}")
                    
                    if alert.auto_remediated:
                        console.print(f"  [green]✓ Auto-remediated[/green]: {alert.remediation_result}")
                    elif alert.remediation_result:
                        console.print(f"  [red]✗ Remediation failed[/red]: {alert.remediation_result}")
                    console.print()
            else:
                console.print("[green]✓ All health checks passed[/green]")
            
            return {
                "status": "ok",
                "alerts": len(alerts),
                "auto_remediated": sum(1 for a in alerts if a.auto_remediated),
                "details": status
            }
            
        except Exception as e:
            error_msg = f"Health check failed: {e}"
            self.logger.log_error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def visualize_result(self, data: any, title: Optional[str] = None) -> str:
        """
        Visualize result data (auto-generates charts/tables)
        
        Args:
            data: Data to visualize
            title: Optional title
        
        Returns:
            Formatted visualization
        """
        if not self.enable_visualization or not self.visualizer:
            return str(data)
        
        try:
            return self.visualizer.visualize(data, title=title)
        except Exception as e:
            self.logger.log_error(f"Visualization failed: {e}")
            return str(data)
    
    def _format_dry_run(self, intent: IntentIR) -> str:
        """Format dry-run output"""
        output = [f"DRY RUN - Would execute: {intent.goal}\n"]
        
        for i, step in enumerate(intent.steps, 1):
            output.append(
                f"{i}. {step.tool}.{step.action}({step.args}) [risk={step.risk}]"
            )
        
        return "\n".join(output)
    
    async def async_execute_command(
        self,
        user_input: str,
        dry_run: bool = False,
        force_oneshot: bool = False,
        force_provider: Optional[str] = None,
    ) -> str:
        """
        Async version of execute_command.

        Uses the LLM's native async API when available (AnthropicLLM),
        otherwise delegates to asyncio.to_thread to avoid blocking the
        event loop.

        Args:
            user_input: Natural language command
            dry_run: If True, show plan without executing
            force_oneshot: Skip iterative detection
            force_provider: Override LLM provider for this call

        Returns:
            Human-readable result
        """
        return await asyncio.to_thread(
            self.execute_command,
            user_input,
            dry_run,
            False,  # explain
            force_oneshot,
            force_provider,
        )

    def interactive_shell(self):
        """Run interactive REPL mode"""
        # Elevate to privileged tier — the user is present and can review actions
        self.privilege_tier = PrivilegeTier.PRIVILEGED

        # Try to use enhanced shell (with tab completion, syntax highlighting)
        enhanced_shell = None
        try:
            from zenus_core.shell.enhanced_shell import create_enhanced_shell
            enhanced_shell = create_enhanced_shell()
        except ImportError:
            # Enhanced shell not available - fall back to basic readline
            pass
        
        # Fallback to basic readline if enhanced shell not available
        if enhanced_shell is None:
            try:
                import readline
                import os
                
                # Set up history file
                history_file = os.path.expanduser("~/.zenus/history.txt")
                os.makedirs(os.path.dirname(history_file), exist_ok=True)
                
                # Load history if exists
                try:
                    readline.read_history_file(history_file)
                except FileNotFoundError:
                    pass
                
                # Set history size
                readline.set_history_length(1000)
                
                # Save history on exit
                import atexit
                atexit.register(readline.write_history_file, history_file)
                
            except ImportError:
                # readline not available (Windows without pyreadline)
                pass
        
        console.print("\n[bold cyan]Zenus Interactive Shell[/bold cyan]")
        console.print("Type 'exit' or 'quit' to exit")
        console.print("Special commands: status, memory, model, history, rollback, update, explain, workflow")
        if enhanced_shell:
            console.print("Enhanced mode: Tab completion, Ctrl+R search, multi-line (Esc+Enter)")
        else:
            console.print("Use ↑↓ arrows for command history")
        console.print()
        
        # Track commands for pattern detection
        command_count = 0
        
        while True:
            try:
                # Get user input (enhanced or basic)
                if enhanced_shell:
                    # Enhanced shell prompt (uses prompt_toolkit styling)
                    user_input = enhanced_shell.prompt()
                else:
                    # Use ANSI codes with readline escape sequences
                    # \001 and \002 mark non-printing characters for readline
                    prompt = "\n\001\033[1;32m\002zenus >\001\033[0m\002 "
                    user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                if user_input in ("exit", "quit"):
                    console.print("[dim]Goodbye![/dim]")
                    break
                
                # Handle special commands
                if user_input == "status":
                    from zenus_core.shell.commands import handle_status_command
                    handle_status_command(self)
                    continue
                
                if user_input.startswith("memory"):
                    from zenus_core.shell.commands import handle_memory_command
                    parts = user_input.split()
                    subcommand = parts[1] if len(parts) > 1 else "stats"
                    handle_memory_command(self, subcommand)
                    continue
                
                if user_input == "update":
                    from zenus_core.shell.commands import handle_update_command
                    handle_update_command()
                    continue
                
                if user_input.startswith("explain"):
                    from zenus_core.shell.commands import handle_explain_command
                    parts = user_input.split()
                    arg = parts[1] if len(parts) > 1 else "last"
                    handle_explain_command(self, arg)
                    continue
                
                if user_input.startswith("workflow"):
                    from zenus_core.shell.commands import handle_workflow_command
                    parts = user_input.split()
                    subcommand = parts[1] if len(parts) > 1 else "list"
                    args = parts[2:] if len(parts) > 2 else []
                    handle_workflow_command(self, subcommand, *args)
                    continue

                if user_input.startswith("model"):
                    from zenus_core.shell.commands import handle_model_command
                    parts = user_input.split()
                    subcommand = parts[1] if len(parts) > 1 else "status"
                    args = parts[2:] if len(parts) > 2 else []
                    handle_model_command(subcommand, args)
                    continue

                # Check for --explain flag
                explain = False
                if "--explain" in user_input:
                    explain = True
                    user_input = user_input.replace("--explain", "").strip()
                
                # Check for --iterative flag
                iterative = False
                if "--iterative" in user_input:
                    iterative = True
                    user_input = user_input.replace("--iterative", "").strip()
                
                # Execute command
                import time
                start_time = time.time()
                
                if iterative:
                    result = self.execute_iterative(user_input)
                else:
                    result = self.execute_command(user_input, explain=explain)
                
                execution_time = time.time() - start_time
                
                # Record step if workflow recording is active
                try:
                    from zenus_core.workflows import get_workflow_recorder
                    recorder = get_workflow_recorder()
                    if recorder.recording:
                        recorder.record_step(user_input, str(result), execution_time)
                except Exception:
                    pass
                
                # Check for patterns periodically
                command_count += 1
                if command_count % 10 == 0:
                    try:
                        from zenus_core.shell.commands import check_and_suggest_patterns
                        check_and_suggest_patterns(self)
                    except Exception:
                        pass  # Silently fail if pattern detection fails
                
            except KeyboardInterrupt:
                console.print("\n[dim]Use 'exit' to quit[/dim]")
                continue
            except EOFError:
                console.print("\n[dim]Goodbye![/dim]")
                break
            except Exception as e:
                print_error(f"Shell error: {e}")
