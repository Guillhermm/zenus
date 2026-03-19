# Zenus Test Coverage

> Last updated: 2026-03-19  

> **2496 total test cases** across 73 test files


## Summary

| Tier | Files | Tests |
|------|-------|-------|
| Unit | 59 | 2342 |
| Integration | 8 | 143 |
| E2E | 2 | 11 |
| Scripts | 0 | 0 |
| **Total** | **73** | **2496** |


---

## Unit Tests (2342 tests)


### [unit/test_action_tracker.py](../tests/unit/test_action_tracker.py) — 16 tests

- `test_tracker_initialization`
- `test_start_transaction`
- `test_end_transaction`
- `test_track_file_create_action`
- `test_file_create_rollback_strategy`
- `test_file_move_rollback_strategy`
- `test_package_install_rollback_strategy`
- `test_git_commit_rollback_strategy`
- `test_git_push_not_rollbackable`
- `test_service_start_rollback_strategy`
- `test_multiple_actions_in_transaction`
- `test_get_recent_transactions`
- `test_create_checkpoint`
- `test_checkpoint_duplicate_name`
- `test_mark_rolled_back`
- `test_container_run_rollback_strategy`

### [unit/test_adaptive_planner.py](../tests/unit/test_adaptive_planner.py) — 36 tests


#### `TestExecutionResult`

- `test_success_result`
- `test_failure_result`

#### `TestAdaptivePlannerInit`

- `test_initializes_empty_history`
- `test_logger_stored`

#### `TestAdaptivePlannerExecuteSingleStep`

- `test_returns_success_on_valid_step`
- `test_returns_failure_when_tool_not_found`
- `test_returns_failure_when_action_not_found`
- `test_returns_failure_on_safety_error`
- `test_returns_failure_on_generic_exception`
- `test_logs_step_result_on_success`
- `test_logs_step_result_on_failure`

#### `TestAdaptivePlannerExecuteAdaptive`

- `test_returns_true_when_all_steps_succeed`
- `test_returns_false_when_step_fails_all_retries`
- `test_retries_up_to_max_retries`
- `test_clears_execution_history_at_start`
- `test_successful_steps_appended_to_history`
- `test_history_records_attempt_number`
- `test_on_failure_callback_called`
- `test_logs_execution_start`
- `test_logs_execution_end_on_success`
- `test_logs_execution_end_on_failure`

#### `TestAdaptivePlannerGetExecutionSummary`

- `test_summary_empty_history`
- `test_summary_counts_total_steps`
- `test_summary_counts_retried_steps`
- `test_summary_success_rate_one_when_steps_present`

#### `TestAdaptPlannerAdaptOnFailure`

- `test_returns_none_currently`

#### `TestSandboxedAdaptivePlannerInit`

- `test_inherits_adaptive_planner`
- `test_tools_registry_available`

#### `TestSandboxedExecuteSingleStep`

- `test_returns_success_on_valid_step`
- `test_returns_failure_on_sandbox_violation`
- `test_returns_failure_when_tool_not_found`
- `test_returns_failure_when_action_not_found`
- `test_logs_on_sandbox_violation`

#### `TestSandboxedExecuteWithRetry`

- `test_returns_list_of_step_outputs`
- `test_failed_steps_prefixed_with_failed`
- `test_calls_execute_adaptive_with_intent`

### [unit/test_browser_ops_unit.py](../tests/unit/test_browser_ops_unit.py) — 38 tests


#### `TestBrowserOpsPlaywrightCheck`

- `test_playwright_installed_true`
- `test_playwright_installed_false_when_import_fails`
- `test_ensure_playwright_raises_when_not_installed`
- `test_ensure_playwright_no_raise_when_installed`

#### `TestBrowserOpsOpen`

- `test_open_not_installed_raises_runtime`
- `test_open_chromium_returns_title`
- `test_open_firefox`
- `test_open_webkit`
- `test_open_unknown_browser_returns_error`
- `test_open_exception_returns_error`
- `test_open_headless_skips_wait`
- `test_open_non_headless_calls_wait`

#### `TestBrowserOpsScreenshot`

- `test_screenshot_not_installed_raises`
- `test_screenshot_saves_to_path`
- `test_screenshot_full_page_flag`
- `test_screenshot_expands_tilde`
- `test_screenshot_exception_returns_error`

#### `TestBrowserOpsGetText`

- `test_get_text_not_installed_raises`
- `test_get_text_no_selector_returns_body`
- `test_get_text_with_selector`
- `test_get_text_selector_not_found`
- `test_get_text_exception_returns_error`

#### `TestBrowserOpsClick`

- `test_click_not_installed_raises`
- `test_click_element_returns_new_url`
- `test_click_waits_after_click`
- `test_click_exception_returns_error`

#### `TestBrowserOpsFill`

- `test_fill_not_installed_raises`
- `test_fill_calls_page_fill`
- `test_fill_exception_returns_error`

#### `TestBrowserOpsSearch`

- `test_search_not_installed_raises`
- `test_search_unknown_engine_returns_error`
- `test_search_google_with_results`
- `test_search_no_results_returns_message`
- `test_search_duckduckgo`
- `test_search_exception_returns_error`

#### `TestBrowserOpsDownload`

- `test_download_not_installed_raises`
- `test_download_saves_to_directory`
- `test_download_exception_returns_error`

### [unit/test_code_exec.py](../tests/unit/test_code_exec.py) — 31 tests


#### `TestTruncate`

- `test_short_text_unchanged`
- `test_exact_limit_unchanged`
- `test_long_text_is_truncated`
- `test_truncated_text_contains_both_ends`
- `test_truncation_reports_dropped_char_count`

#### `TestCodeExecPython`

- `test_python_returns_stdout`
- `test_python_includes_stderr`
- `test_python_no_output_placeholder`
- `test_python_raises_on_nonzero_exit`
- `test_python_raises_on_timeout`
- `test_python_unlinks_script_on_success`
- `test_python_unlinks_script_on_failure`
- `test_python_uses_sys_executable`
- `test_python_default_timeout_30`
- `test_python_custom_timeout`
- `test_python_working_dir_forwarded`
- `test_python_output_capped_at_8000`

#### `TestCodeExecBash`

- `test_bash_returns_stdout`
- `test_bash_raises_on_nonzero_exit`
- `test_bash_raises_on_timeout`
- `test_bash_unlinks_script_on_success`
- `test_bash_unlinks_script_on_failure`
- `test_bash_uses_bash_interpreter`
- `test_bash_default_timeout_60`
- `test_bash_sets_executable_permission`
- `test_bash_output_capped_at_8000`
- `test_bash_no_output_placeholder`

#### `TestCodeExecDryRun`

- `test_dry_run_contains_prefix`
- `test_dry_run_includes_code_preview`
- `test_dry_run_truncates_long_code`
- `test_dry_run_does_not_execute`

### [unit/test_config.py](../tests/unit/test_config.py) — 64 tests


#### `TestProfile`

- `test_dev_value`
- `test_staging_value`
- `test_production_value`
- `test_profile_from_string`
- `test_invalid_profile_raises`

#### `TestLLMConfig`

- `test_defaults`
- `test_custom_values`
- `test_temperature_boundary_zero`
- `test_temperature_boundary_one`
- `test_temperature_too_low`
- `test_temperature_too_high`

#### `TestFallbackConfig`

- `test_defaults`
- `test_custom_providers`
- `test_disabled`

#### `TestCircuitBreakerSettings`

- `test_defaults`
- `test_custom_values`

#### `TestRetrySettings`

- `test_defaults`
- `test_disable_jitter`

#### `TestCacheConfig`

- `test_defaults`

#### `TestSafetyConfig`

- `test_defaults`
- `test_disable_sandbox`

#### `TestMonitoringConfig`

- `test_defaults`

#### `TestFeaturesConfig`

- `test_defaults`

#### `TestZenusConfig`

- `test_defaults`
- `test_is_dev`
- `test_is_staging`
- `test_is_production`
- `test_custom_normalises_none_to_empty_dict`
- `test_custom_accepts_dict`
- `test_profile_string_accepted`
- `test_validate_assignment`

#### `TestConfigLoader`

- `test_loads_yaml_file`
- `test_missing_file_falls_back_to_defaults`
- `test_empty_yaml_uses_defaults`
- `test_profile_override_merges_correctly`
- `test_non_active_profile_not_merged`
- `test_get_config_returns_zenus_config`
- `test_reload_re_reads_file`
- `test_save_config_writes_yaml`
- `test_invalid_yaml_falls_back_to_defaults`
- `test_merge_dicts_deep`
- `test_detect_profile_from_env`
- `test_detect_profile_defaults_to_dev`
- `test_detect_profile_unknown_falls_back_to_dev`
- `test_find_config_from_zenus_config_env`
- `test_stop_watching_when_observer_is_none`
- `test_stop_watching_stops_observer`

#### `TestSecretsManager`

- `test_get_existing_secret`
- `test_get_missing_secret_returns_default`
- `test_has_secret_true`
- `test_has_secret_false`
- `test_get_llm_api_key_anthropic`
- `test_get_llm_api_key_openai`
- `test_get_llm_api_key_deepseek`
- `test_get_llm_api_key_unknown_provider`
- `test_get_llm_api_key_case_insensitive`
- `test_validate_required_all_present`
- `test_validate_required_missing`
- `test_list_available_returns_keys`
- `test_mask_secret_normal_value`
- `test_mask_secret_short_value`
- `test_mask_secret_empty_string`
- `test_loads_from_env_file`
- `test_find_env_file_returns_none_when_no_files_exist`

### [unit/test_container_ops.py](../tests/unit/test_container_ops.py) — 25 tests


#### `TestDetectRuntime`

- `test_detects_docker`
- `test_falls_back_to_podman`
- `test_returns_none_when_no_runtime`

#### `TestRun`

- `test_no_runtime_returns_error`
- `test_success_returns_stdout`
- `test_nonzero_returncode_returns_stderr`
- `test_exception_returns_error`

#### `TestContainerRun`

- `test_basic_run`
- `test_run_with_detach`
- `test_run_with_name`
- `test_run_with_ports`
- `test_run_with_volumes`
- `test_run_with_command`

#### `TestPs`

- `test_ps_basic`
- `test_ps_all`

#### `TestStopRemove`

- `test_stop`
- `test_remove_basic`
- `test_remove_force`

#### `TestLogsExec`

- `test_logs`
- `test_exec`

#### `TestImageOps`

- `test_images`
- `test_pull`
- `test_build`
- `test_rmi_basic`
- `test_rmi_force`

### [unit/test_context_feedback_workflows.py](../tests/unit/test_context_feedback_workflows.py) — 62 tests


#### `TestContextManagerTimeContext`

- `test_time_context_has_required_keys`
- `test_time_of_day_is_valid_value`
- `test_is_weekend_is_bool`
- `test_is_work_hours_is_bool`
- `test_timestamp_format`

#### `TestContextManagerDirectoryContext`

- `test_directory_context_has_required_keys`
- `test_absolute_path_is_absolute`
- `test_project_name_is_directory_basename`

#### `TestContextManagerDetectProjectType`

- `test_detects_python_from_pyproject`
- `test_detects_node_from_package_json`
- `test_detects_rust_from_cargo_toml`
- `test_returns_none_for_unknown`

#### `TestContextManagerTrackFileAccess`

- `test_track_adds_file_to_recent`
- `test_track_does_not_duplicate`
- `test_track_trims_to_max`

#### `TestContextManagerGetFullContext`

- `test_full_context_has_all_sections`
- `test_contextual_prompt_is_string`

#### `TestContextManagerSystemContext`

- `test_system_context_has_required_keys`

#### `TestGetContextManagerSingleton`

- `test_returns_same_instance`

#### `TestFeedbackEntry`

- `test_to_dict_round_trip`

#### `TestFeedbackCollectorDisabled`

- `test_collect_returns_none_when_disabled`
- `test_env_var_disables_prompts`

#### `TestFeedbackCollectorStats`

- `test_stats_empty_file_returns_zeros`
- `test_stats_count_positive_and_negative`
- `test_stats_positive_rate`
- `test_stats_by_tool`
- `test_stats_cache_is_used`

#### `TestFeedbackCollectorSanitize`

- `test_sanitize_removes_password`
- `test_sanitize_removes_email`
- `test_sanitize_leaves_normal_text_unchanged`

#### `TestFeedbackCollectorExport`

- `test_export_creates_file`
- `test_export_skips_negative_by_default`

#### `TestGetFeedbackCollectorSingleton`

- `test_returns_same_instance`

#### `TestWorkflowStep`

- `test_default_timestamp_is_set`
- `test_duration_defaults_to_zero`

#### `TestWorkflow`

- `test_to_dict_and_from_dict_round_trip`
- `test_default_use_count_is_zero`

#### `TestWorkflowRecorder`

- `test_start_recording_sets_recording_flag`
- `test_start_recording_while_active_returns_message`
- `test_stop_recording_no_steps_discards`
- `test_stop_recording_saves_file`
- `test_stop_recording_resets_state`
- `test_cancel_recording_clears_state`
- `test_cancel_when_not_recording`
- `test_record_step_when_not_recording_is_noop`
- `test_record_step_appends_step`
- `test_load_workflow_returns_none_for_missing`
- `test_save_and_load_workflow`
- `test_list_workflows_empty`
- `test_list_workflows_returns_sorted_names`
- `test_delete_existing_workflow`
- `test_delete_nonexistent_workflow`
- `test_get_workflow_info_returns_dict`
- `test_get_workflow_info_steps_count`
- `test_replay_nonexistent_returns_not_found`
- `test_replay_returns_command_list`
- `test_replay_parameter_substitution`
- `test_replay_increments_use_count`
- `test_parameterize_workflow_saves_parameters`
- `test_export_and_import_round_trip`
- `test_import_nonexistent_file_returns_error`

#### `TestGetWorkflowRecorderSingleton`

- `test_returns_same_instance`

### [unit/test_dependency_analyzer.py](../tests/unit/test_dependency_analyzer.py) — 30 tests


#### `TestDependencyAnalyzerEmptyAndSingle`

- `test_empty_intent_returns_empty_graph`
- `test_single_step_returns_trivial_graph`

#### `TestDependencyGraphBuilding`

- `test_independent_file_ops_on_different_paths`
- `test_same_path_creates_dependency`
- `test_parent_child_path_creates_dependency`
- `test_file_write_then_read_creates_dependency`
- `test_file_copy_creates_dependency_on_dest`
- `test_move_file_creates_dependency_on_dest`

#### `TestPackageAndGitDependencies`

- `test_package_ops_are_sequential`
- `test_git_ops_are_sequential`
- `test_same_package_resource_conflict`

#### `TestNetworkAndServiceDependencies`

- `test_network_ops_same_url_create_dependency`
- `test_network_ops_different_urls_are_independent`
- `test_service_ops_same_service_create_dependency`
- `test_service_ops_different_services_are_independent`

#### `TestExecutionLevels`

- `test_independent_steps_share_a_level`
- `test_chained_steps_produce_sequential_levels`
- `test_all_nodes_included_in_levels`
- `test_cycle_handling_falls_back_to_sequential`

#### `TestIsParallelizable`

- `test_single_step_not_parallelizable`
- `test_independent_steps_are_parallelizable`
- `test_dependent_steps_are_not_parallelizable`

#### `TestEstimateSpeedup`

- `test_single_step_speedup_is_one`
- `test_fully_parallel_speedup_equals_step_count`
- `test_sequential_speedup_is_one`

#### `TestGetExecutionOrder`

- `test_returns_same_as_graph_levels`

#### `TestVisualize`

- `test_visualize_contains_total_steps`
- `test_visualize_marks_parallel_levels`
- `test_visualize_marks_sequential_levels`
- `test_visualize_includes_tool_and_action`

### [unit/test_error_handling.py](../tests/unit/test_error_handling.py) — 71 tests


#### `TestCircuitBreakerConfig`

- `test_defaults`
- `test_custom_values`

#### `TestCircuitBreakerInitialState`

- `test_initial_state_is_closed`
- `test_initial_stats`

#### `TestCircuitBreakerClosedState`

- `test_successful_call_passes_through`
- `test_successful_call_increments_totals`
- `test_failed_call_increments_failure_count`
- `test_success_resets_failure_count`
- `test_opens_after_threshold`
- `test_failure_rate_calculation`

#### `TestCircuitBreakerOpenState`

- `test_open_circuit_rejects_calls`
- `test_open_circuit_error_message`
- `test_total_requests_still_incremented_when_open`
- `test_transitions_to_half_open_after_timeout`

#### `TestCircuitBreakerHalfOpenState`

- `test_success_in_half_open_increments_success_count`
- `test_closes_after_success_threshold`
- `test_failure_in_half_open_reopens`
- `test_closed_circuit_resets_counters`

#### `TestCircuitBreakerReset`

- `test_reset_from_open`
- `test_reset_clears_failure_count`

#### `TestCircuitBreakerStats`

- `test_stats_zero_requests_failure_rate`
- `test_stats_last_failure_is_iso_string`
- `test_stats_last_success_is_iso_string`

#### `TestCircuitBreakerRegistry`

- `test_get_creates_new_instance`
- `test_get_returns_existing_instance`
- `test_reset_all_resets_each_breaker`

#### `TestFallbackOption`

- `test_creation`

#### `TestFallback`

- `test_no_options_raises`
- `test_first_option_succeeds`
- `test_falls_through_to_next_on_exception`
- `test_last_successful_option_is_tracked`
- `test_all_fail_raises_all_fallbacks_failed`
- `test_all_fallbacks_failed_message_contains_names`
- `test_priority_ordering`
- `test_options_sorted_after_add`
- `test_parallel_strategy_falls_back_to_cascade`
- `test_unknown_strategy_raises`
- `test_get_stats`
- `test_kwargs_passed_to_func`

#### `TestRuleBasedFallback`

- `test_list_keyword`
- `test_create_keyword`
- `test_delete_keyword`
- `test_move_keyword`
- `test_cpu_keyword`
- `test_git_keyword`
- `test_unknown_prompt_returns_generic`

#### `TestFallbackRegistry`

- `test_register_and_get`
- `test_get_creates_empty_fallback_for_unknown_name`
- `test_get_llm_creates_llm_fallback`

#### `TestRetryConfig`

- `test_defaults`

#### `TestRetryBudget`

- `test_initial_state`
- `test_can_retry_when_budget_available`
- `test_can_retry_false_when_exhausted`
- `test_consume_reduces_remaining`
- `test_consume_multiple_times`
- `test_get_usage_percentage`
- `test_window_reset_clears_usage`
- `test_get_remaining_never_negative`

#### `TestRetryWithBudget`

- `test_succeeds_on_first_attempt`
- `test_retries_on_failure_then_succeeds`
- `test_raises_retry_exhausted_after_all_attempts`
- `test_raises_budget_exceeded`
- `test_retry_only_on_specified_exception`
- `test_exponential_backoff_capped_at_max_delay`
- `test_no_sleep_after_last_attempt`
- `test_budget_consumed_per_retry`
- `test_default_config_and_budget_used_when_not_provided`

#### `TestRetryBudgetRegistry`

- `test_get_creates_new_budget`
- `test_get_returns_same_instance`
- `test_reset_all_clears_registry`
- `test_get_budget_stats_returns_dict`

### [unit/test_error_recovery.py](../tests/unit/test_error_recovery.py) — 42 tests


#### `TestRecoveryResult`

- `test_defaults`
- `test_all_fields`

#### `TestRecoveryStrategy`

- `test_strategy_values`

#### `TestErrorRecoveryInit`

- `test_defaults`
- `test_custom_params`
- `test_initial_stats_zero`

#### `TestRetryWithBackoff`

- `test_success_on_first_retry`
- `test_success_on_second_retry`
- `test_all_retries_fail`
- `test_backoff_sleep_called`
- `test_passes_args_and_kwargs`

#### `TestRequestPermission`

- `test_user_grants_permission`
- `test_user_skips`
- `test_user_aborts`
- `test_empty_input_aborts`

#### `TestHandleMissingResource`

- `test_user_skips`
- `test_empty_input_skips`
- `test_user_aborts`

#### `TestHandleMissingDependency`

- `test_skips_operation`
- `test_message_contains_module_name`

#### `TestHandleMissingKey`

- `test_continues_without_key`
- `test_message_contains_key_name`

#### `TestHandleRateLimit`

- `test_success_after_wait`
- `test_failure_after_wait`

#### `TestHandleUnknownError`

- `test_user_continues`
- `test_empty_input_continues`
- `test_user_aborts`

#### `TestRecoverDispatch`

- `test_timeout_error_dispatches_retry`
- `test_connection_error_dispatches_retry`
- `test_permission_error_dispatches_permission`
- `test_file_not_found_dispatches_missing_resource`
- `test_import_error_dispatches_missing_dependency`
- `test_module_not_found_dispatches_missing_dependency`
- `test_key_error_dispatches_missing_key`
- `test_rate_limit_string_dispatches_rate_limit`
- `test_unknown_error_dispatches_unknown`
- `test_recover_passes_args_to_operation`

#### `TestGetStats`

- `test_returns_copy`
- `test_stats_all_keys_present`
- `test_stats_accumulate`

#### `TestGetErrorRecovery`

- `test_returns_error_recovery_instance`
- `test_returns_same_instance`

### [unit/test_execution_modules.py](../tests/unit/test_execution_modules.py) — 64 tests


#### `TestCacheEntry`

- `test_not_expired_when_no_ttl`
- `test_not_expired_when_fresh`
- `test_expired_when_old`
- `test_to_dict_round_trip`

#### `TestSmartCacheBasics`

- `test_get_miss_returns_none`
- `test_set_and_get_returns_value`
- `test_get_expired_entry_returns_none`
- `test_stats_track_hits_and_misses`
- `test_hit_rate_calculation`
- `test_clear_resets_cache_and_stats`
- `test_invalidate_existing_key`
- `test_invalidate_missing_key`
- `test_invalidate_pattern_removes_matching`
- `test_max_entries_triggers_eviction`

#### `TestSmartCacheGetOrCompute`

- `test_computes_on_miss_and_caches_result`
- `test_returns_cached_value_on_hit`

#### `TestSmartCachePersistence`

- `test_persist_and_load`
- `test_expired_entries_not_loaded`

#### `TestComputeCacheKey`

- `test_same_args_produce_same_key`
- `test_different_args_produce_different_keys`
- `test_key_length_is_16`

#### `TestSmartCacheSingletons`

- `test_get_llm_cache_returns_smart_cache`
- `test_get_fs_cache_returns_smart_cache`

#### `TestCachedIntent`

- `test_not_expired_when_fresh`
- `test_expired_when_old`
- `test_to_dict_round_trip`

#### `TestIntentCache`

- `test_get_miss_returns_none`
- `test_set_and_get_returns_intent`
- `test_get_is_case_insensitive`
- `test_expired_entry_returns_none`
- `test_invalidate_removes_entry`
- `test_invalidate_missing_returns_false`
- `test_clear_removes_all_entries`
- `test_stats_tokens_saved_on_hit`
- `test_stats_hit_rate`
- `test_lru_eviction_on_max_entries`

#### `TestErrorCategory`

- `test_permission_pattern_matched`
- `test_not_found_pattern_matched`
- `test_network_pattern_matched`
- `test_timeout_pattern_matched`
- `test_unknown_error_maps_to_unknown`

#### `TestErrorHandlerMessages`

- `test_permission_message_mentions_path`
- `test_not_found_message_for_package_ops`
- `test_network_message`
- `test_unknown_message_contains_tool_and_action`

#### `TestErrorHandlerSuggestions`

- `test_permission_suggestions_mention_permissions`
- `test_not_found_suggestions_for_package`
- `test_network_suggestions_include_connectivity_check`

#### `TestErrorHandlerHandle`

- `test_handle_returns_enhanced_error`
- `test_enhanced_error_format_contains_message`
- `test_handle_accepts_context`

#### `TestGetErrorHandler`

- `test_singleton`

#### `TestResourceLimiter`

- `test_non_io_step_can_always_execute`
- `test_io_step_blocked_when_limit_reached`
- `test_io_step_allowed_below_limit`
- `test_acquire_and_release_io`
- `test_release_io_does_not_go_below_zero`

#### `TestParallelExecutorShouldUseParallel`

- `test_single_step_not_parallel`
- `test_sequential_steps_not_parallel`
- `test_independent_steps_are_parallel`

#### `TestParallelExecutorExecute`

- `test_empty_intent_returns_empty_list`
- `test_single_step_result_returned`
- `test_sequential_steps_all_results_returned`
- `test_get_parallel_executor_factory`

### [unit/test_explain.py](../tests/unit/test_explain.py) — 52 tests


#### `TestStepExplanation`

- `test_defaults`
- `test_all_fields`

#### `TestExecutionExplanationToDict`

- `test_to_dict_has_all_keys`
- `test_to_dict_intent_structure`
- `test_to_dict_step_explanations`
- `test_timestamp_auto_set`

#### `TestExplainModeGenerateReasoning`

- `test_single_step_says_simple`
- `test_multi_step_counts_steps`
- `test_all_read_only_steps`
- `test_modify_steps_noted`
- `test_danger_steps_noted`
- `test_tools_listed`

#### `TestExplainModeExplain`

- `test_explain_calls_print_explanation`
- `test_explain_with_semantic_search_high_success`
- `test_explain_with_semantic_search_low_success`
- `test_explain_no_similar_when_empty`

#### `TestExplainModeConfirm`

- `test_y_returns_true`
- `test_yes_returns_true`
- `test_n_returns_false`

#### `TestExplainer`

- `test_explain_intent_runs_without_error`
- `test_explain_intent_requires_confirmation`
- `test_explain_task_complexity_iterative`
- `test_explain_task_complexity_one_shot`
- `test_explain_iteration`
- `test_explain_context`
- `test_explain_context_no_git`
- `test_explain_context_weekend`
- `test_explain_context_git_with_ahead`
- `test_confirm_y_returns_true`
- `test_confirm_n_returns_false`
- `test_show_alternatives`
- `test_explain_steps_with_risk_levels`
- `test_explain_risks_all_levels`

#### `TestExplainabilityDashboard`

- `test_empty_history`
- `test_add_execution`
- `test_history_trimmed_at_max`
- `test_explain_last_empty`
- `test_explain_last_with_history`
- `test_explain_last_verbose`
- `test_explain_execution_by_index`
- `test_explain_execution_invalid_index`
- `test_explain_execution_empty_history`
- `test_show_history_empty`
- `test_show_history_with_entries`
- `test_display_step_confidence_colors`
- `test_display_step_with_result`
- `test_display_step_with_alternatives`
- `test_display_statistics`

#### `TestGetExplainer`

- `test_returns_explainer_instance`
- `test_returns_same_instance`

#### `TestGetExplainabilityDashboard`

- `test_returns_dashboard_instance`
- `test_returns_same_instance`

### [unit/test_failure_analyzer.py](../tests/unit/test_failure_analyzer.py) — 20 tests

- `test_categorize_permission_error`
- `test_categorize_file_not_found`
- `test_categorize_network_error`
- `test_categorize_unknown_error`
- `test_generate_suggestions_permission`
- `test_generate_suggestions_file_not_found`
- `test_analyze_failure_logs_to_database`
- `test_analyze_before_execution_no_history`
- `test_analyze_before_execution_with_history`
- `test_get_success_probability_no_failures`
- `test_get_success_probability_some_failures`
- `test_get_success_probability_many_failures`
- `test_should_retry_permission_error`
- `test_should_retry_network_error`
- `test_should_retry_unknown_error_once`
- `test_generate_recovery_plan_permission`
- `test_generate_recovery_plan_file_not_found`
- `test_tool_specific_suggestions_browser`
- `test_tool_specific_suggestions_package`
- `test_recurring_failure_detection`

### [unit/test_failure_logger.py](../tests/unit/test_failure_logger.py) — 11 tests

- `test_logger_initialization`
- `test_log_simple_failure`
- `test_log_failure_with_context`
- `test_get_similar_failures`
- `test_pattern_tracking`
- `test_normalize_error`
- `test_get_failure_stats`
- `test_pattern_suggestions`
- `test_failure_with_resolution`
- `test_recent_failures_only`
- `test_multiple_patterns_same_tool`

### [unit/test_feedback_collector.py](../tests/unit/test_feedback_collector.py) — 45 tests


#### `TestFeedbackEntry`

- `test_to_dict_contains_all_fields`
- `test_to_dict_with_comment`

#### `TestFeedbackCollectorInit`

- `test_creates_feedback_dir`
- `test_enable_prompts_default`
- `test_env_var_disables_prompts`
- `test_env_var_0_disables_prompts`
- `test_prompt_frequency`

#### `TestCollectDisabled`

- `test_returns_none_when_disabled`

#### `TestCollectSampling`

- `test_skips_when_random_above_frequency`
- `test_prompts_when_random_below_frequency`

#### `TestCollectDeduplication`

- `test_does_not_ask_twice_same_session`
- `test_already_has_feedback_from_file`

#### `TestCollectResponses`

- `test_positive_feedback`
- `test_yes_full_word_feedback`
- `test_negative_without_comment`
- `test_negative_with_comment`
- `test_skip_response`
- `test_keyboard_interrupt_returns_none`
- `test_eof_error_returns_none`

#### `TestRecordFeedback`

- `test_writes_jsonl_file`
- `test_appends_multiple_entries`
- `test_truncates_long_input`
- `test_intent_with_no_steps_uses_unknown_tool`
- `test_invalidates_stats_cache`

#### `TestGetStats`

- `test_empty_file_returns_zeros`
- `test_missing_file_returns_zeros`
- `test_counts_feedback_types`
- `test_stats_by_tool`
- `test_stats_positive_rate`
- `test_stats_cached`
- `test_stats_by_success`

#### `TestExportTrainingData`

- `test_returns_path_when_no_file`
- `test_exports_positive_only_by_default`
- `test_exports_with_negative_included`
- `test_exported_format`

#### `TestSanitizeText`

- `test_redacts_password`
- `test_redacts_token`
- `test_redacts_email`
- `test_safe_text_unchanged`

#### `TestAlreadyHasFeedback`

- `test_false_when_no_file`
- `test_true_for_exact_match`
- `test_false_for_different_command`
- `test_true_for_substring_match_long_cmd`

#### `TestGetFeedbackCollector`

- `test_returns_feedback_collector_instance`
- `test_returns_same_instance`

### [unit/test_file_ops.py](../tests/unit/test_file_ops.py) — 9 tests


#### `TestFileOps`

- `test_scan_directory`
- `test_mkdir_creates_directory`
- `test_mkdir_creates_nested_directories`
- `test_mkdir_idempotent`
- `test_move_file`
- `test_write_file_creates_file`
- `test_write_file_creates_parent_dirs`
- `test_touch_creates_empty_file`
- `test_touch_creates_parent_dirs`

### [unit/test_git_ops_unit.py](../tests/unit/test_git_ops_unit.py) — 56 tests


#### `TestRunGit`

- `test_returns_stdout_on_success`
- `test_returns_error_on_nonzero`
- `test_exception_returns_error`
- `test_expands_tilde_in_cwd`
- `test_git_is_first_arg`

#### `TestGitBasicOps`

- `test_clone_passes_url`
- `test_clone_with_directory`
- `test_status_calls_git_status`
- `test_add_single_file`
- `test_add_list_of_files`
- `test_add_dot_stages_all`
- `test_commit_includes_message`

#### `TestGitPushPull`

- `test_push_default_remote`
- `test_push_with_branch`
- `test_pull_default_remote`
- `test_pull_with_branch`
- `test_push_error_propagated`

#### `TestGitBranchCheckout`

- `test_branch_list_no_name`
- `test_branch_create`
- `test_branch_delete`
- `test_branch_create_error_returned`
- `test_checkout_existing`
- `test_checkout_create_adds_b_flag`
- `test_checkout_error_returned_as_is`

#### `TestGitHistoryOps`

- `test_log_default_limit_10`
- `test_log_custom_limit`
- `test_log_uses_oneline`
- `test_diff_no_file`
- `test_diff_with_file`
- `test_stash_push`
- `test_stash_pop`
- `test_remote_show_uses_v`
- `test_remote_non_show_action_included`

#### `TestGitHubToken`

- `test_reads_github_token_env`
- `test_reads_gh_token_env`
- `test_returns_none_when_no_token`

#### `TestGitHubRequest`

- `test_returns_error_when_no_token`
- `test_get_returns_json`
- `test_204_returns_success`
- `test_http_error_returns_error_dict`
- `test_generic_exception_returns_error_dict`

#### `TestGitHubIssues`

- `test_create_issue_returns_url`
- `test_create_issue_propagates_error`
- `test_list_issues_formats_output`
- `test_list_issues_empty_returns_message`
- `test_list_issues_api_error`
- `test_list_issues_unexpected_response`
- `test_close_issue_success`
- `test_close_issue_with_comment_posts_comment_first`
- `test_close_issue_error`

#### `TestCreateIssuesFromRoadmap`

- `test_returns_error_when_roadmap_not_found`
- `test_dry_run_shows_preview`
- `test_phase_filter_excludes_other_phases`
- `test_no_unchecked_items_returns_message`
- `test_live_run_creates_issues`
- `test_live_run_handles_partial_errors`

### [unit/test_goal_inference.py](../tests/unit/test_goal_inference.py) — 61 tests


#### `TestGoalTypeDetection`

- `test_detects_deploy`
- `test_detects_deploy_via_release`
- `test_detects_develop`
- `test_detects_debug`
- `test_detects_debug_via_fix`
- `test_detects_migrate`
- `test_detects_backup`
- `test_detects_monitor`
- `test_detects_optimize`
- `test_detects_security`
- `test_detects_test`
- `test_detects_setup`
- `test_detects_cleanup`
- `test_returns_unknown_for_unrecognized_input`
- `test_case_insensitive_detection`

#### `TestExplicitStepExtraction`

- `test_extracts_known_action_words`
- `test_returns_default_when_no_actions_found`
- `test_does_not_duplicate_steps`

#### `TestImplicitStepInsertion`

- `test_deploy_adds_critical_before_steps`
- `test_deploy_adds_health_check_after`
- `test_develop_checks_system_requirements`
- `test_migrate_adds_backup_before`
- `test_migrate_adds_dry_run_before`
- `test_security_adds_audit_before`
- `test_cleanup_adds_preview_and_confirm`
- `test_database_keyword_adds_db_backup`
- `test_delete_keyword_adds_trash_step`
- `test_unknown_goal_returns_empty_or_minimal`
- `test_implicit_steps_have_valid_importance_levels`

#### `TestCompleteWorkflowBuilding`

- `test_critical_before_steps_come_first`
- `test_after_steps_come_last`
- `test_during_steps_are_recommended`
- `test_explicit_steps_preserved`

#### `TestReasoningAndMetadata`

- `test_reasoning_mentions_goal_type`
- `test_reasoning_mentions_critical_count`
- `test_estimate_time_short_workflow`
- `test_estimate_time_medium_workflow`
- `test_estimate_time_long_workflow`
- `test_estimate_time_very_long_workflow`
- `test_risk_high_when_no_safety_steps`
- `test_risk_medium_with_safety_steps`
- `test_risk_low_for_non_destructive_goals`
- `test_deploy_prerequisites`
- `test_develop_prerequisites`
- `test_unknown_goal_has_empty_prerequisites`
- `test_deploy_post_actions`
- `test_security_post_actions`
- `test_unknown_goal_returns_empty_post_actions`

#### `TestInferGoal`

- `test_infer_goal_returns_workflow_suggestion`
- `test_infer_goal_detects_correct_type`
- `test_infer_goal_includes_implicit_steps`
- `test_infer_goal_builds_complete_workflow`
- `test_infer_goal_logs_info`
- `test_infer_goal_goal_description_truncated`
- `test_workflow_suggestion_to_dict`

#### `TestPatternPersistence`

- `test_initializes_common_patterns_when_file_absent`
- `test_save_and_reload_patterns`
- `test_load_patterns_returns_empty_on_missing_file`
- `test_load_patterns_handles_corrupt_file`

#### `TestGetGoalInference`

- `test_get_goal_inference_returns_instance`
- `test_get_goal_inference_returns_same_instance`

### [unit/test_goal_tracker.py](../tests/unit/test_goal_tracker.py) — 7 tests

- `test_goal_tracker_initialization`
- `test_goal_tracker_iteration_limit`
- `test_goal_tracker_reset`
- `test_goal_status_representation`
- `test_build_reflection_prompt`
- `test_parse_reflection`
- `test_observation_accumulation`

### [unit/test_intent_history.py](../tests/unit/test_intent_history.py) — 37 tests


#### `TestIntentHistoryInit`

- `test_creates_history_dir`
- `test_current_file_is_daily`
- `test_current_file_is_jsonl`

#### `TestRecord`

- `test_record_creates_file`
- `test_record_appends_valid_json_line`
- `test_record_stores_user_input`
- `test_record_stores_success_true`
- `test_record_stores_success_false`
- `test_record_stores_results`
- `test_record_stores_steps_count`
- `test_record_intent_without_goal_attribute`
- `test_record_intent_without_steps_attribute`
- `test_record_multiple_entries_appended`
- `test_record_has_timestamp`

#### `TestGetRecent`

- `test_get_recent_empty_when_no_file`
- `test_get_recent_returns_all_when_fewer_than_limit`
- `test_get_recent_respects_limit`
- `test_get_recent_returns_most_recent`

#### `TestSearch`

- `test_search_matches_user_input`
- `test_search_matches_goal`
- `test_search_is_case_insensitive`
- `test_search_returns_empty_for_no_match`
- `test_search_respects_limit`
- `test_search_across_multiple_files`
- `test_search_no_files_returns_empty`

#### `TestGetSuccessRate`

- `test_success_rate_no_files`
- `test_success_rate_all_success`
- `test_success_rate_all_failure`
- `test_success_rate_mixed`

#### `TestGetPopularGoals`

- `test_popular_goals_empty_dir`
- `test_popular_goals_sorted_by_count`
- `test_popular_goals_respects_limit`
- `test_popular_goals_entry_structure`

#### `TestAnalyzeFailures`

- `test_analyze_failures_empty_dir`
- `test_analyze_failures_returns_only_failures`
- `test_analyze_failures_respects_limit`
- `test_analyze_failures_no_failures`

### [unit/test_iterative_execution.py](../tests/unit/test_iterative_execution.py) — 15 tests


#### `TestExecuteIterativeBasic`

- `test_goal_achieved_first_iteration_returns_success`
- `test_goal_achieved_returns_string`
- `test_execution_exception_returns_error_string`
- `test_max_iterations_hit_returns_descriptive_message`
- `test_llm_exception_in_iteration_returns_error`

#### `TestIterativeMemoryUpdates`

- `test_session_memory_updated_each_iteration`

#### `TestIterativeDryRun`

- `test_dry_run_does_not_call_execute_plan`

#### `TestGoalStatus`

- `test_goal_status_achieved_true`
- `test_goal_status_achieved_false`
- `test_goal_status_defaults_next_steps_to_empty`
- `test_goal_status_repr_achieved`
- `test_goal_status_repr_in_progress`

#### `TestGoalTrackerIterationLimit`

- `test_max_iterations_returns_not_achieved`
- `test_empty_observations_returns_not_achieved`
- `test_llm_exception_falls_back_gracefully`

### [unit/test_llm_layer.py](../tests/unit/test_llm_layer.py) — 64 tests


#### `TestBuildSystemPrompt`

- `test_contains_base_content`
- `test_includes_privileged_tools_by_default`
- `test_excludes_privileged_when_flag_is_false`
- `test_returns_string`
- `test_fallback_static_list_when_registry_unavailable`
- `test_base_string_present`

#### `TestGetLLM`

- `test_creates_anthropic_llm`
- `test_creates_openai_llm`
- `test_creates_deepseek_llm`
- `test_creates_ollama_llm`
- `test_force_provider_overrides_config`
- `test_raises_for_unknown_provider`
- `test_raises_when_no_provider_configured`
- `test_raises_when_api_key_missing`
- `test_get_available_providers_with_keys`
- `test_get_available_providers_fallback_to_anthropic`

#### `TestExtractJson`

- `test_plain_json`
- `test_json_in_code_fence`
- `test_json_in_plain_fence`
- `test_json_with_surrounding_text`
- `test_no_json_raises`
- `test_invalid_json_raises`

#### `TestAnthropicLLM`

- `test_raises_without_api_key`
- `test_strips_quotes_from_api_key`
- `test_translate_intent_returns_intent_ir`
- `test_translate_intent_calls_create_with_system_prompt`
- `test_translate_intent_invalid_json_raises`
- `test_reflect_on_goal_non_streaming`
- `test_reflect_on_goal_calls_create`
- `test_generate_returns_text`
- `test_generate_calls_create_with_prompt`
- `test_analyze_image_returns_text`
- `test_analyze_image_returns_error_string_on_exception`
- `test_translate_intent_streaming`

#### `TestOpenAILLM`

- `test_raises_without_api_key`
- `test_translate_intent_returns_intent_ir`
- `test_translate_intent_calls_parse_with_system_prompt`
- `test_reflect_on_goal_non_streaming`
- `test_generate_returns_content`
- `test_generate_uses_correct_model`
- `test_analyze_image_success`
- `test_analyze_image_error_returns_string`

#### `TestDeepSeekLLM`

- `test_raises_without_api_key`
- `test_uses_deepseek_base_url_by_default`
- `test_translate_intent_returns_intent_ir`
- `test_translate_intent_invalid_json_raises`
- `test_reflect_on_goal_non_streaming`
- `test_generate_returns_content`
- `test_strips_quotes_from_api_key`

#### `TestOllamaLLM`

- `test_raises_when_ollama_not_running`
- `test_raises_when_ollama_non_200`
- `test_translate_intent_returns_intent_ir`
- `test_translate_intent_non_200_raises`
- `test_translate_intent_timeout_raises`
- `test_translate_intent_invalid_json_raises`
- `test_reflect_on_goal_non_streaming`
- `test_reflect_on_goal_non_200_raises`
- `test_reflect_on_goal_timeout_raises`
- `test_generate_returns_response`
- `test_generate_non_200_raises`
- `test_extract_json_strips_code_fence`
- `test_extract_json_plain`
- `test_model_attribute_set`
- `test_base_url_attribute_set`

### [unit/test_model_router.py](../tests/unit/test_model_router.py) — 32 tests


#### `TestModelRouterRouting`

- `test_route_returns_recommended_model_when_available`
- `test_route_falls_back_to_primary_when_recommended_unavailable`
- `test_route_uses_first_available_when_primary_also_missing`
- `test_route_uses_primary_when_no_models_available`
- `test_force_model_overrides_routing`
- `test_route_logs_decision_when_enabled`
- `test_route_skips_logging_when_disabled`
- `test_route_increments_session_command_count`
- `test_user_input_truncated_to_100_chars_in_decision`

#### `TestFallbackCascade`

- `test_execute_with_fallback_succeeds_on_first_try`
- `test_execute_with_fallback_uses_next_model_on_failure`
- `test_execute_with_fallback_marks_fallback_used_in_decision`
- `test_execute_with_fallback_raises_when_all_fail`
- `test_execute_with_fallback_sets_env_var`

#### `TestBuildFallbackChain`

- `test_chain_is_primary_only_when_fallback_disabled`
- `test_chain_only_primary_when_one_model_available`
- `test_chain_escalates_to_more_powerful_models`
- `test_chain_respects_max_fallbacks`
- `test_chain_uses_most_powerful_when_primary_unavailable`

#### `TestTokenTracking`

- `test_track_tokens_updates_session_stats`
- `test_track_tokens_estimates_cost`
- `test_track_tokens_ollama_is_free`
- `test_track_tokens_accumulates_across_calls`
- `test_track_tokens_creates_model_entry_if_absent`
- `test_unknown_model_cost_defaults_to_zero`

#### `TestStatsHelpers`

- `test_get_stats_returns_session_and_all_time`
- `test_load_stats_returns_defaults_when_file_missing`
- `test_load_stats_returns_defaults_on_corrupt_file`
- `test_update_stats_increments_successes`
- `test_update_stats_increments_failures`
- `test_update_stats_computes_average_latency`

#### `TestGetRouter`

- `test_get_router_returns_model_router_instance`

### [unit/test_monitoring_audit.py](../tests/unit/test_monitoring_audit.py) — 88 tests


#### `TestAuditLoggerInit`

- `test_creates_log_dir`
- `test_session_file_created`
- `test_default_log_dir`

#### `TestAuditLoggerWrite`

- `test_log_error_writes_entry`
- `test_log_error_contains_message`
- `test_log_error_empty_context`
- `test_log_info_writes_entry`
- `test_log_info_no_data`
- `test_log_execution_start`
- `test_log_execution_end_success`
- `test_log_execution_end_failure`
- `test_log_step_result_success`
- `test_log_step_result_failure`
- `test_log_intent_writes_entry`
- `test_entries_have_timestamps`

#### `TestGetLogger`

- `test_returns_audit_logger_instance`

#### `TestMetricPoint`

- `test_to_dict_contains_all_fields`

#### `TestMetricsCollectorInit`

- `test_buffer_starts_empty`
- `test_aggregates_start_at_zero`

#### `TestMetricsCollectorRecord`

- `test_record_adds_to_buffer`
- `test_record_metric_name_stored`
- `test_record_with_tags`
- `test_record_updates_latency_aggregate`
- `test_record_updates_token_aggregate`
- `test_record_updates_cost_aggregate`
- `test_record_cache_hit_increments_hits`
- `test_record_cache_miss_increments_misses`
- `test_record_success_increments_successes`
- `test_record_failure_increments_failures`

#### `TestMetricsCollectorRecordCommand`

- `test_records_latency`
- `test_records_tokens_when_nonzero`
- `test_skips_tokens_when_zero`
- `test_records_cost_when_nonzero`
- `test_cache_hit_recorded`
- `test_success_recorded`
- `test_failure_recorded`

#### `TestMetricsCollectorGetStats`

- `test_stats_empty_collector`
- `test_stats_after_commands`
- `test_avg_latency_computed`
- `test_success_rate_computed`
- `test_cache_hit_rate_computed`
- `test_by_model_stats`

#### `TestMetricsCollectorFlush`

- `test_flush_writes_to_disk`
- `test_flush_clears_buffer`
- `test_flush_empty_buffer_noop`
- `test_auto_flush_on_full_buffer`

#### `TestMetricsCollectorQuery`

- `test_query_all_returns_all`
- `test_query_by_metric_name`
- `test_query_by_tags`
- `test_query_missing_file_returns_empty`
- `test_query_limit_respected`

#### `TestGetMetricsCollector`

- `test_returns_metrics_collector_instance`

#### `TestHealthCheck`

- `test_to_dict_round_trips`

#### `TestAlert`

- `test_to_dict_converts_level_to_value`

#### `TestMonitoringSession`

- `test_to_dict_converts_status_to_value`

#### `TestHealthChecker`

- `test_check_disk_space_healthy`
- `test_check_disk_space_warning`
- `test_check_disk_space_critical`
- `test_check_disk_space_exception`
- `test_check_memory_healthy`
- `test_check_service_active`
- `test_check_service_inactive`
- `test_check_log_size_missing_path`

#### `TestRemediator`

- `test_remediate_success`
- `test_remediate_failure`
- `test_remediate_exception`
- `test_remediate_with_orchestrator`

#### `TestProactiveMonitorInit`

- `test_initializes_default_checks`
- `test_storage_dir_created`
- `test_current_session_none_initially`

#### `TestProactiveMonitorStartMonitoring`

- `test_returns_monitoring_session`
- `test_session_status_healthy`
- `test_session_stored_on_instance`

#### `TestProactiveMonitorAddRemove`

- `test_add_health_check`
- `test_remove_health_check`

#### `TestProactiveMonitorShouldRun`

- `test_runs_when_never_checked`
- `test_does_not_run_before_interval`
- `test_runs_after_interval_elapsed`

#### `TestProactiveMonitorCreateAlert`

- `test_creates_warning_alert`
- `test_creates_critical_alert`
- `test_alert_source_is_check_name`

#### `TestProactiveMonitorGetStatus`

- `test_status_has_expected_keys`
- `test_status_session_none_before_start`
- `test_status_health_checks_count`

#### `TestProactiveMonitorIsRecent`

- `test_now_is_recent`
- `test_old_timestamp_not_recent`
- `test_invalid_timestamp_returns_false`

#### `TestGetProactiveMonitor`

- `test_returns_proactive_monitor_instance`

### [unit/test_multi_agent.py](../tests/unit/test_multi_agent.py) — 56 tests


#### `TestAgentRoles`

- `test_researcher_role_value`
- `test_planner_role_value`
- `test_executor_role_value`
- `test_validator_role_value`
- `test_coordinator_role_value`

#### `TestMessageCreation`

- `test_message_appended_to_session`
- `test_message_has_correct_from_agent`
- `test_message_has_correct_to_agent`
- `test_messages_sent_counter_incremented`
- `test_message_id_is_string`
- `test_message_to_dict_has_string_roles`

#### `TestResearcherAgent`

- `test_execute_returns_agent_result`
- `test_execute_success_on_valid_response`
- `test_execute_confidence_from_response`
- `test_execute_agent_role_is_researcher`
- `test_execute_failure_on_llm_error`
- `test_execute_failure_on_invalid_json`
- `test_prompt_contains_task`
- `test_result_duration_is_non_negative`

#### `TestPlannerAgent`

- `test_execute_returns_agent_result`
- `test_execute_success_on_valid_response`
- `test_execute_agent_role_is_planner`
- `test_prompt_includes_research_context`
- `test_execute_failure_on_llm_error`

#### `TestExecutorAgent`

- `test_execute_returns_agent_result`
- `test_execute_agent_role_is_executor`
- `test_execute_calls_orchestrator_per_step`
- `test_execute_success_when_all_steps_pass`
- `test_execute_failure_when_step_raises`
- `test_stops_on_high_risk_failure`
- `test_execute_no_steps_returns_success`
- `test_result_contains_step_results`

#### `TestValidatorAgent`

- `test_execute_returns_agent_result`
- `test_execute_agent_role_is_validator`
- `test_success_reflects_llm_overall_success`
- `test_execute_failure_on_llm_error`
- `test_prompt_contains_task`
- `test_prompt_includes_plan_context`

#### `TestMultiAgentSystemCollaboration`

- `test_collaborate_returns_session`
- `test_collaboration_runs_all_phases`
- `test_session_success_on_all_agents_pass`
- `test_research_output_propagated_to_planner`
- `test_plan_output_propagated_to_validator`
- `test_stops_on_researcher_failure`
- `test_stops_on_planner_failure`
- `test_session_contains_all_results`
- `test_session_agents_involved_populated`
- `test_session_duration_is_non_negative`
- `test_session_has_unique_id`
- `test_exception_during_collaboration_returns_failed_session`
- `test_executor_runs_when_present`
- `test_stops_on_executor_failure`

#### `TestCollaborationSessionToDict`

- `test_agents_involved_serialized_as_strings`

#### `TestAgentResultToDict`

- `test_agent_role_serialized_as_string`

#### `TestGetMultiAgentSystem`

- `test_returns_instance`
- `test_returns_same_singleton`

### [unit/test_orchestrator.py](../tests/unit/test_orchestrator.py) — 46 tests


#### `TestExceptions`

- `test_intent_translation_error_is_exception`
- `test_orchestrator_error_is_exception`

#### `TestOrchestratorInit`

- `test_default_privilege_tier`
- `test_adaptive_false_sets_no_planner`
- `test_adaptive_true_sandbox_creates_sandboxed_planner`
- `test_adaptive_true_no_sandbox_creates_basic_planner`
- `test_use_memory_false_no_session_memory`
- `test_use_memory_true_creates_memory`
- `test_show_progress_false_no_progress`
- `test_enable_parallel_false_no_executor`
- `test_visualization_disabled_no_visualizer`
- `test_flags_stored`

#### `TestFormatDryRun`

- `test_contains_goal`
- `test_contains_dry_run_marker`
- `test_lists_all_steps`
- `test_includes_risk_level`
- `test_empty_steps`

#### `TestVisualizeResult`

- `test_disabled_returns_str_data`
- `test_no_visualizer_returns_str_data`
- `test_visualizer_called_with_title`
- `test_visualizer_exception_returns_str_data`

#### `TestRunHealthCheck`

- `test_disabled_returns_disabled_status`
- `test_enabled_no_alerts`
- `test_enabled_with_alerts`
- `test_enabled_with_auto_remediated_alert`
- `test_exception_returns_error_status`

#### `TestExecuteWithMultiAgent`

- `test_disabled_returns_not_enabled_message`
- `test_success_returns_final_result`
- `test_failure_returns_error_message`
- `test_exception_returns_error_string`

#### `TestBuildContext`

- `test_no_memory_no_env_empty_string`
- `test_env_context_included`
- `test_with_memory_calls_session_summary`
- `test_file_keyword_triggers_frequent_paths`
- `test_non_file_keyword_skips_frequent_paths`

#### `TestExecuteCommandDryRun`

- `test_dry_run_returns_dry_run_string`

#### `TestExecuteCommandIntentError`

- `test_llm_exception_returns_error_string`

#### `TestExecuteCommandCache`

- `test_cache_hit_skips_llm`

#### `TestExecuteCommandSuccess`

- `test_success_returns_string`
- `test_success_logs_intent`
- `test_action_tracker_transaction_completed`

#### `TestExecuteCommandFailure`

- `test_execution_exception_returns_error_message`
- `test_execution_failure_ends_transaction_as_failed`

#### `TestExecuteCommandIterativeDetection`

- `test_complex_task_delegates_to_execute_iterative`
- `test_force_oneshot_skips_iterative_detection`

#### `TestExecuteCommandAdaptive`

- `test_adaptive_planner_used_when_enabled`

### [unit/test_output.py](../tests/unit/test_output.py) — 73 tests


#### `TestOutputFormatterDetection`

- `test_looks_like_json_object`
- `test_looks_like_json_array`
- `test_not_json`
- `test_looks_like_table_with_pipe`
- `test_not_table_single_line`
- `test_looks_like_code_python`
- `test_looks_like_code_import`
- `test_not_code`

#### `TestOutputFormatterLanguageDetection`

- `test_detects_python`
- `test_detects_javascript`
- `test_detects_php`
- `test_detects_bash`
- `test_fallback_text`

#### `TestOutputFormatterSimpleDict`

- `test_is_simple_dict_no_nesting`
- `test_is_not_simple_dict_with_nested_dict`
- `test_is_not_simple_dict_with_list`

#### `TestOutputFormatterFormat`

- `test_format_empty_list_returns_empty_message`
- `test_format_list_of_dicts_returns_table_string`
- `test_format_simple_dict_returns_table_string`
- `test_format_int_falls_through_to_str`
- `test_format_list_of_scalars_returns_bullets`
- `test_format_string_json_returns_json_dump`

#### `TestOutputFormatterDelimiterDetection`

- `test_detect_delimiter_pipe`
- `test_detect_delimiter_comma`

#### `TestGetFormatter`

- `test_singleton_is_returned`
- `test_format_output_convenience`

#### `TestConsolePrintHelpers`

- `test_print_success_uses_green_style`
- `test_print_error_uses_red_style`
- `test_print_warning_uses_yellow_style`
- `test_print_info_uses_cyan_style`
- `test_print_goal_contains_goal_text`
- `test_print_divider_calls_print`
- `test_print_header_calls_print`
- `test_print_step_risk_read_prints_label`
- `test_print_similar_commands_empty_does_nothing`
- `test_print_plan_summary_calls_print_once`

#### `TestProgressTracker`

- `test_start_timer_and_stop_returns_positive_elapsed`
- `test_stop_unknown_timer_returns_zero`
- `test_get_elapsed_unknown_returns_zero`
- `test_get_elapsed_running_timer`
- `test_stop_timer_removes_entry`

#### `TestStreamingDisplay`

- `test_start_sets_start_time`
- `test_new_iteration_updates_current_iteration`
- `test_complete_step_success_calls_print`
- `test_complete_step_truncates_long_result`
- `test_finish_calls_print`
- `test_batch_complete_calls_print`

#### `TestProgressIndicatorAlias`

- `test_alias_points_to_tracker`

#### `TestGetProgressSingletons`

- `test_get_progress_tracker_returns_singleton`
- `test_get_streaming_display_returns_singleton`

#### `TestStreamHandler`

- `test_initial_cancelled_is_false`
- `test_cancel_sets_flag`
- `test_cancel_invokes_callbacks`
- `test_cancel_callback_exception_does_not_propagate`
- `test_register_multiple_callbacks`
- `test_stream_llm_tokens_returns_complete_text`
- `test_stream_llm_tokens_stops_on_cancel`
- `test_show_progress_returns_progress_and_task_id`
- `test_get_stream_handler_returns_global`

#### `TestCancelableOperation`

- `test_context_manager_restores_sigint`

#### `TestConsolePrintHelpersExtended`

- `test_print_step_with_result_simple`
- `test_print_step_with_multiline_result`
- `test_print_step_with_json_result`
- `test_print_step_visualization_fallback`
- `test_print_similar_commands_with_data`
- `test_print_explanation_with_reasoning`
- `test_print_explanation_without_reasoning`
- `test_print_explanation_all_risk_levels`
- `test_print_code_block_calls_print`
- `test_print_json_calls_print`
- `test_print_status_table_with_data`
- `test_print_status_table_empty`
- `test_print_step_risk_variants`

### [unit/test_parallel_executor.py](../tests/unit/test_parallel_executor.py) — 36 tests


#### `TestStepExecutionResult`

- `test_defaults`
- `test_all_fields`

#### `TestParallelExecutorInit`

- `test_default_workers`
- `test_custom_workers`
- `test_default_timeout`

#### `TestParallelExecutorExecuteBasic`

- `test_empty_intent_returns_empty`
- `test_single_step_calls_func_once`

#### `TestParallelExecutorSequential`

- `test_all_sequential_executes_in_order`
- `test_sequential_fast_path_propagates_error`

#### `TestParallelExecutorParallel`

- `test_parallel_level_executes_multiple`
- `test_parallel_error_handled_gracefully`

#### `TestExecuteStepSafe`

- `test_success_returns_result`
- `test_exception_re_raised`
- `test_logs_completion`
- `test_logs_error_on_failure`

#### `TestShouldUseParallel`

- `test_single_step_returns_false`
- `test_not_parallelizable_returns_false`
- `test_low_speedup_returns_false`
- `test_high_speedup_returns_true`

#### `TestVisualizeExecutionPlan`

- `test_delegates_to_analyzer`

#### `TestResourceLimiter`

- `test_defaults`
- `test_custom_params`
- `test_can_execute_non_io_step`
- `test_can_execute_io_step_within_limit`
- `test_cannot_execute_io_step_at_limit`
- `test_acquire_io_increments`
- `test_release_io_decrements`
- `test_release_io_does_not_go_below_zero`
- `test_io_intensive_file_ops`
- `test_io_intensive_network_ops`
- `test_io_intensive_browser_ops`
- `test_not_io_intensive_shell_ops`
- `test_not_io_intensive_unknown_tool`

#### `TestGetParallelExecutor`

- `test_default_workers`
- `test_custom_workers`
- `test_returns_parallel_executor_instance`

### [unit/test_pattern_detector.py](../tests/unit/test_pattern_detector.py) — 49 tests


#### `TestDetectPatternsGeneral`

- `test_empty_history_returns_empty_list`
- `test_below_min_occurrences_returns_empty`
- `test_results_sorted_by_confidence_descending`
- `test_records_outside_lookback_are_excluded`
- `test_invalid_timestamps_are_skipped`

#### `TestDetectRecurringCommands`

- `test_daily_pattern_detected`
- `test_weekly_pattern_detected`
- `test_monthly_pattern_detected`
- `test_recurring_pattern_has_cron_expression`
- `test_irregular_intervals_no_frequency`
- `test_fewer_than_min_occurrences_not_detected`
- `test_confidence_increases_with_occurrences`
- `test_pattern_type_is_recurring`

#### `TestDetectWorkflows`

- `test_workflow_detected_for_repeated_sequence`
- `test_single_session_no_repeated_workflow`
- `test_large_time_gap_breaks_sequence`
- `test_workflow_pattern_type_label`

#### `TestDetectTimePatterns`

- `test_commands_at_same_hour_detected`
- `test_time_pattern_description_includes_hour`
- `test_commands_at_random_hours_no_time_pattern`

#### `TestDetectPreferences`

- `test_dominant_tool_detected_as_preference`
- `test_no_intent_steps_no_preference`

#### `TestNormalizeCommand`

- `test_paths_replaced_with_placeholder`
- `test_numbers_replaced_with_placeholder`
- `test_lowercased`
- `test_whitespace_stripped`

#### `TestDetectFrequency`

- `test_single_timestamp_returns_none`
- `test_daily_interval_returns_daily`
- `test_weekly_interval_returns_weekly`
- `test_monthly_interval_returns_monthly`
- `test_unclassifiable_interval_returns_none`
- `test_daily_cron_expression_format`

#### `TestParseTimestamp`

- `test_valid_iso_timestamp`
- `test_timestamp_with_z_suffix`
- `test_empty_string_returns_none`
- `test_invalid_format_returns_none`

#### `TestGetPatternDetectorSingleton`

- `test_returns_pattern_detector_instance`
- `test_returns_same_instance_on_repeated_calls`

#### `TestPatternMemory`

- `test_new_pattern_not_suggested`
- `test_mark_suggested_persists`
- `test_clear_removes_all_entries`
- `test_persistence_across_instances`
- `test_missing_file_loads_empty_set`
- `test_corrupt_file_loads_empty_set`
- `test_clear_persists_empty_state`
- `test_multiple_marks_do_not_duplicate`
- `test_save_failure_is_silent`

#### `TestGetPatternMemorySingleton`

- `test_returns_pattern_memory_instance`
- `test_returns_same_instance_on_repeated_calls`

### [unit/test_planner.py](../tests/unit/test_planner.py) — 14 tests


#### `TestPlanner`

- `test_executes_simple_plan`
- `test_executes_multi_step_plan`
- `test_stops_on_safety_error`
- `test_raises_on_missing_tool`
- `test_raises_on_missing_action`
- `test_logs_steps_when_logger_provided`
- `test_parallel_false_skips_parallel_executor`
- `test_logs_missing_tool_error`
- `test_logs_missing_action_error`
- `test_privilege_check_raises_for_restricted_tier`
- `test_privilege_check_allows_privileged_tier`
- `test_error_recovery_on_tool_exception`
- `test_error_recovery_failure_raises`
- `test_returns_list_of_string_results`

### [unit/test_privilege.py](../tests/unit/test_privilege.py) — 21 tests


#### `TestPrivilegeTierValues`

- `test_restricted_value`
- `test_standard_value`
- `test_privileged_value`
- `test_tier_is_str_subclass`
- `test_all_three_tiers_exist`

#### `TestPrivilegedToolsSet`

- `test_shell_ops_is_privileged`
- `test_code_exec_is_privileged`
- `test_file_ops_is_not_privileged`
- `test_system_ops_is_not_privileged`

#### `TestCheckPrivilege`

- `test_shell_ops_allowed_at_privileged`
- `test_code_exec_allowed_at_privileged`
- `test_shell_ops_blocked_at_standard`
- `test_code_exec_blocked_at_standard`
- `test_shell_ops_blocked_at_restricted`
- `test_code_exec_blocked_at_restricted`
- `test_file_ops_allowed_at_standard`
- `test_file_ops_allowed_at_restricted`
- `test_network_ops_allowed_at_standard`
- `test_unknown_tool_allowed_at_restricted`
- `test_error_mentions_current_tier`
- `test_error_mentions_tool_name`

### [unit/test_proactive_monitor.py](../tests/unit/test_proactive_monitor.py) — 58 tests


#### `TestEnums`

- `test_alert_level_values`
- `test_health_status_values`

#### `TestHealthCheck`

- `test_to_dict`
- `test_default_optional_fields`

#### `TestAlert`

- `test_to_dict_converts_level`

#### `TestMonitoringSession`

- `test_to_dict_converts_status`

#### `TestHealthCheckerDisk`

- `test_disk_healthy`
- `test_disk_warning`
- `test_disk_critical`
- `test_disk_subprocess_error`

#### `TestHealthCheckerMemory`

- `test_memory_healthy`
- `test_memory_warning`
- `test_memory_critical`
- `test_memory_subprocess_error`

#### `TestHealthCheckerService`

- `test_service_active`
- `test_service_inactive`
- `test_service_error`

#### `TestHealthCheckerLogSize`

- `test_log_file_healthy`
- `test_log_path_not_found`
- `test_log_directory`
- `test_log_warning_threshold`
- `test_log_critical_threshold`

#### `TestHealthCheckerSSL`

- `test_ssl_valid`
- `test_ssl_invalid`
- `test_ssl_error`

#### `TestRemediator`

- `test_remediate_direct_command_success`
- `test_remediate_direct_command_failure`
- `test_remediate_exception`
- `test_remediate_with_orchestrator`

#### `TestProactiveMonitorInit`

- `test_creates_storage_dir`
- `test_initializes_default_checks`
- `test_health_checks_file_created`
- `test_no_session_initially`

#### `TestProactiveMonitorStartMonitoring`

- `test_start_monitoring_creates_session`
- `test_start_monitoring_sets_current_session`

#### `TestProactiveMonitorChecks`

- `test_add_health_check`
- `test_remove_health_check`
- `test_get_status_no_session`
- `test_get_status_with_session`

#### `TestProactiveMonitorRunChecks`

- `test_run_checks_no_issues`
- `test_run_checks_generates_alert_on_failure`
- `test_run_checks_updates_session_count`
- `test_run_checks_updates_status_on_warning`
- `test_run_checks_updates_status_on_critical`
- `test_run_checks_auto_remediation`

#### `TestProactiveMonitorShouldRunCheck`

- `test_should_run_when_never_checked`
- `test_should_not_run_when_recently_checked`
- `test_should_run_when_overdue`

#### `TestProactiveMonitorCreateAlert`

- `test_creates_alert_with_correct_level`
- `test_creates_warning_alert`
- `test_alert_has_unique_id`

#### `TestProactiveMonitorIsRecent`

- `test_recent_timestamp`
- `test_old_timestamp`
- `test_invalid_timestamp`

#### `TestProactiveMonitorPersistence`

- `test_loads_saved_checks`
- `test_saves_and_loads_alerts`

#### `TestGetProactiveMonitor`

- `test_returns_instance`
- `test_returns_same_instance`

### [unit/test_prompt_evolution.py](../tests/unit/test_prompt_evolution.py) — 66 tests


#### `TestPromptVersionStats`

- `test_update_stats_success_increments_counters`
- `test_update_stats_failure_increments_failure_count`
- `test_success_rate_calculated_correctly`
- `test_success_rate_zero_when_no_uses`
- `test_add_example_appends`
- `test_add_example_keeps_at_most_10`
- `test_add_example_keeps_most_recent`
- `test_to_dict_returns_dict`

#### `TestPromptVariantStats`

- `test_update_stats_success`
- `test_update_stats_success_rate`
- `test_to_dict`

#### `TestPromptEvolutionInit`

- `test_storage_dir_created`
- `test_versions_empty_initially`
- `test_variants_empty_initially`
- `test_active_tests_empty_initially`

#### `TestGetPrompt`

- `test_returns_tuple_of_prompt_and_version`
- `test_creates_default_version_if_absent`
- `test_prompt_contains_user_input`
- `test_prompt_contains_context_when_provided`
- `test_domain_specific_version_used`
- `test_few_shot_examples_included_in_prompt`
- `test_variant_used_when_active_test_exists`

#### `TestDomainDetection`

- `test_detects_git_domain`
- `test_detects_docker_domain`
- `test_detects_files_domain`
- `test_detects_network_domain`
- `test_detects_database_domain`
- `test_returns_none_for_unknown_domain`

#### `TestRecordResult`

- `test_records_success_for_version`
- `test_records_failure_for_version`
- `test_adds_example_on_success_with_result`
- `test_no_example_added_on_failure`
- `test_records_result_for_variant`
- `test_ignores_unknown_version_id`
- `test_saves_versions_to_disk_after_record`

#### `TestCreateVariant`

- `test_returns_variant_id_string`
- `test_variant_added_to_variants_dict`
- `test_variant_added_to_active_tests`
- `test_variant_stores_base_version`
- `test_variant_stores_modification`
- `test_raises_on_unknown_base_version`
- `test_persists_variant_to_disk`

#### `TestPromoteVariant`

- `test_returns_new_version_id`
- `test_new_version_added_to_versions`
- `test_variant_removed_from_active_tests`
- `test_new_version_inherits_stats`
- `test_new_version_inherits_examples_from_base`
- `test_raises_on_unknown_variant`

#### `TestAutoPromotionOnSufficientSamples`

- `test_no_promotion_below_min_samples`
- `test_no_promotion_when_not_significantly_better`
- `test_auto_promotes_when_significantly_better`

#### `TestAutoImprovementVariantGeneration`

- `test_generates_variant_when_success_rate_low`
- `test_does_not_generate_when_max_tests_reached`

#### `TestGetStatistics`

- `test_returns_statistics_dict`
- `test_statistics_includes_version_count`
- `test_statistics_includes_active_tests`
- `test_statistics_versions_list`

#### `TestPersistence`

- `test_versions_persist_across_instances`
- `test_variants_persist_across_instances`
- `test_active_tests_persist_across_instances`
- `test_load_versions_returns_empty_on_missing_file`
- `test_load_versions_handles_corrupt_file`
- `test_load_variants_handles_corrupt_file`
- `test_load_active_tests_handles_corrupt_file`

#### `TestGetPromptEvolution`

- `test_returns_instance`
- `test_returns_same_singleton`

### [unit/test_provider_override.py](../tests/unit/test_provider_override.py) — 52 tests


#### `TestInferProviderFromModel`

- `test_claude_model_infers_anthropic`
- `test_sonnet_model_infers_anthropic`
- `test_haiku_model_infers_anthropic`
- `test_opus_model_infers_anthropic`
- `test_gpt_model_infers_openai`
- `test_o1_model_infers_openai`
- `test_o3_model_infers_openai`
- `test_o4_model_infers_openai`
- `test_deepseek_model_infers_deepseek`
- `test_llama_model_infers_ollama`
- `test_qwen_model_infers_ollama`
- `test_mistral_model_infers_ollama`
- `test_phi_model_infers_ollama`
- `test_gemma_model_infers_ollama`
- `test_unknown_model_returns_none`
- `test_inference_is_case_insensitive`

#### `TestAtProviderSyntax`

- `test_at_provider_with_colon_and_space`
- `test_at_claude_alias`
- `test_at_local_alias`
- `test_at_gpt_alias`
- `test_at_unknown_provider_no_match`
- `test_at_provider_case_insensitive`

#### `TestUseSyntax`

- `test_use_provider_colon`
- `test_using_provider_comma`
- `test_using_ollama_alias`
- `test_use_case_insensitive`
- `test_using_unknown_provider_no_match`
- `test_use_provider_space_separator`

#### `TestProviderFlagSyntax`

- `test_provider_flag_equals`
- `test_provider_flag_space`
- `test_provider_flag_claude_alias`
- `test_provider_flag_unknown_does_not_override`
- `test_provider_flag_case_insensitive`

#### `TestModelFlagSyntax`

- `test_model_flag_equals`
- `test_model_flag_space`
- `test_model_flag_deepseek`
- `test_model_flag_unknown_model_no_provider`
- `test_model_flag_case_insensitive`
- `test_model_flag_provider_flag_together`

#### `TestNoDirectiveAndEdgeCases`

- `test_plain_text_unchanged`
- `test_empty_string_unchanged`
- `test_only_directive_no_command_restores_original`
- `test_leading_whitespace_stripped`
- `test_multiline_command_preserved`

#### `TestDescribeOverride`

- `test_provider_and_model`
- `test_model_only`
- `test_provider_only`
- `test_neither_returns_empty_string`

#### `TestProviderAliasesMap`

- `test_all_canonical_names_are_self_mapped`
- `test_claude_maps_to_anthropic`
- `test_llama_maps_to_ollama`
- `test_chatgpt_maps_to_openai`

### [unit/test_registry.py](../tests/unit/test_registry.py) — 34 tests


#### `TestToolsDict`

- `test_tools_is_not_empty`
- `test_shell_ops_registered`
- `test_code_exec_registered`
- `test_file_ops_registered`
- `test_network_ops_registered`
- `test_process_ops_registered`
- `test_package_ops_registered`
- `test_all_values_are_tool_instances`
- `test_lookup_by_name`
- `test_missing_tool_raises_key_error`

#### `TestDescribe`

- `test_returns_dict`
- `test_contains_known_tools`
- `test_each_entry_has_doc`
- `test_each_entry_has_privileged_flag`
- `test_each_entry_has_actions_list`
- `test_shell_ops_marked_privileged`
- `test_code_exec_marked_privileged`
- `test_file_ops_not_privileged`
- `test_actions_have_name_doc_params`
- `test_shell_ops_has_run_action`
- `test_code_exec_has_python_action`
- `test_code_exec_has_bash_script_action`
- `test_private_methods_excluded`
- `test_dry_run_excluded`
- `test_execute_excluded`
- `test_privileged_flag_consistent_with_privileged_tools`

#### `TestDescribeCompact`

- `test_returns_string`
- `test_not_empty`
- `test_contains_tool_names`
- `test_privileged_tools_tagged`
- `test_shell_ops_line_has_privileged_tag`
- `test_non_privileged_tool_has_no_privileged_tag`
- `test_actions_indented_with_dash`
- `test_action_lines_contain_em_dash`

### [unit/test_rollback.py](../tests/unit/test_rollback.py) — 47 tests

- `test_analyze_feasibility_all_rollbackable`
- `test_analyze_feasibility_with_non_rollbackable`
- `test_describe_rollback_delete`
- `test_describe_rollback_move_back`
- `test_rollback_file_creation`
- `test_rollback_dry_run`
- `test_rollback_with_non_rollbackable_action`
- `test_rollback_last_n_actions`
- `test_rollback_empty_transaction`
- `test_rollback_updates_transaction_status`
- `test_rollback_marks_actions_as_rolled_back`
- `test_rollback_file_move`
- `test_rollback_partial_failure`
- `test_rollback_last_n_no_transactions`
- `test_rollback_last_n_fewer_than_requested`
- `test_rollback_last_n_dry_run`
- `test_rollback_last_n_skips_non_rollbackable`
- `test_execute_rollback_delete_file`
- `test_execute_rollback_delete_directory`
- `test_execute_rollback_delete_raises_when_missing`
- `test_execute_rollback_delete_raises_when_no_path`
- `test_execute_rollback_delete_copy`
- `test_execute_rollback_delete_copy_missing_is_ok`
- `test_execute_rollback_move_back`
- `test_execute_rollback_restore_raises`
- `test_execute_rollback_restore_content_raises`
- `test_execute_rollback_uninstall`
- `test_execute_rollback_reinstall`
- `test_execute_rollback_git_reset`
- `test_execute_rollback_stop`
- `test_execute_rollback_start`
- `test_execute_rollback_stop_and_remove`
- `test_execute_rollback_requires_manual_raises`
- `test_execute_rollback_unknown_strategy_raises`
- `test_execute_rollback_called_process_error`
- `test_execute_package_op_apt_install`
- `test_execute_package_op_apt_remove`
- `test_execute_package_op_dnf`
- `test_execute_package_op_pacman`
- `test_execute_package_op_no_manager_raises`
- `test_restore_checkpoint_not_found`
- `test_restore_checkpoint_dry_run`
- `test_restore_checkpoint_backup_not_found`
- `test_restore_checkpoint_success`
- `test_get_rollback_engine_singleton`
- `test_describe_rollback_all_strategies`
- `test_describe_rollback_unknown_strategy`

### [unit/test_router.py](../tests/unit/test_router.py) — 10 tests


#### `TestCommandRouter`

- `test_no_args_routes_to_interactive`
- `test_shell_command_routes_to_interactive`
- `test_help_flag_routes_to_help`
- `test_version_flag_routes_to_version`
- `test_direct_command_single_word`
- `test_direct_command_multiple_words`
- `test_dry_run_flag_parsing`
- `test_dry_run_flag_defaults_false`
- `test_show_help_outputs`
- `test_show_version_outputs`

### [unit/test_safety_policy.py](../tests/unit/test_safety_policy.py) — 5 tests


#### `TestSafetyPolicy`

- `test_allows_read_operations`
- `test_allows_create_operations`
- `test_allows_modify_operations`
- `test_blocks_delete_operations`
- `test_blocks_unknown_high_risk`

### [unit/test_sandbox.py](../tests/unit/test_sandbox.py) — 67 tests


#### `TestSandboxConstraintsInit`

- `test_empty_constraints_have_no_read_paths`
- `test_empty_constraints_have_no_write_paths`
- `test_paths_normalised_to_absolute`
- `test_tilde_expanded`
- `test_forbidden_paths_normalised`
- `test_default_max_execution_time`
- `test_network_disabled_by_default`
- `test_subprocess_disabled_by_default`

#### `TestSandboxConstraintsCanRead`

- `test_can_read_anywhere_with_no_allow_list`
- `test_cannot_read_forbidden_path`
- `test_can_read_within_allowed_path`
- `test_cannot_read_outside_allowed_path`
- `test_forbidden_takes_priority_over_allowed`

#### `TestSandboxConstraintsCanWrite`

- `test_cannot_write_without_explicit_permission`
- `test_can_write_within_allowed_write_path`
- `test_cannot_write_outside_allowed_write_path`
- `test_cannot_write_to_forbidden_path`
- `test_can_write_to_home_subdirectory`

#### `TestSandboxConstraintsIsUnderAny`

- `test_exact_match_returns_true`
- `test_subpath_returns_true`
- `test_unrelated_path_returns_false`
- `test_empty_parents_returns_false`

#### `TestPresetProfiles`

- `test_get_safe_defaults_has_write_to_home_and_tmp`
- `test_get_safe_defaults_blocks_network`
- `test_get_safe_defaults_blocks_etc`
- `test_get_restricted_has_limited_read`
- `test_get_restricted_max_time_ten_seconds`
- `test_get_permissive_allows_network`
- `test_get_permissive_allows_subprocess`
- `test_get_filesystem_only_no_network`
- `test_get_filesystem_only_no_subprocess`

#### `TestSandboxExecutorInit`

- `test_uses_safe_defaults_when_no_constraints`
- `test_uses_provided_constraints`

#### `TestSandboxExecutorValidatePaths`

- `test_read_allowed_path_no_raise`
- `test_write_denied_raises_sandbox_violation`
- `test_write_allowed_path_no_raise`
- `test_read_forbidden_path_raises`

#### `TestSandboxExecutorValidateNetwork`

- `test_network_disabled_raises`
- `test_network_enabled_no_raise`
- `test_host_not_in_allowed_list_raises`
- `test_host_in_allowed_list_no_raise`

#### `TestSandboxExecutorValidateSubprocess`

- `test_subprocess_disabled_raises`
- `test_subprocess_enabled_no_raise`

#### `TestSandboxExecutorExecute`

- `test_executes_function_and_returns_result`
- `test_passes_args_to_function`
- `test_passes_kwargs_to_function`
- `test_raises_sandbox_violation_on_write_to_forbidden`
- `test_check_paths_false_skips_validation`
- `test_function_exceptions_propagate`

#### `TestSandboxExecutorTimeout`

- `test_timeout_raises_sandbox_timeout`
- `test_fast_operation_no_timeout`

#### `TestSandboxViolationHierarchy`

- `test_sandbox_violation_is_exception`
- `test_sandbox_timeout_is_sandbox_violation`

#### `TestSandboxedToolBase`

- `test_execute_safe_calls_method`
- `test_execute_safe_has_sandbox_attribute`

#### `TestToolSandboxWrapperInit`

- `test_stores_tool_and_sandbox`

#### `TestToolSandboxWrapperExecute`

- `test_execute_calls_tool_action`
- `test_execute_raises_sandbox_violation_for_forbidden_write`
- `test_execute_wraps_permission_denied_as_sandbox_violation`
- `test_execute_propagates_other_exceptions`

#### `TestToolSandboxWrapperValidateStepPaths`

- `test_write_action_checks_write_permission`
- `test_read_action_with_safe_path_no_raise`
- `test_step_with_no_path_args_no_raise`

#### `TestToolSandboxRegistry`

- `test_registry_wraps_all_tools`
- `test_registry_get_returns_none_for_unknown`
- `test_registry_keys_returns_all_tool_names`
- `test_registry_uses_provided_constraints`

### [unit/test_schemas.py](../tests/unit/test_schemas.py) — 12 tests


#### `TestStep`

- `test_valid_step_creation`
- `test_step_defaults_empty_args`
- `test_step_requires_tool`
- `test_step_requires_action`
- `test_step_requires_risk`
- `test_step_validates_risk_range`

#### `TestIntentIR`

- `test_valid_intent_creation`
- `test_intent_requires_goal`
- `test_intent_requires_confirmation_flag`
- `test_intent_requires_steps`
- `test_intent_can_have_empty_steps`
- `test_intent_validates_step_structure`

### [unit/test_self_reflection.py](../tests/unit/test_self_reflection.py) — 36 tests


#### `TestConfidenceLevelMapping`

- `test_score_above_90_is_very_high`
- `test_score_exactly_90_is_very_high`
- `test_score_70_to_89_is_high`
- `test_score_50_to_69_is_medium`
- `test_score_30_to_49_is_low`
- `test_score_below_30_is_very_low`

#### `TestReflectOnPlan`

- `test_returns_plan_reflection_instance`
- `test_high_confidence_plan`
- `test_low_confidence_forces_ask_user`
- `test_critical_issues_are_stored`
- `test_questions_for_user_propagated`
- `test_suggested_improvements_propagated`
- `test_step_reflection_parsed`
- `test_step_confidence_level_assigned`
- `test_logger_called_on_success`
- `test_llm_called_with_prompt`
- `test_context_included_in_prompt`
- `test_returns_fallback_on_llm_json_error`
- `test_fallback_logs_error`
- `test_fallback_has_one_step_reflection_per_intent_step`
- `test_estimated_success_probability_equals_overall_score`

#### `TestShouldProceed`

- `test_proceeds_when_all_clear`
- `test_does_not_proceed_with_critical_issues`
- `test_does_not_proceed_with_low_confidence`
- `test_does_not_proceed_with_very_low_confidence`
- `test_does_not_proceed_when_ask_user_set`
- `test_returns_reason_string_on_proceed`

#### `TestFallbackReflection`

- `test_fallback_confidence_is_medium`
- `test_fallback_does_not_ask_user`
- `test_fallback_step_descriptions_match_intent`

#### `TestReflectionPromptBuilding`

- `test_prompt_contains_user_input`
- `test_prompt_contains_goal`
- `test_prompt_contains_step_tool_and_action`
- `test_prompt_includes_context_when_provided`

#### `TestGetSelfReflection`

- `test_get_self_reflection_returns_instance`
- `test_get_self_reflection_singleton`

### [unit/test_semantic_search.py](../tests/unit/test_semantic_search.py) — 28 tests


#### `TestSemanticSearchInit`

- `test_raises_import_error_when_deps_missing`
- `test_initial_embeddings_are_none`
- `test_initial_metadata_is_empty`
- `test_cache_dir_created`

#### `TestAddCommand`

- `test_add_single_command_sets_embeddings`
- `test_add_single_command_stores_metadata`
- `test_metadata_fields_stored`
- `test_add_multiple_commands_accumulates_metadata`
- `test_add_command_persists_to_disk`
- `test_add_command_default_timestamp`

#### `TestLoadCache`

- `test_cache_loaded_on_reinit`
- `test_corrupt_cache_falls_back_to_empty`

#### `TestSearch`

- `test_search_empty_index_returns_empty`
- `test_search_returns_list`
- `test_search_result_has_similarity_field`
- `test_search_respects_top_k`
- `test_search_filters_by_min_similarity`
- `test_search_metadata_fields_in_results`
- `test_search_does_not_mutate_metadata`

#### `TestGetSuccessRate`

- `test_returns_half_when_no_similar_results`
- `test_full_success_rate`
- `test_zero_success_rate`
- `test_mixed_success_rate`

#### `TestGetStats`

- `test_stats_empty_index`
- `test_stats_total_commands`
- `test_stats_success_rate_all_success`
- `test_stats_success_rate_mixed`
- `test_stats_contains_cache_size_mb`

### [unit/test_service_ops.py](../tests/unit/test_service_ops.py) — 32 tests


#### `TestRunSystemctl`

- `test_returns_combined_stdout_stderr`
- `test_sudo_prepended_when_requested`
- `test_no_sudo_by_default`
- `test_exception_returns_error_string`
- `test_systemctl_is_in_command`
- `test_timeout_is_30`

#### `TestServiceStart`

- `test_start_calls_systemctl_start`
- `test_start_uses_sudo`
- `test_start_exception_returns_error`

#### `TestServiceStop`

- `test_stop_calls_systemctl_stop`
- `test_stop_uses_sudo`

#### `TestServiceRestart`

- `test_restart_calls_systemctl_restart`
- `test_restart_uses_sudo`

#### `TestServiceStatus`

- `test_status_calls_systemctl_status`
- `test_status_does_not_use_sudo`
- `test_status_returns_output`

#### `TestServiceEnable`

- `test_enable_calls_systemctl_enable`
- `test_enable_uses_sudo`

#### `TestServiceDisable`

- `test_disable_calls_systemctl_disable`
- `test_disable_uses_sudo`

#### `TestServiceListServices`

- `test_list_includes_type_service`
- `test_list_no_state_no_filter`
- `test_list_with_state_filter`
- `test_list_does_not_use_sudo`
- `test_list_active_state`

#### `TestServiceLogs`

- `test_logs_calls_journalctl`
- `test_logs_default_50_lines`
- `test_logs_custom_lines`
- `test_logs_uses_no_pager`
- `test_logs_returns_stdout`
- `test_logs_exception_returns_error`
- `test_logs_timeout_is_10`

### [unit/test_session_memory.py](../tests/unit/test_session_memory.py) — 34 tests


#### `TestSessionMemoryInit`

- `test_default_max_history`
- `test_custom_max_history`
- `test_initial_state_empty`
- `test_session_start_is_set`

#### `TestAddIntent`

- `test_add_intent_with_goal_and_steps`
- `test_add_intent_stores_intent_object`
- `test_add_intent_without_goal_attribute`
- `test_add_intent_without_steps_attribute`
- `test_add_intent_default_user_input_and_result`
- `test_add_intent_timestamp_is_set`
- `test_history_enforces_max_history_limit`
- `test_history_keeps_most_recent_on_overflow`
- `test_intents_list_not_trimmed`

#### `TestContextRefs`

- `test_add_and_get_context_ref`
- `test_get_missing_context_ref_returns_none`
- `test_overwrite_context_ref`
- `test_multiple_context_refs`

#### `TestGetRecentIntents`

- `test_get_recent_returns_last_n`
- `test_get_recent_are_most_recent`
- `test_get_recent_fewer_than_requested`
- `test_get_recent_empty_history`

#### `TestGetContextSummary`

- `test_summary_no_history`
- `test_summary_with_intents`
- `test_summary_shows_context_refs`
- `test_summary_no_context_refs_section_when_empty`
- `test_summary_limits_to_three_most_recent_intents`

#### `TestClear`

- `test_clear_removes_intent_history`
- `test_clear_removes_context_refs`
- `test_clear_does_not_reset_intents_list`

#### `TestGetSessionStats`

- `test_stats_structure`
- `test_stats_counts_intents`
- `test_stats_counts_context_refs`
- `test_stats_duration_is_non_negative`
- `test_stats_after_clear`

### [unit/test_shell_commands.py](../tests/unit/test_shell_commands.py) — 53 tests


#### `TestHandleStatusCommand`

- `test_runs_without_error`
- `test_memory_disabled_no_crash`
- `test_config_exception_fallback`
- `test_fallback_disabled_printed`
- `test_fallback_chain_printed`

#### `TestHandleModelCommand`

- `test_status`
- `test_empty_is_status`
- `test_list`
- `test_set_no_args_usage`
- `test_set_invalid_provider`
- `test_set_valid_provider_calls_update`
- `test_set_provider_only_passes_none_model`
- `test_unknown_subcommand`
- `test_config_exception_fallback`
- `test_fallback_providers_in_output`

#### `TestUpdateConfigProvider`

- `test_raises_when_no_config_found`
- `test_updates_provider_and_model`
- `test_updates_provider_without_model`
- `test_creates_llm_section_if_missing`

#### `TestHandleMemoryCommand`

- `test_memory_disabled_prints_message`
- `test_stats`
- `test_stats_no_frequent_paths`
- `test_clear_confirmed`
- `test_clear_declined`
- `test_unknown_subcommand`

#### `TestHandleUpdateCommand`

- `test_runs_without_error`
- `test_git_pull_failure_handled`

#### `TestHandleExplainCommand`

- `test_last`
- `test_history`
- `test_digit`
- `test_unknown_arg_prints_usage`

#### `TestCheckAndSuggestPatterns`

- `test_no_patterns_returns_early`
- `test_exception_silenced`
- `test_already_suggested_skipped`
- `test_recurring_user_accepts`
- `test_recurring_user_show_more`

#### `TestHandleWorkflowCommand`

- `test_list_no_workflows`
- `test_list_with_workflows`
- `test_record_no_args`
- `test_record_with_name_and_desc`
- `test_record_with_name_no_desc`
- `test_stop`
- `test_cancel`
- `test_replay_no_args`
- `test_replay_not_found`
- `test_replay_executes_commands`
- `test_replay_command_exception_breaks`
- `test_info_no_args`
- `test_info_not_found`
- `test_info_found_with_params`
- `test_delete_no_args`
- `test_delete_with_name`
- `test_unknown_subcommand`

### [unit/test_shell_executor.py](../tests/unit/test_shell_executor.py) — 20 tests


#### `TestStreamingExecutorQuiet`

- `test_quiet_returns_tuple`
- `test_quiet_passes_timeout`
- `test_quiet_nonzero_returncode`

#### `TestStreamingExecutorStreaming`

- `test_streaming_returns_stdout`
- `test_streaming_capture_false_does_not_accumulate`
- `test_streaming_stderr_captured`
- `test_streaming_returncode_propagated`
- `test_streaming_closes_pipes`

#### `TestStreamingExecutorExecute`

- `test_execute_streaming_by_default`
- `test_execute_quiet_when_not_streaming`
- `test_execute_timeout_returns_error`
- `test_execute_exception_returns_error`
- `test_execute_sudo_prepends_sudo`
- `test_execute_no_sudo_when_root`

#### `TestExecuteShellCommand`

- `test_returns_stdout_on_success`
- `test_includes_stderr_in_output`
- `test_returns_no_output_placeholder`
- `test_raises_on_nonzero_exit`
- `test_passes_timeout_to_executor`
- `test_combines_stdout_and_stderr`

### [unit/test_shell_modules.py](../tests/unit/test_shell_modules.py) — 41 tests


#### `TestShellHelpers`

- `test_setup_readline_does_not_raise`
- `test_clear_line_writes_escape_sequence`
- `test_move_cursor_up_writes_sequence`
- `test_save_cursor_writes_sequence`
- `test_restore_cursor_writes_sequence`
- `test_move_cursor_up_default_one_line`

#### `TestZenusCompleter`

- `test_special_commands_completed_at_start`
- `test_action_verb_completed`
- `test_common_target_completed`
- `test_unknown_word_no_crash`
- `test_completion_metadata_for_special_command`

#### `TestEnhancedShell`

- `test_create_enhanced_shell_factory`
- `test_prompt_returns_stripped_input`
- `test_prompt_returns_empty_on_keyboard_interrupt`
- `test_prompt_returns_exit_on_eoferror`
- `test_multiline_prompt_restores_multiline_flag`

#### `TestExplainMode`

- `test_generate_reasoning_single_step`
- `test_generate_reasoning_multiple_steps`
- `test_generate_reasoning_all_read_only`
- `test_generate_reasoning_danger_steps`
- `test_generate_reasoning_lists_tools`
- `test_explain_calls_print_explanation`
- `test_confirm_returns_true_for_y`
- `test_confirm_returns_false_for_n`

#### `TestExplainer`

- `test_explain_intent_prints_to_console`
- `test_explain_task_complexity_iterative`
- `test_explain_task_complexity_one_shot`
- `test_show_alternatives_prints_alternatives`

#### `TestExplainabilityDashboard`

- `test_add_execution_appends_to_history`
- `test_history_trimmed_to_max`
- `test_explain_last_with_empty_history`
- `test_explain_last_with_history_prints_details`
- `test_explain_execution_invalid_index`
- `test_show_history_empty`
- `test_execution_explanation_to_dict`
- `test_get_explainability_dashboard_singleton`

#### `TestResponseGenerator`

- `test_simple_summary_no_results`
- `test_simple_summary_created_result`
- `test_simple_summary_found_result`
- `test_simple_summary_generic_result`
- `test_generate_summary_returns_string`

### [unit/test_shell_ops.py](../tests/unit/test_shell_ops.py) — 38 tests


#### `TestIsBlocked`

- `test_allows_safe_command`
- `test_blocks_rm_rf_root`
- `test_blocks_rm_rf_root_with_extra_spaces`
- `test_blocks_dd_if`
- `test_blocks_fork_bomb`
- `test_blocks_mkfs`
- `test_blocks_redirect_to_dev_sd`
- `test_allows_dd_without_if`
- `test_allows_rm_in_subdir`
- `test_allows_rm_relative_path`

#### `TestShellOpsRun`

- `test_run_returns_stdout`
- `test_run_combines_stdout_and_stderr`
- `test_run_no_output_returns_placeholder`
- `test_run_raises_on_nonzero_exit`
- `test_run_raises_on_timeout`
- `test_run_blocks_hard_blocked_command`
- `test_run_blocks_fork_bomb`
- `test_run_passes_working_dir`
- `test_run_expands_tilde_in_working_dir`
- `test_run_uses_bash_c`
- `test_run_default_timeout_120`
- `test_run_custom_timeout`

#### `TestShellOpsDryRun`

- `test_dry_run_contains_command`
- `test_dry_run_contains_dry_run_prefix`
- `test_dry_run_marks_blocked_command`
- `test_dry_run_includes_working_dir`
- `test_dry_run_does_not_execute`

#### `TestStreamingExecutor`

- `test_execute_quiet_success`
- `test_execute_quiet_failure`
- `test_execute_timeout_returns_error_tuple`
- `test_execute_generic_exception_returns_error_tuple`
- `test_execute_streaming_captures_stdout`
- `test_sudo_prepended_when_not_root`
- `test_sudo_not_prepended_when_root`

#### `TestExecuteShellCommand`

- `test_returns_stdout_on_success`
- `test_includes_stderr_in_result`
- `test_no_output_placeholder`
- `test_raises_on_failure`

### [unit/test_suggestion_engine.py](../tests/unit/test_suggestion_engine.py) — 40 tests


#### `TestAnalyzeOrchestration`

- `test_analyze_returns_list`
- `test_analyze_returns_at_most_five_suggestions`
- `test_analyze_sorted_by_confidence_descending`
- `test_analyze_empty_steps_no_crash`
- `test_analyze_passes_context_to_rules`

#### `TestSuggestBatchOperations`

- `test_three_same_file_ops_triggers_suggestion`
- `test_fewer_than_three_file_ops_no_suggestion`
- `test_mixed_file_ops_actions_no_suggestion`
- `test_batch_suggestion_confidence_is_high`

#### `TestSuggestParallelExecution`

- `test_fewer_than_three_steps_returns_none`
- `test_parallelizable_steps_suggest_parallel`
- `test_sequential_steps_no_parallel_suggestion`

#### `TestSuggestCaching`

- `test_duplicate_urls_triggers_cache_suggestion`
- `test_different_urls_no_cache_suggestion`
- `test_single_network_op_no_cache_suggestion`

#### `TestSuggestToolAlternatives`

- `test_high_failure_rate_triggers_alternative_suggestion`
- `test_low_failure_rate_no_alternative_suggestion`
- `test_no_alternatives_available_no_suggestion`

#### `TestWarnAboutFailures`

- `test_low_success_probability_triggers_warning`
- `test_high_success_probability_no_warning`

#### `TestWarnAboutDestructiveOps`

- `test_high_risk_step_triggers_warning`
- `test_low_risk_steps_no_warning`
- `test_multiple_high_risk_steps_counted`

#### `TestWarnAboutPerformance`

- `test_three_browser_ops_triggers_warning`
- `test_fewer_than_three_slow_ops_no_warning`
- `test_download_network_ops_counted_as_slow`

#### `TestShouldShow`

- `test_suggestion_above_threshold_shown`
- `test_suggestion_below_threshold_not_shown`
- `test_warning_always_shown_regardless_of_threshold`
- `test_low_accept_rate_hides_suggestion`
- `test_zero_accept_rate_does_not_suppress`
- `test_custom_threshold`

#### `TestFormatSuggestion`

- `test_format_includes_title`
- `test_format_includes_description`
- `test_format_includes_reason`
- `test_format_unknown_type_defaults_to_bulb_icon`

#### `TestGetToolAlternatives`

- `test_browser_ops_has_alternatives`
- `test_unknown_tool_returns_empty_list`

#### `TestGetSuggestionEngineSingleton`

- `test_returns_suggestion_engine_instance`
- `test_returns_same_instance_on_second_call`

### [unit/test_system_ops_unit.py](../tests/unit/test_system_ops_unit.py) — 30 tests


#### `TestSystemOpsDiskUsage`

- `test_returns_formatted_string`
- `test_calculates_percent_correctly`
- `test_file_not_found_returns_error`
- `test_oserror_returns_error`
- `test_expands_tilde_in_path`
- `test_free_gb_shown`

#### `TestSystemOpsMemoryInfo`

- `test_returns_formatted_memory`
- `test_available_gb_included`

#### `TestSystemOpsCpuInfo`

- `test_returns_cpu_string`
- `test_zero_percent_included`

#### `TestSystemOpsGetSystemInfo`

- `test_returns_multiline_info`
- `test_version_truncated`

#### `TestSystemOpsListProcesses`

- `test_returns_pid_and_name`
- `test_respects_limit`
- `test_sorted_by_memory_descending`
- `test_skips_no_such_process`
- `test_skips_access_denied`

#### `TestSystemOpsUptime`

- `test_returns_days_hours_minutes`
- `test_zero_days_allowed`

#### `TestSystemOpsFindLargeFiles`

- `test_finds_files_above_threshold`
- `test_no_large_files_returns_message`
- `test_oserror_on_file_skipped`
- `test_walk_exception_returns_error`
- `test_respects_limit`
- `test_skips_hidden_dirs`

#### `TestSystemOpsCheckResourceUsage`

- `test_contains_cpu_memory_disk`
- `test_high_cpu_triggers_warning`
- `test_high_memory_triggers_warning`
- `test_high_disk_triggers_warning`
- `test_no_warnings_under_thresholds`

### [unit/test_task_analyzer.py](../tests/unit/test_task_analyzer.py) — 13 tests

- `test_task_analyzer_initialization`
- `test_simple_oneshot_tasks`
- `test_complex_iterative_tasks`
- `test_multi_step_detection`
- `test_conditional_task_detection`
- `test_estimated_steps`
- `test_task_complexity_representation`
- `test_iterative_keywords_detection`
- `test_oneshot_keywords_detection`
- `test_word_count_heuristic`
- `test_file_operations_with_conditions`
- `test_reasoning_provided`
- `test_confidence_ranges`

### [unit/test_task_complexity.py](../tests/unit/test_task_complexity.py) — 50 tests


#### `TestComplexityScoreProperties`

- `test_is_simple_below_threshold`
- `test_is_simple_at_threshold`
- `test_is_simple_above_threshold`
- `test_is_complex_above_threshold`
- `test_is_complex_at_threshold`
- `test_is_complex_below_threshold`
- `test_neither_simple_nor_complex`

#### `TestAnalyzerDefaults`

- `test_default_cheap_model`
- `test_default_powerful_model`
- `test_custom_models`

#### `TestAnalyzeSimpleInputs`

- `test_ls_command_is_simple`
- `test_pwd_is_simple_operation`
- `test_simple_keyword_reduces_score`
- `test_check_status_is_simple`
- `test_cat_file_is_simple_op`
- `test_returns_complexity_score_instance`
- `test_reasons_is_list`
- `test_confidence_between_0_and_1`
- `test_score_between_0_and_1`

#### `TestAnalyzeComplexInputs`

- `test_analyze_keyword_increases_score`
- `test_refactor_keyword_increases_score`
- `test_design_keyword_increases_score`
- `test_long_command_increases_score`
- `test_medium_length_command`
- `test_codebase_keyword_increases_score`
- `test_repository_keyword_increases_score`
- `test_database_keyword_increases_score`
- `test_multiple_complex_keywords_boost`

#### `TestAnalyzeIterative`

- `test_iterative_mode_boosts_score`
- `test_iterative_adds_reason`
- `test_iterative_adds_04_to_score`

#### `TestAnalyzeMultiStep`

- `test_and_connector_counts_as_step`
- `test_step_number_pattern`
- `test_first_second_pattern`

#### `TestAnalyzeDestructive`

- `test_delete_noted_in_reasons`
- `test_remove_noted_in_reasons`
- `test_destroy_noted_in_reasons`
- `test_wipe_noted_in_reasons`

#### `TestModelRecommendation`

- `test_simple_task_recommends_cheap_model`
- `test_highly_complex_task_recommends_powerful_model`
- `test_medium_score_uses_cheap_model`

#### `TestShouldUsePowerfulModel`

- `test_simple_task_returns_false`
- `test_highly_complex_returns_true`
- `test_returns_bool`
- `test_iterative_flag_propagated`

#### `TestScoreClamping`

- `test_score_never_exceeds_1`
- `test_score_never_below_0`
- `test_confidence_never_exceeds_095`

#### `TestCaseInsensitivity`

- `test_uppercase_keywords_detected`
- `test_mixed_case_keywords`

### [unit/test_text_ops_enhanced.py](../tests/unit/test_text_ops_enhanced.py) — 15 tests

- `test_write_new_file`
- `test_write_overwrite_existing`
- `test_write_multiline`
- `test_read_small_file`
- `test_read_large_file`
- `test_append_to_existing`
- `test_search_case_insensitive`
- `test_search_case_sensitive`
- `test_count_lines`
- `test_head_default`
- `test_tail_default`
- `test_write_creates_parent_directories`
- `test_read_nonexistent_file`
- `test_write_empty_content`
- `test_write_unicode`

### [unit/test_tools_base.py](../tests/unit/test_tools_base.py) — 11 tests


#### `TestToolInterface`

- `test_dry_run_raises_not_implemented`
- `test_execute_raises_not_implemented`
- `test_dry_run_raises_with_kwargs`
- `test_execute_raises_with_kwargs`

#### `TestToolSubclass`

- `test_subclass_can_override_dry_run`
- `test_subclass_can_override_execute`
- `test_subclass_dry_run_not_raises`
- `test_partial_subclass_execute_still_raises`
- `test_partial_subclass_dry_run_still_raises`
- `test_name_attribute_on_subclass`
- `test_multiple_subclasses_independent`

### [unit/test_tools_misc.py](../tests/unit/test_tools_misc.py) — 69 tests


#### `TestNetworkOpsCurl`

- `test_curl_get_returns_stdout`
- `test_curl_uses_silent_mode_without_output`
- `test_curl_post_with_data`
- `test_curl_with_headers`
- `test_curl_with_output_file_returns_saved_message`
- `test_curl_exception_returns_error_string`
- `test_curl_uses_x_flag_for_method`

#### `TestNetworkOpsWget`

- `test_wget_returns_output`
- `test_wget_with_output_file`
- `test_wget_exception_returns_error_string`

#### `TestNetworkOpsPing`

- `test_ping_returns_stdout`
- `test_ping_default_count_4`
- `test_ping_custom_count`
- `test_ping_exception_returns_error_string`

#### `TestNetworkOpsTraceroute`

- `test_traceroute_returns_stdout`
- `test_traceroute_falls_back_to_tracepath`
- `test_traceroute_exception_returns_error_string`

#### `TestNetworkOpsSsh`

- `test_ssh_with_command_returns_stdout`
- `test_ssh_with_user`
- `test_ssh_custom_port`
- `test_ssh_without_command_returns_error`
- `test_ssh_exception_returns_error_string`

#### `TestNetworkOpsNetstat`

- `test_netstat_returns_stdout`
- `test_netstat_listening_uses_tuln`
- `test_netstat_falls_back_to_netstat_command`
- `test_netstat_exception_returns_error_string`

#### `TestNetworkOpsNslookup`

- `test_nslookup_returns_stdout`
- `test_nslookup_exception_returns_error_string`

#### `TestProcessOpsFindByName`

- `test_find_returns_matching_process`
- `test_find_case_insensitive`
- `test_find_no_match_returns_message`
- `test_find_skips_no_such_process`
- `test_find_multiple_matches`

#### `TestProcessOpsInfo`

- `test_info_returns_process_details`
- `test_info_no_such_process`
- `test_info_access_denied`

#### `TestProcessOpsKill`

- `test_kill_terminate_sends_sigterm`
- `test_kill_force_sends_sigkill`
- `test_kill_no_such_process`
- `test_kill_access_denied`

#### `TestPackageOpsDetect`

- `test_detects_apt`
- `test_detects_dnf`
- `test_detects_pacman`
- `test_unknown_when_none_found`

#### `TestPackageOpsInstall`

- `test_apt_install`
- `test_apt_install_confirm_adds_y`
- `test_dnf_install`
- `test_pacman_install`
- `test_install_unsupported_manager`

#### `TestPackageOpsRemove`

- `test_apt_remove`
- `test_pacman_remove_uses_R_flag`
- `test_remove_unsupported_manager`

#### `TestPackageOpsUpdate`

- `test_apt_update_without_upgrade`
- `test_apt_update_with_upgrade_calls_both`
- `test_dnf_update`
- `test_update_unsupported_manager`

#### `TestPackageOpsSearch`

- `test_apt_search`
- `test_search_unsupported_manager`

#### `TestPackageOpsListInstalled`

- `test_apt_list_all`
- `test_list_with_pattern_filters`
- `test_list_unsupported_manager`

#### `TestPackageOpsClean`

- `test_apt_clean`
- `test_dnf_clean_all`
- `test_clean_unsupported_manager`

#### `TestPackageOpsInfo`

- `test_apt_info`
- `test_dnf_info`
- `test_pacman_info_uses_Si`
- `test_info_unsupported_manager`

#### `TestPackageOpsRuntimeError`

- `test_runtime_error_converted_to_string`

### [unit/test_tree_of_thoughts.py](../tests/unit/test_tree_of_thoughts.py) — 40 tests


#### `TestPathQualityDetermination`

- `test_confidence_above_90_is_excellent`
- `test_confidence_exactly_90_is_excellent`
- `test_confidence_70_to_89_is_good`
- `test_confidence_50_to_69_is_acceptable`
- `test_confidence_below_50_is_risky`

#### `TestPathScoring`

- `test_high_confidence_increases_score`
- `test_low_risk_increases_score`
- `test_fast_time_increases_score`
- `test_more_pros_increases_score`
- `test_score_within_valid_range`

#### `TestPathSelection`

- `test_selects_highest_scoring_path`
- `test_single_path_is_returned_unchanged`
- `test_returns_selection_reasoning_string`
- `test_large_margin_uses_clearly_wording`
- `test_selection_reasoning_mentions_path_id`

#### `TestGeneratePaths`

- `test_returns_list_of_solution_paths`
- `test_fallback_path_returned_when_parse_fails`
- `test_fallback_on_llm_generate_failure`
- `test_fallback_logs_error`
- `test_fallback_confidence_is_0_7`
- `test_fallback_quality_is_good`
- `test_prompt_contains_user_input`
- `test_prompt_contains_num_paths`
- `test_context_included_in_prompt`

#### `TestExplore`

- `test_explore_returns_thought_tree`
- `test_thought_tree_has_user_input`
- `test_thought_tree_has_selected_path`
- `test_thought_tree_paths_list_non_empty`
- `test_explore_respects_custom_num_paths_in_prompt`
- `test_explore_logs_when_learning_enabled`
- `test_explore_does_not_log_when_learning_disabled`
- `test_explore_records_exploration_time`
- `test_explore_selection_reasoning_non_empty`

#### `TestThoughtTreeGetBestPath`

- `test_returns_selected_path_when_set`
- `test_returns_highest_confidence_when_no_selected`

#### `TestParseIntentFromPath`

- `test_raises_on_invalid_step_fields`
- `test_empty_steps_raises_on_invalid_intent_fields`

#### `TestSolutionPathToDict`

- `test_quality_is_serialized_as_string`

#### `TestGetTreeOfThoughts`

- `test_returns_instance`
- `test_returns_same_singleton`

### [unit/test_vision_ops.py](../tests/unit/test_vision_ops.py) — 41 tests


#### `TestVisionOpsLazyLoad`

- `test_pil_image_available`
- `test_pil_image_raises_when_unavailable`
- `test_pil_imagegrab_available`
- `test_pyautogui_raises_when_unavailable`

#### `TestVisionOpsScreenshot`

- `test_screenshot_full_screen_returns_temp_path`
- `test_screenshot_with_save_path_returns_that_path`
- `test_screenshot_with_region`
- `test_screenshot_stores_last_screenshot`
- `test_screenshot_exception_returns_error`

#### `TestVisionOpsAnalyzeScreenshot`

- `test_returns_error_when_no_screenshot_and_no_path`
- `test_loads_image_from_path`
- `test_uses_last_screenshot_when_no_path`
- `test_returns_error_when_image_file_not_found`
- `test_llm_without_analyze_image_returns_message`
- `test_llm_exception_returns_error`

#### `TestVisionOpsFindOnScreen`

- `test_takes_screenshot_when_none_exists`
- `test_uses_existing_screenshot`
- `test_returns_analyze_result`

#### `TestVisionOpsMouseOps`

- `test_click_at_coordinates`
- `test_click_without_args_returns_message`
- `test_click_exception_returns_error`
- `test_click_with_description_calls_find`
- `test_double_click_calls_pyautogui`
- `test_double_click_exception_returns_error`
- `test_right_click_calls_pyautogui`
- `test_right_click_exception_returns_error`
- `test_move_to_calls_pyautogui`
- `test_move_to_exception_returns_error`
- `test_drag_calls_moveto_and_drag`
- `test_drag_exception_returns_error`

#### `TestVisionOpsKeyboardOps`

- `test_type_text_calls_write`
- `test_type_text_exception_returns_error`
- `test_press_key_calls_pyautogui`
- `test_press_key_exception_returns_error`
- `test_hotkey_calls_pyautogui`
- `test_hotkey_exception_returns_error`

#### `TestVisionOpsAdvanced`

- `test_get_screen_text_calls_analyze`
- `test_get_screen_text_takes_screenshot_when_none`
- `test_fill_form_iterates_fields`

#### `TestVisionOpsWaitForElement`

- `test_returns_immediately_when_found`
- `test_returns_timeout_message_when_not_found`

### [unit/test_visualization.py](../tests/unit/test_visualization.py) — 92 tests


#### `TestChartType`

- `test_auto_value`
- `test_all_types_present`

#### `TestChartGeneratorDetect`

- `test_dict_few_values_returns_pie`
- `test_dict_many_values_returns_bar`
- `test_list_short_numbers_returns_line`
- `test_list_long_numbers_returns_histogram`
- `test_list_of_pairs_returns_scatter`
- `test_unknown_falls_back_to_bar`

#### `TestChartGeneratorCreate`

- `test_create_chart_returns_path`
- `test_create_chart_with_dict_bar`
- `test_create_chart_auto_temp_file`
- `test_create_chart_pie`
- `test_create_chart_histogram`
- `test_create_chart_scatter`
- `test_create_chart_heatmap`
- `test_create_chart_with_title_and_labels`

#### `TestCreateChartFunction`

- `test_function_delegates_to_generator`

#### `TestTableFormatterNormalize`

- `test_list_of_dicts_passthrough`
- `test_list_of_lists_with_columns`
- `test_list_of_lists_auto_columns`
- `test_column_oriented_dict`
- `test_single_row_dict`
- `test_list_of_simple_values`

#### `TestTableFormatterFormatTable`

- `test_format_list_of_dicts`
- `test_format_empty_data`
- `test_format_with_title`
- `test_format_with_limit`
- `test_format_with_sort_by`
- `test_format_with_filter_func`
- `test_format_with_show_index`

#### `TestTableFormatterCellValues`

- `test_none_returns_dim_null`
- `test_true_returns_green_checkmark`
- `test_false_returns_red_cross`
- `test_int_formatted_with_commas`
- `test_float_formatted_two_decimals`
- `test_long_string_truncated`
- `test_list_serialized_as_json`

#### `TestTableFormatterProperties`

- `test_format_dict_returns_string`
- `test_format_dict_with_title`

#### `TestFormatTableFunction`

- `test_function_returns_string`

#### `TestDiffViewerTextDiff`

- `test_identical_strings_no_diff`
- `test_added_line_shows_green`
- `test_title_in_output`
- `test_non_unified_mode`

#### `TestDiffViewerDictDiff`

- `test_added_key_shown`
- `test_removed_key_shown`
- `test_changed_value_shown`
- `test_no_changes_message`

#### `TestDiffViewerListDiff`

- `test_list_diff_returns_string`
- `test_added_items_in_output`

#### `TestDiffViewerSummary`

- `test_dict_summary_contains_added_removed`
- `test_list_summary_contains_added`
- `test_text_summary_contains_lines`

#### `TestDiffViewerFileDiff`

- `test_file_diff_with_real_files`
- `test_file_diff_missing_file_returns_error`

#### `TestShowDiffFunction`

- `test_function_returns_string`

#### `TestDataTypeDetection`

- `test_numeric_list_detected`
- `test_categorical_dict_detected`
- `test_list_of_dicts_detected_as_tabular`
- `test_list_of_lists_detected_as_tabular`
- `test_string_detected_as_text`
- `test_mixed_dict_detected_as_properties`
- `test_empty_list_returns_unknown`

#### `TestVisualizerAutoVisualize`

- `test_numeric_series_short_returns_chart`
- `test_numeric_series_long_returns_histogram`
- `test_categorical_few_returns_pie`
- `test_categorical_many_returns_bar`
- `test_tabular_returns_table_string`
- `test_text_returns_original`

#### `TestVisualizerForceFormats`

- `test_force_chart`
- `test_force_table`
- `test_force_text_returns_str`

#### `TestVisualizerShowDiff`

- `test_delegates_to_diff_viewer`

#### `TestVisualizerSummaryStats`

- `test_returns_stats_for_numeric_data`
- `test_returns_error_for_non_numeric`
- `test_returns_error_for_empty_data`
- `test_single_element_std_dev_zero`

#### `TestVisualizerComparisonTable`

- `test_empty_items_returns_message`
- `test_returns_table_string`
- `test_respects_compare_keys`

#### `TestGetVisualizer`

- `test_returns_visualizer_instance`

#### `TestZenusVisualizationVisualizer`

- `test_visualize_dict_simple`
- `test_visualize_list_of_dicts`
- `test_visualize_list_of_strings`
- `test_visualize_empty_list`
- `test_visualize_string_with_context`
- `test_visualize_process_list_string`
- `test_visualize_json_string`
- `test_visualize_key_value_multiline`
- `test_visualize_percentage_string`
- `test_visualize_complex_dict`
- `test_visualize_other_type`

### [unit/test_world_model.py](../tests/unit/test_world_model.py) — 37 tests


#### `TestWorldModelInit`

- `test_default_storage_path`
- `test_custom_storage_path`
- `test_fresh_model_has_default_structure`
- `test_loads_existing_file`
- `test_falls_back_to_default_on_corrupt_file`

#### `TestSave`

- `test_save_creates_file`
- `test_save_updates_last_updated`
- `test_save_creates_parent_directories`
- `test_saved_data_is_valid_json`

#### `TestFrequentPaths`

- `test_add_new_frequent_path`
- `test_add_frequent_path_increments_existing`
- `test_add_frequent_path_expands_tilde`
- `test_update_path_frequency_is_alias`
- `test_get_frequent_paths_sorted_by_count`
- `test_get_frequent_paths_respects_limit`
- `test_get_frequent_paths_empty`
- `test_add_frequent_path_persists_to_disk`

#### `TestPreferences`

- `test_set_and_get_preference`
- `test_get_missing_preference_returns_none`
- `test_get_missing_preference_with_default`
- `test_overwrite_preference`
- `test_preference_persists_to_disk`

#### `TestPatterns`

- `test_add_new_pattern`
- `test_add_duplicate_pattern_increments_occurrences`
- `test_add_distinct_patterns`
- `test_pattern_has_first_seen_field`
- `test_patterns_persist_to_disk`
- `test_get_patterns_empty`

#### `TestApplications`

- `test_register_and_find_application`
- `test_register_application_with_category`
- `test_register_application_without_category`
- `test_find_missing_application_returns_none`
- `test_overwrite_application`
- `test_application_persists_to_disk`

#### `TestGetSummary`

- `test_summary_is_string`
- `test_summary_contains_counts`
- `test_summary_contains_last_updated`

---

## Integration Tests (143 tests)


### [integration/test_concurrency.py](../tests/integration/test_concurrency.py) — 23 tests


#### `TestParallelExecutionCorrectness`

- `test_results_count_matches_steps`
- `test_results_are_correct_values`
- `test_each_step_executed_exactly_once`
- `test_sequential_and_parallel_same_result`

#### `TestParallelThreadSafety`

- `test_concurrent_steps_do_not_corrupt_shared_list`
- `test_parallel_execution_is_faster_than_sequential`

#### `TestParallelFailureHandling`

- `test_failed_step_does_not_prevent_sibling_steps`
- `test_all_failing_steps_return_error_strings_or_none`
- `test_sequential_path_propagates_exception`

#### `TestResourceLimiterThrottling`

- `test_io_limit_blocks_fileops_at_cap`
- `test_io_limit_allows_after_release`
- `test_acquire_release_balance`
- `test_release_does_not_go_negative`
- `test_non_io_tool_always_allowed_regardless_of_count`
- `test_network_ops_counted_as_io`
- `test_custom_limits_respected`

#### `TestParallelRealFileOps`

- `test_two_file_scans_in_parallel_both_succeed`
- `test_parallel_system_ops_complete`

#### `TestShouldUseParallel`

- `test_single_step_always_sequential`
- `test_not_parallelizable_returns_false`
- `test_low_speedup_returns_false`
- `test_good_speedup_returns_true`
- `test_empty_steps_returns_false`

### [integration/test_git_ops.py](../tests/integration/test_git_ops.py) — 14 tests


#### `TestGitOps`

- `test_status`
- `test_status_with_changes`
- `test_diff`
- `test_log`
- `test_branch_list`
- `test_branch_create`
- `test_add_files`
- `test_add_all`
- `test_commit`
- `test_commit_without_changes`
- `test_stash`
- `test_checkout_branch`

#### `TestGitOpsPerformance`

- `test_status_fast`
- `test_log_fast`

### [integration/test_llm_deepseek.py](../tests/integration/test_llm_deepseek.py) — 26 tests


#### `TestExtractJson`

- `test_plain_json`
- `test_markdown_json_fence`
- `test_plain_code_fence`
- `test_json_with_surrounding_text`
- `test_no_json_raises`
- `test_invalid_json_raises`
- `test_nested_object`

#### `TestDeepSeekCredentials`

- `test_missing_api_key_raises`
- `test_api_key_with_quotes_stripped`

#### `TestDeepSeekTranslateIntent`

- `test_returns_intentir_instance`
- `test_goal_is_non_empty_string`
- `test_steps_is_list`
- `test_each_step_has_tool_and_action`
- `test_risk_is_within_bounds`
- `test_requires_confirmation_is_bool`
- `test_args_is_dict`
- `test_file_command_uses_fileops_or_similar`
- `test_step_count_is_reasonable`
- `test_pydantic_model_is_valid`
- `test_second_call_returns_fresh_intent`
- `test_bad_response_json_raises_runtime_error`

#### `TestDeepSeekGenerate`

- `test_returns_string`
- `test_responds_to_factual_prompt`
- `test_respects_prompt_content`

#### `TestDeepSeekReflectOnGoal`

- `test_returns_string`
- `test_achieved_goal_says_achieved`

### [integration/test_pipeline_e2e.py](../tests/integration/test_pipeline_e2e.py) — 12 tests


#### `TestOrchestratorWiring`

- `test_dry_run_returns_dry_run_marker`
- `test_execute_returns_string`
- `test_intent_cache_second_call_skips_llm`
- `test_execution_exception_returns_error_message`
- `test_high_risk_step_returns_safety_error_message`
- `test_action_tracker_records_transaction`

#### `TestFullPipelineWithRealLLM`

- `test_system_info_command_returns_string`
- `test_result_is_not_raw_exception`
- `test_dry_run_with_real_llm_returns_plan`
- `test_repeated_command_uses_cache`
- `test_real_llm_produces_valid_intentir`
- `test_file_scan_produces_output`

### [integration/test_provider_contract.py](../tests/integration/test_provider_contract.py) — 20 tests


#### `TestLLMFactory`

- `test_force_deepseek_returns_deepseek`
- `test_missing_provider_raises_environment_error`
- `test_unknown_provider_raises_value_error`
- `test_missing_credentials_raises_environment_error`
- `test_config_provider_takes_effect`

#### `TestGetAvailableProviders`

- `test_deepseek_present_when_key_set`
- `test_anthropic_present_when_key_set`
- `test_deepseek_absent_when_key_missing`
- `test_returns_list`
- `test_no_keys_returns_default`

#### `TestDeepSeekInterfaceCompliance`

- `test_has_translate_intent`
- `test_has_reflect_on_goal`
- `test_has_generate`
- `test_translate_intent_returns_intentir_from_valid_json`
- `test_generate_returns_string`
- `test_reflect_on_goal_non_stream_returns_string`
- `test_translate_intent_bad_json_raises_runtime_error`
- `test_default_model_is_deepseek_chat`
- `test_max_tokens_positive`

#### `TestDeepSeekLiveRoundTrip`

- `test_factory_creates_deepseek_that_can_translate`

### [integration/test_rollback_pipeline.py](../tests/integration/test_rollback_pipeline.py) — 23 tests


#### `TestActionTrackerCore`

- `test_start_transaction_returns_id`
- `test_end_transaction_updates_status`
- `test_track_action_returns_id`
- `test_get_transaction_actions_returns_list`
- `test_create_file_action_is_rollbackable`
- `test_delete_file_action_is_not_rollbackable`
- `test_copy_file_action_is_rollbackable`
- `test_move_file_action_is_rollbackable`
- `test_multiple_actions_in_one_transaction`
- `test_unknown_transaction_returns_empty`

#### `TestAnalyzeFeasibility`

- `test_all_rollbackable_actions_are_feasible`
- `test_non_rollbackable_action_marks_infeasible`
- `test_empty_actions_returns_feasible`

#### `TestRollbackRealFilesystem`

- `test_create_file_rollback_removes_file`
- `test_copy_file_rollback_removes_copy`
- `test_move_file_rollback_moves_back`
- `test_multi_step_rollback_reverses_all`
- `test_nonexistent_transaction_raises_rollback_error`
- `test_non_rollbackable_transaction_raises_rollback_error`

#### `TestRollbackDryRun`

- `test_dry_run_does_not_delete_file`
- `test_dry_run_returns_success_true`

#### `TestRollbackLastN`

- `test_rollback_last_1_removes_most_recent_file`
- `test_no_recent_transactions_raises`

### [integration/test_safety_pipeline.py](../tests/integration/test_safety_pipeline.py) — 13 tests


#### `TestSafetyPolicyInPlanner`

- `test_risk_3_raises_safety_error`
- `test_risk_2_is_allowed`
- `test_risk_0_is_allowed`
- `test_multiple_steps_blocked_if_any_has_risk_3`
- `test_safety_error_message_is_descriptive`

#### `TestPrivilegeTierInPlanner`

- `test_shellops_blocked_at_standard_tier`
- `test_shellops_allowed_at_privileged_tier`
- `test_codeexec_blocked_at_standard_tier`
- `test_fileops_allowed_at_standard_tier`

#### `TestSafetyThroughOrchestrator`

- `test_risk3_intent_returns_error_string`
- `test_shellops_at_standard_tier_via_orchestrator`
- `test_privileged_orchestrator_allows_shellops`

#### `TestSafetyWithRealLLM`

- `test_destructive_command_blocked_or_returns_string`

### [integration/test_system_ops.py](../tests/integration/test_system_ops.py) — 12 tests


#### `TestSystemOps`

- `test_check_resource_usage`
- `test_resource_usage_valid_numbers`
- `test_list_processes`
- `test_list_processes_limit`
- `test_list_processes_finds_self`
- `test_disk_usage`
- `test_disk_usage_valid_path`
- `test_disk_usage_invalid_path`
- `test_get_system_info`
- `test_resource_usage_returns_current_state`

#### `TestSystemOpsPerformance`

- `test_check_resource_usage_fast`
- `test_list_processes_reasonable_time`

---

## End-to-End Tests (11 tests)


### [e2e/test_file_workflow.py](../tests/e2e/test_file_workflow.py) — 5 tests


#### `TestFileWorkflows`

- `test_organize_files_by_extension`
- `test_create_project_structure`
- `test_backup_and_restore`
- `test_batch_rename_files`

#### `TestFileWorkflowsPerformance`

- `test_create_many_files_performance`

### [e2e/test_system_monitoring_workflow.py](../tests/e2e/test_system_monitoring_workflow.py) — 6 tests


#### `TestSystemMonitoringWorkflows`

- `test_complete_system_health_check`
- `test_resource_monitoring_over_time`
- `test_identify_high_memory_processes`
- `test_disk_space_analysis`

#### `TestSystemMonitoringPerformance`

- `test_rapid_health_checks`
- `test_complete_monitoring_workflow_fast`

---

## Script Tests (0 tests)

