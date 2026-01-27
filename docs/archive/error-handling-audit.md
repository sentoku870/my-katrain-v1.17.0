# Error Handling Audit - Phase 77

## Summary

| Metric | Count |
|--------|-------|
| Total handlers | 108 |
| Intentional (noqa or justified) | 39 |
| Improvement targets | 69 |
| By pattern: except Exception | 108 |

## Audit Table

| id | file | line | context | pattern | category | behavior | risk | intent | action | notes |
|----|------|------|---------|---------|----------|----------|------|--------|--------|-------|
| 1 | katrain/__main__.py | 446 | KaTrainGui.set_analysis_focus_toggle | except Exception | ui-state-restore | log-and-continue | low | improve | add-specific-catch |  |
| 2 | katrain/__main__.py | 472 | KaTrainGui.restore_last_mode | except Exception | ui-state-restore | log-and-continue | low | improve | add-specific-catch |  |
| 3 | katrain/__main__.py | 532 | KaTrainGui.start | except Exception | ui-state-restore | silent-ignore | low | intentional | none |  |
| 4 | katrain/__main__.py | 754 | KaTrainGui._message_loop_thread | except Exception | thread-exception | user-notify | low | intentional | none |  |
| 5 | katrain/__main__.py | 1245 | KaTrainApp.is_valid_window_position | except Exception | ui-state-restore | fallback-value | low | intentional | none |  |
| 6 | katrain/__main__.py | 1289 | KaTrainApp.build | except Exception | ui-state-restore | fallback-value | low | intentional | none |  |
| 7 | katrain/common/file_opener.py | 53 | open_folder | except Exception | external-lib | log-and-continue | low | intentional | none |  |
| 8 | katrain/common/file_opener.py | 82 | open_file | except Exception | external-lib | log-and-continue | low | intentional | none |  |
| 9 | katrain/common/file_opener.py | 111 | open_file_in_folder | except Exception | external-lib | log-and-continue | low | intentional | none |  |
| 10 | katrain/common/settings_export.py | 259 | atomic_save_config | except Exception | ui-state-restore | user-notify | medium | improve | add-specific-catch |  |
| 11 | katrain/core/base_katrain.py | 86 | _save_config_with_errors | except Exception | file-io-fallback | log-and-continue | low | intentional | none | must continue saving other sections |
| 12 | katrain/core/base_katrain.py | 171 | KaTrainBase._load_config | except Exception | file-io-fallback | fallback-value | low | intentional | none | config version parse may fail in many ways |
| 13 | katrain/core/base_katrain.py | 186 | KaTrainBase._load_config | except Exception | file-io-fallback | fallback-value | low | intentional | none | config setup may fail in many ways, fallback to package |
| 14 | katrain/core/base_katrain.py | 194 | KaTrainBase._load_config | except Exception | file-io-fallback | fallback-value | low | intentional | none | config load failure is fatal, log and exit |
| 15 | katrain/core/batch/analysis.py | 151 | analyze_single_file | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 16 | katrain/core/batch/analysis.py | 390 | analyze_single_file_leela | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 17 | katrain/core/batch/helpers.py | 260 | safe_write_file | except Exception | file-io-fallback | log-and-continue | low | intentional | none |  |
| 18 | katrain/core/batch/helpers.py | 303 | read_sgf_with_fallback | except Exception | file-io-fallback | log-and-continue | low | intentional | none |  |
| 19 | katrain/core/batch/helpers.py | 366 | parse_sgf_with_fallback | except Exception | file-io-fallback | log-and-continue | low | intentional | none |  |
| 20 | katrain/core/batch/helpers.py | 393 | has_analysis | except Exception | file-io-fallback | log-and-continue | low | intentional | none |  |
| 21 | katrain/core/batch/orchestration.py | 351 | run_batch | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 22 | katrain/core/batch/orchestration.py | 376 | run_batch | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 23 | katrain/core/batch/orchestration.py | 458 | run_batch | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 24 | katrain/core/batch/orchestration.py | 495 | run_batch | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 25 | katrain/core/batch/stats/extraction.py | 261 | extract_game_stats | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 26 | katrain/core/batch/stats/extraction.py | 276 | extract_game_stats | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 27 | katrain/core/batch/stats/extraction.py | 288 | extract_game_stats | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 28 | katrain/core/curator/batch.py | 261 | generate_curator_outputs | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 29 | katrain/core/curator/batch.py | 281 | generate_curator_outputs | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 30 | katrain/core/curator/batch.py | 301 | generate_curator_outputs | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 31 | katrain/core/diagnostics.py | 275 | create_diagnostics_zip | except Exception | external-lib | fallback-value | low | improve | add-specific-catch |  |
| 32 | katrain/core/engine.py | 393 | KataGoEngine._safe_queue_put | except Exception | shutdown-cleanup | log-and-continue | low | intentional | none | shutdown cleanup, must continue |
| 33 | katrain/core/engine.py | 406 | KataGoEngine._safe_terminate | except Exception | shutdown-cleanup | log-and-continue | low | intentional | none | shutdown cleanup, must continue |
| 34 | katrain/core/engine.py | 426 | KataGoEngine._safe_close_pipes | except Exception | shutdown-cleanup | log-and-continue | low | intentional | none | shutdown cleanup, must continue |
| 35 | katrain/core/engine.py | 464 | KataGoEngine._safe_force_kill | except Exception | shutdown-cleanup | log-and-continue | low | intentional | none | shutdown cleanup, must continue |
| 36 | katrain/core/engine.py | 518 | KataGoEngine._read_stderr_thread | except Exception | thread-exception | log-and-exit | low | intentional | none | thread exception, must log and continue |
| 37 | katrain/core/engine.py | 529 | KataGoEngine._read_stderr_thread | except Exception | thread-exception | log-and-exit | low | intentional | none | thread exception, must log and exit gracefully |
| 38 | katrain/core/engine.py | 556 | KataGoEngine._analysis_read_thread | except Exception | thread-exception | log-and-exit | low | intentional | none | thread exception, must log and exit gracefully |
| 39 | katrain/core/engine.py | 633 | KataGoEngine._analysis_read_thread | except Exception | callback-protection | log-and-continue | low | intentional | none | callback exception, must log and continue |
| 40 | katrain/core/engine.py | 640 | KataGoEngine._analysis_read_thread | except Exception | thread-exception | log-and-exit | low | intentional | none | thread exception, must log and continue processing |
| 41 | katrain/core/game.py | 655 | Game.get_important_move_evals | except Exception | file-io-fallback | fallback-value | low | improve | add-specific-catch |  |
| 42 | katrain/core/lang.py | 62 | Lang._notify_change | except Exception | callback-protection | silent-ignore | low | intentional | none |  |
| 43 | katrain/core/leela/engine.py | 180 | LeelaEngine.shutdown | except Exception | shutdown-cleanup | log-and-continue | low | intentional | none | shutdown cleanup |
| 44 | katrain/core/leela/engine.py | 371 | LeelaEngine._run_analysis | except Exception | thread-exception | log-and-continue | low | intentional | none |  |
| 45 | katrain/core/leela/engine.py | 394 | LeelaEngine._run_analysis | except Exception | thread-exception | log-and-continue | low | intentional | none |  |
| 46 | katrain/core/reports/karte/builder.py | 99 | _compute_style_safe | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 47 | katrain/core/reports/karte/builder.py | 171 | build_karte_report | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 48 | katrain/core/reports/karte/builder.py | 294 | _build_karte_report_impl | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 49 | katrain/core/reports/karte/builder.py | 396 | _build_karte_report_impl | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 50 | katrain/core/reports/karte/json_export.py | 194 | build_karte_json | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 51 | katrain/core/reports/karte/sections/important_moves.py | 115 | get_context_info_for_move | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 52 | katrain/core/reports/karte/sections/important_moves.py | 276 | critical_3_section_for | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 53 | katrain/core/reports/karte/sections/metadata.py | 222 | risk_management_section | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 54 | katrain/core/reports/package_export.py | 187 | _is_writable_directory | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 55 | katrain/core/reports/package_export.py | 236 | load_coach_md | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 56 | katrain/core/reports/package_export.py | 344 | create_llm_package | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 57 | katrain/core/sgf_parser.py | 681 | SGF.parse_gib | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 58 | katrain/core/sgf_parser.py | 691 | SGF.parse_gib | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 59 | katrain/core/sgf_parser.py | 705 | SGF.parse_gib | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 60 | katrain/core/smart_kifu/logic.py | 216 | compute_analyzed_ratio_from_sgf_file | except Exception | file-io-fallback | log-and-continue | medium | improve | add-specific-catch |  |
| 61 | katrain/gui/controlspanel.py | 77 | PlayAnalyzeSelect.load_ui_state | except Exception | ui-state-restore | fallback-value | low | improve | add-specific-catch |  |
| 62 | katrain/gui/error_handler.py | 57 | ErrorHandler.handle | except Exception | traceback-format | silent-ignore | low | intentional | none |  |
| 63 | katrain/gui/error_handler.py | 97 | ErrorHandler._handle_impl | except Exception | traceback-format | silent-ignore | low | intentional | none |  |
| 64 | katrain/gui/error_handler.py | 115 | ErrorHandler._handle_impl._notify | except Exception | traceback-format | silent-ignore | low | intentional | none |  |
| 65 | katrain/gui/error_handler.py | 128 | ErrorHandler._fallback_log | except Exception | traceback-format | silent-ignore | low | intentional | none |  |
| 66 | katrain/gui/error_handler.py | 156 | ErrorHandler.safe_call | except Exception | traceback-format | silent-ignore | low | intentional | none |  |
| 67 | katrain/gui/features/batch_core.py | 289 | run_batch_in_thread | except Exception | thread-exception | user-notify | low | intentional | none |  |
| 68 | katrain/gui/features/engine_compare_popup.py | 96 | _show_engine_compare_popup_impl | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 69 | katrain/gui/features/karte_export.py | 188 | do_export_karte_ui | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 70 | katrain/gui/features/package_export_ui.py | 79 | _do_export_package_impl | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 71 | katrain/gui/features/package_export_ui.py | 86 | _do_export_package_impl | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 72 | katrain/gui/features/settings_popup.py | 202 | _do_export_settings | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 73 | katrain/gui/features/settings_popup.py | 253 | _do_import_settings | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 74 | katrain/gui/features/settings_popup.py | 286 | _do_import_settings | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 75 | katrain/gui/features/settings_popup.py | 293 | _do_import_settings | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 76 | katrain/gui/features/settings_popup.py | 1196 | do_mykatrain_settings_popup.save_settings | except Exception | ui-state-restore | user-notify | medium | improve | add-specific-catch |  |
| 77 | katrain/gui/features/skill_radar_popup.py | 61 | _show_impl | except Exception | ui-state-restore | fallback-value | low | improve | add-specific-catch |  |
| 78 | katrain/gui/features/skill_radar_popup.py | 91 | _show_impl | except Exception | ui-state-restore | fallback-value | low | improve | add-specific-catch |  |
| 79 | katrain/gui/features/smart_kifu_training_set.py | 303 | show_create_training_set_dialog.on_create | except Exception | file-io-fallback | log-and-continue | medium | improve | add-specific-catch |  |
| 80 | katrain/gui/features/smart_kifu_training_set.py | 521 | show_import_sgf_dialog.on_import.import_thread | except Exception | thread-exception | user-notify | low | intentional | none |  |
| 81 | katrain/gui/features/summary_aggregator.py | 49 | scan_player_names | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 82 | katrain/gui/features/summary_io.py | 98 | save_summaries_per_player | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 83 | katrain/gui/features/summary_io.py | 184 | save_categorized_summaries_from_stats | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 84 | katrain/gui/features/summary_io.py | 243 | save_summary_file | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 85 | katrain/gui/features/summary_io.py | 252 | save_summary_file | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 86 | katrain/gui/features/summary_stats.py | 63 | extract_analysis_from_sgf_node | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 87 | katrain/gui/features/summary_stats.py | 247 | extract_sgf_statistics | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 88 | katrain/gui/features/summary_stats.py | 285 | extract_sgf_statistics | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 89 | katrain/gui/features/summary_stats.py | 291 | extract_sgf_statistics | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 90 | katrain/gui/features/summary_ui.py | 476 | process_and_export_summary | except Exception | partial-failure | log-and-continue | medium | improve | add-specific-catch |  |
| 91 | katrain/gui/lang_bridge.py | 96 | KivyLangBridge.fbind | except Exception | file-io-fallback | fallback-value | low | improve | add-specific-catch |  |
| 92 | katrain/gui/lang_bridge.py | 124 | KivyLangBridge._notify_observers | except Exception | callback-protection | silent-ignore | low | intentional | none |  |
| 93 | katrain/gui/leela_manager.py | 103 | LeelaManager.start_engine | except Exception | thread-exception | log-and-continue | low | intentional | none |  |
| 94 | katrain/gui/leela_manager.py | 113 | LeelaManager.shutdown_engine | except Exception | shutdown-cleanup | log-and-continue | low | intentional | none |  |
| 95 | katrain/gui/popups.py | 245 | QuickConfigGui.collect_properties | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 96 | katrain/gui/popups.py | 294 | QuickConfigGui._set_properties_subtree | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 97 | katrain/gui/popups.py | 684 | BaseConfigPopup._download_models.download_complete | except Exception | external-lib | log-and-continue | medium | improve | add-specific-catch |  |
| 98 | katrain/gui/popups.py | 705 | BaseConfigPopup._download_models | except Exception | external-lib | log-and-continue | medium | improve | add-specific-catch |  |
| 99 | katrain/gui/popups.py | 768 | BaseConfigPopup.download_katas.download_complete | except Exception | external-lib | log-and-continue | medium | improve | add-specific-catch |  |
| 100 | katrain/gui/popups.py | 775 | BaseConfigPopup.download_katas.download_complete | except Exception | external-lib | log-and-continue | medium | improve | add-specific-catch |  |
| 101 | katrain/gui/sgf_manager.py | 120 | SGFManager.load_sgf_from_clipboard | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 102 | katrain/gui/sgf_manager.py | 153 | SGFManager.save_game | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 103 | katrain/gui/sgf_manager.py | 160 | SGFManager.open_recent_sgf | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 104 | katrain/gui/sgf_manager.py | 176 | SGFManager.open_recent_sgf | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 105 | katrain/gui/sgf_manager.py | 254 | SGFManager._show_recent_sgf_dropdown | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |
| 106 | katrain/gui/sound.py | 12 | <module> | except Exception | external-lib | silent-ignore | low | intentional | none |  |
| 107 | katrain/gui/widgets/radar_chart.py | 150 | RadarChartWidget._do_redraw | except Exception | ui-state-restore | fallback-value | low | improve | add-specific-catch |  |
| 108 | katrain/tools/batch_analyze_sgf.py | 197 | main | except Exception | file-io-fallback | user-notify | medium | improve | add-specific-catch |  |

## Category Summary

### partial-failure (34 entries)
Exception handlers in batch processing. Allow partial success when processing multiple items.

### file-io-fallback (30 entries)
Exception handlers for file I/O operations. Mix of intentional (config) and improvement targets.

### ui-state-restore (11 entries)
Exception handlers for UI state restoration. Safe to fail with fallback values.

### thread-exception (10 entries)
Exception handlers in thread contexts. Most are intentional to prevent thread crashes.

### external-lib (9 entries)
Exception handlers for external library calls. Protect against external failures.

### shutdown-cleanup (6 entries)
Exception handlers during shutdown/cleanup. Intentional to ensure cleanup completes.

### traceback-format (5 entries)
Exception handlers in error handler itself. Must not throw to prevent cascading failures.

### callback-protection (3 entries)
Exception handlers protecting callback callers. Intentional to prevent crash propagation.

## Phase 78/79 Recommendations

### High Priority (Phase 78) - User-facing paths
- File I/O operations that notify users should use specific exceptions (FileNotFoundError, PermissionError)
- SGF parsing errors should catch specific sgf_parser exceptions
- Settings import/export should validate data before processing

### Medium Priority (Phase 79) - Background paths
- Batch processing should differentiate between recoverable and fatal errors
- Report generation should use specific exceptions for different failure modes
- Curator operations should have clearer error categories

