"""Phase 68: Command pattern unit tests (v6).

Comprehensive tests for AnalysisCommand, StandardAnalysisCommand, and CommandExecutor.
"""

import threading
import time
from unittest.mock import MagicMock

import pytest


# ======== Helpers ========


def create_mock_node():
    """Create a properly configured mock GameNode."""
    node = MagicMock()
    node.komi = 6.5
    node.ruleset = "japanese"
    node.initial_player = "B"
    node.next_player = "B"
    node.board_size = (19, 19)
    node.nodes_from_root = [node]
    node.moves = []
    node.placements = []
    node.analysis = {"moves": {}}
    return node


# ======== Fixtures ========


@pytest.fixture
def mock_game_node():
    """Create a mock GameNode for testing."""
    return create_mock_node()


@pytest.fixture
def mock_engine():
    """Create a mock KataGoEngine for testing."""
    engine = MagicMock()
    engine.config = {
        "max_visits": 100,
        "fast_visits": 50,
        "_enable_ownership": True,
        "wide_root_noise": 0.0,
        "max_time": 5.0,
    }
    engine.base_priority = 0
    engine.override_settings = {"reportAnalysisWinratesAs": "BLACK"}
    engine.get_rules = MagicMock(return_value="japanese")
    engine.send_query = MagicMock()
    engine.terminate_query = MagicMock()
    engine.PONDER_KEY = "_kt_continuous"
    return engine


# ======== Issue 1: commands dict invariant ========


class TestCommandsInvariant:
    """commands dict must contain only ACTIVE commands."""

    def test_commands_empty_after_all_completed(self, mock_engine):
        """All commands completed should leave commands dict empty."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        num_commands = 10

        for i in range(num_commands):
            cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)
            executor.submit(cmd)
            callback_wrapper = mock_engine.send_query.call_args[0][1]
            # Complete the command
            callback_wrapper({"id": f"QUERY:{i}", "moveInfos": []}, False)

        assert len(executor.commands) == 0
        assert len(executor._pending_commands) == 0
        assert len(executor.history) == num_commands

    def test_commands_contains_only_active(self, mock_engine):
        """commands should only contain active (executing) commands."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)

        cmd1 = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)
        cmd2 = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd1)
        executor.submit(cmd2)

        cb1 = mock_engine.send_query.call_args_list[0][0][1]
        cb2 = mock_engine.send_query.call_args_list[1][0][1]

        # cmd1: partial result (executing)
        cb1({"id": "QUERY:1", "moveInfos": []}, True)
        # cmd2: final result (completed)
        cb2({"id": "QUERY:2", "moveInfos": []}, False)

        assert "QUERY:1" in executor.commands
        assert "QUERY:2" not in executor.commands  # completed, removed

    def test_error_removes_from_commands(self, mock_engine):
        """Error should also remove from commands."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]
        err = mock_engine.send_query.call_args[0][2]

        # First get query_id
        cb({"id": "QUERY:1", "moveInfos": []}, True)
        assert "QUERY:1" in executor.commands

        # Then error
        err({"id": "QUERY:1", "error": "test"})
        assert "QUERY:1" not in executor.commands


# ======== Issue 2: Results without query_id ========


class TestResultsWithoutId:
    """Results without query_id should be ignored."""

    def test_result_without_id_ignored(self, mock_engine):
        """Result without id should not call callback."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        callback_calls = []
        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            callback=lambda a, p: callback_calls.append((a, p)),
        )

        executor.submit(cmd)
        callback_wrapper = mock_engine.send_query.call_args[0][1]

        # Result without id
        callback_wrapper({"moveInfos": []}, True)

        assert len(callback_calls) == 0
        assert cmd in executor._pending_commands
        assert cmd.status == "pending"

    def test_result_with_id_processes_normally(self, mock_engine):
        """Result with id should process normally."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        callback_calls = []
        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            callback=lambda a, p: callback_calls.append((a, p)),
        )

        executor.submit(cmd)
        callback_wrapper = mock_engine.send_query.call_args[0][1]

        # Result with id
        callback_wrapper({"id": "QUERY:1", "moveInfos": []}, True)

        assert len(callback_calls) == 1
        assert cmd not in executor._pending_commands
        assert "QUERY:1" in executor.commands


# ======== Issue 3: error_wrapper cleanup ========


class TestErrorCleanup:
    """error_wrapper should clean up properly."""

    def test_error_without_id_uses_command_query_id(self, mock_engine):
        """Error without id should use command.query_id for cleanup."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]
        err = mock_engine.send_query.call_args[0][2]

        # Get query_id first
        cb({"id": "QUERY:1", "moveInfos": []}, True)
        assert cmd.query_id == "QUERY:1"

        # Error without id
        err({"error": "No id"})

        assert "QUERY:1" not in executor.commands
        assert cmd.status == "failed"

    def test_error_for_pending_command_cleans_up(self, mock_engine):
        """Error for pending command should clean up."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        err = mock_engine.send_query.call_args[0][2]

        # Error while still pending
        err({"error": "Immediate error"})

        assert cmd not in executor._pending_commands
        assert cmd.status == "failed"


# ======== Issue 4: Early cancel before send_query ========


class TestEarlyCancel:
    """Cancel during/after prepare should skip send_query."""

    def test_cancel_during_prepare_skips_send(self, mock_engine):
        """Cancel during prepare() should skip send_query."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)

        prepare_started = threading.Event()
        prepare_continue = threading.Event()

        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)
        original_prepare = cmd.prepare

        def slow_prepare():
            prepare_started.set()
            prepare_continue.wait(timeout=2.0)
            return original_prepare()

        cmd.prepare = slow_prepare

        def do_submit():
            executor.submit(cmd)

        def do_cancel():
            prepare_started.wait(timeout=2.0)
            executor.cancel_command(cmd)
            prepare_continue.set()

        t1 = threading.Thread(target=do_submit)
        t2 = threading.Thread(target=do_cancel)

        t1.start()
        t2.start()
        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        assert not mock_engine.send_query.called
        assert cmd.status == "cancelled"

    def test_cancelled_command_not_sent(self, mock_engine):
        """Pre-cancelled command should not be sent."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        # Pre-cancel
        cmd.mark_cancelled()
        cmd.status = "cancelled"

        executor.submit(cmd)

        assert not mock_engine.send_query.called


# ======== Issue 5: PONDER_KEY single ownership ========


class TestPonderKey:
    """PONDER_KEY should be set only by executor."""

    def test_ponder_key_set_exactly_once(self, mock_engine):
        """PONDER_KEY should be set exactly once by executor."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        # prepare() should NOT set PONDER_KEY
        prepared = cmd.prepare()
        assert "_kt_continuous" not in prepared

        executor.submit(cmd)

        # executor should set it
        query = mock_engine.send_query.call_args[0][0]
        assert "_kt_continuous" in query
        assert query["_kt_continuous"] is True

    def test_prepare_never_sets_ponder_key(self, mock_engine):
        """prepare() should never set PONDER_KEY."""
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        for _ in range(3):
            query = cmd.prepare()
            assert "_kt_continuous" not in query


# ======== Hashability ========


class TestHashability:
    """Commands must be hashable for Set membership."""

    def test_command_hashable(self):
        """Commands should be hashable (eq=False)."""
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        cmd1 = StandardAnalysisCommand(node=MagicMock())
        cmd2 = StandardAnalysisCommand(node=MagicMock())

        s = set()
        s.add(cmd1)
        s.add(cmd2)
        assert len(s) == 2

    def test_same_attributes_different_instances(self):
        """Same attributes should still be different commands."""
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        node = MagicMock()
        cmd1 = StandardAnalysisCommand(node=node)
        cmd2 = StandardAnalysisCommand(node=node)

        assert cmd1 is not cmd2
        assert hash(cmd1) != hash(cmd2)


# ======== Cancel Flag ========


class TestCancelFlag:
    """Cancel flag behavior tests."""

    def test_cancel_completed_no_flag_change(self, mock_engine):
        """Cancelling completed command should not set flag."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]
        cb({"id": "QUERY:1", "moveInfos": []}, False)  # Complete

        result = executor.cancel_command(cmd)

        assert result is False
        assert not cmd.is_cancelled()

    def test_cancel_success_sets_flag(self, mock_engine):
        """Successful cancel should set flag."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        result = executor.cancel_command(cmd)

        assert result is True
        assert cmd.is_cancelled()


# ======== clear_all ========


class TestClearAll:
    """clear_all behavior tests."""

    def test_clear_all_preserves_completed_flag(self, mock_engine):
        """clear_all should not set cancelled flag on completed."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]
        cb({"id": "QUERY:1", "moveInfos": []}, False)  # Complete

        executor.clear_all()

        assert cmd.status == "completed"
        assert not cmd.is_cancelled()

    def test_clear_all_cancels_pending(self, mock_engine):
        """clear_all should cancel pending commands."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        executor.clear_all()

        assert cmd.status == "cancelled"
        assert cmd.is_cancelled()


# ======== Status Transitions ========


class TestStatusTransitions:
    """Status transition tests."""

    def test_no_results_keeps_pending(self, mock_engine):
        """noResults should not transition status."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        # noResults is ignored by on_result (returns False)
        cb({"id": "QUERY:1", "noResults": True}, True)

        # Status doesn't change because on_result returned False
        assert cmd.status == "pending"

    def test_partial_transitions_to_executing(self, mock_engine):
        """Partial result should transition to executing."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        cb({"id": "QUERY:1", "moveInfos": []}, True)

        assert cmd.status == "executing"

    def test_final_transitions_to_completed(self, mock_engine):
        """Final result should transition to completed."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        cb({"id": "QUERY:1", "moveInfos": []}, False)

        assert cmd.status == "completed"


# ======== Concurrency ========


class TestConcurrency:
    """Concurrency tests using Barrier."""

    def test_concurrent_submits_no_data_corruption(self, mock_engine):
        """Concurrent submits should not corrupt data."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        num_threads = 20
        barrier = threading.Barrier(num_threads)
        commands = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=2.0)
                cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)
                executor.submit(cmd)
                commands.append(cmd)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0
        assert mock_engine.send_query.call_count == num_threads

    def test_concurrent_cancel_and_result(self, mock_engine):
        """Cancel and result should not corrupt state."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        barrier = threading.Barrier(2)
        errors = []

        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)
        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        def do_cancel():
            try:
                barrier.wait(timeout=2.0)
                executor.cancel_command(cmd)
            except Exception as e:
                errors.append(e)

        def do_result():
            try:
                barrier.wait(timeout=2.0)
                cb({"id": "QUERY:1", "moveInfos": []}, False)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=do_cancel)
        t2 = threading.Thread(target=do_result)

        t1.start()
        t2.start()
        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        assert len(errors) == 0
        # Either cancelled or completed, but state is consistent
        assert cmd.status in ("cancelled", "completed")


# ======== Backward Compatibility ========


class TestBackwardCompatibility:
    """Backward compatibility tests."""

    def test_callback_signature_preserved(self):
        """Callback should receive (analysis, partial)."""
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        received = []
        cmd = StandardAnalysisCommand(
            node=MagicMock(),
            callback=lambda a, p: received.append((a, p)),
        )
        cmd.status = "executing"

        cmd.on_result({"moveInfos": []}, partial=True)

        assert received == [({"moveInfos": []}, True)]

    def test_error_callback_signature_preserved(self):
        """Error callback should receive (error)."""
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        received = []
        cmd = StandardAnalysisCommand(
            node=MagicMock(),
            error_callback=lambda e: received.append(e),
        )

        cmd.on_error({"error": "test"})

        assert received == [{"error": "test"}]

    def test_ignore_results_by_query_id(self, mock_engine):
        """ignore_results should work by query_id."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]
        cb({"id": "QUERY:1", "moveInfos": []}, True)

        result = executor.ignore_results("QUERY:1")

        assert result is True
        assert cmd.is_cancelled()

    def test_terminate_by_query_id(self, mock_engine):
        """terminate should work by query_id."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]
        cb({"id": "QUERY:1", "moveInfos": []}, True)

        result = executor.terminate("QUERY:1")

        assert result is True
        assert cmd.is_cancelled()
        mock_engine.terminate_query.assert_called_once_with(
            "QUERY:1", ignore_further_results=True
        )


# ======== History ========


class TestHistory:
    """History management tests."""

    def test_history_limited_by_maxlen(self, mock_engine):
        """History should be limited by maxlen."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)

        # Submit more than MAX_HISTORY_SIZE
        for i in range(CommandExecutor.MAX_HISTORY_SIZE + 10):
            cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)
            executor.submit(cmd)

        assert len(executor.history) == CommandExecutor.MAX_HISTORY_SIZE

    def test_history_returns_snapshot(self, mock_engine):
        """history property should return a snapshot."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(node=create_mock_node(), engine=mock_engine)
        executor.submit(cmd)

        h1 = executor.history
        h2 = executor.history

        assert h1 is not h2
        assert h1 == h2


# ======== Import ========


class TestImport:
    """Import tests."""

    def test_no_circular_import(self):
        """Package should import without circular import errors."""
        from katrain.core.engine_cmd import (
            AnalysisCommand,
            StandardAnalysisCommand,
            CommandExecutor,
        )

        assert AnalysisCommand is not None
        assert StandardAnalysisCommand is not None
        assert CommandExecutor is not None


# ======== Guard Pattern ========


class TestGuardPattern:
    """Tests for callback guard pattern."""

    def test_callback_can_guard_with_is_cancelled(self, mock_engine):
        """Callback can use is_cancelled() to guard."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        processed = []

        def guarded_callback(analysis, partial):
            # This is the recommended guard pattern
            processed.append(analysis)

        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            callback=guarded_callback,
        )

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        # Get query_id
        cb({"id": "QUERY:1", "moveInfos": []}, True)

        # Cancel
        executor.cancel_command(cmd)

        # Late delivery should be blocked by executor
        cb({"id": "QUERY:1", "moveInfos": []}, False)

        # Only one result should be processed (before cancel)
        assert len(processed) == 1


# ======== Phase 68-C: Pondering ========


class TestPondering:
    """Tests for pondering convenience methods (Phase 68-C)."""

    def test_is_pondering_false_when_no_commands(self, mock_engine):
        """is_pondering should be False when no commands."""
        from katrain.core.engine_cmd.executor import CommandExecutor

        executor = CommandExecutor(mock_engine)

        assert executor.is_pondering is False

    def test_is_pondering_false_for_non_ponder_command(self, mock_engine):
        """is_pondering should be False for regular commands."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=False,
        )

        executor.submit(cmd)

        assert executor.is_pondering is False

    def test_is_pondering_true_for_pending_ponder_command(self, mock_engine):
        """is_pondering should be True for pending ponder command."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)

        # Command is still pending (no callback yet)
        assert cmd in executor._pending_commands
        assert executor.is_pondering is True

    def test_is_pondering_true_for_active_ponder_command(self, mock_engine):
        """is_pondering should be True for active ponder command."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        # Move to active (partial result)
        cb({"id": "QUERY:1", "moveInfos": []}, True)

        assert "QUERY:1" in executor.commands
        assert executor.is_pondering is True

    def test_is_pondering_false_after_ponder_completed(self, mock_engine):
        """is_pondering should be False after ponder command completed."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        # Complete the command
        cb({"id": "QUERY:1", "moveInfos": []}, False)

        assert cmd.status == "completed"
        assert executor.is_pondering is False

    def test_get_ponder_command_returns_none_when_no_ponder(self, mock_engine):
        """get_ponder_command should return None when no pondering."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)

        # No commands
        assert executor.get_ponder_command() is None

        # Regular command
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=False,
        )
        executor.submit(cmd)

        assert executor.get_ponder_command() is None

    def test_get_ponder_command_returns_ponder_command(self, mock_engine):
        """get_ponder_command should return the pondering command."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)

        assert executor.get_ponder_command() is cmd

    def test_get_ponder_command_prefers_pending(self, mock_engine):
        """get_ponder_command should return pending ponder before active."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        executor = CommandExecutor(mock_engine)

        # Submit first ponder command and activate it
        cmd1 = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )
        executor.submit(cmd1)
        cb1 = mock_engine.send_query.call_args[0][1]
        cb1({"id": "QUERY:1", "moveInfos": []}, True)

        # Submit second ponder command (pending)
        cmd2 = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )
        executor.submit(cmd2)

        # Should return pending one first
        result = executor.get_ponder_command()
        assert result is cmd2

    def test_stop_pondering_returns_false_when_no_ponder(self, mock_engine):
        """stop_pondering should return False when no pondering."""
        from katrain.core.engine_cmd.executor import CommandExecutor

        executor = CommandExecutor(mock_engine)

        result = executor.stop_pondering()

        assert result is False

    def test_stop_pondering_cancels_ponder_command(self, mock_engine):
        """stop_pondering should cancel the pondering command."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        # Add stop_pondering to mock engine
        mock_engine.stop_pondering = MagicMock()

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)

        result = executor.stop_pondering()

        assert result is True
        assert cmd.status == "cancelled"
        assert cmd.is_cancelled()
        assert executor.is_pondering is False

    def test_stop_pondering_calls_engine_stop_pondering(self, mock_engine):
        """stop_pondering should call engine.stop_pondering()."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        mock_engine.stop_pondering = MagicMock()

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)
        executor.stop_pondering()

        mock_engine.stop_pondering.assert_called_once()

    def test_stop_pondering_with_terminate_false(self, mock_engine):
        """stop_pondering(terminate=False) should not call terminate_query."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        mock_engine.stop_pondering = MagicMock()

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        # Activate the command
        cb({"id": "QUERY:1", "moveInfos": []}, True)

        # Stop without terminate
        executor.stop_pondering(terminate=False)

        assert cmd.status == "cancelled"
        # terminate_query should not be called
        mock_engine.terminate_query.assert_not_called()

    def test_stop_pondering_with_terminate_true(self, mock_engine):
        """stop_pondering(terminate=True) should call terminate_query."""
        from katrain.core.engine_cmd.executor import CommandExecutor
        from katrain.core.engine_cmd.commands import StandardAnalysisCommand

        mock_engine.stop_pondering = MagicMock()

        executor = CommandExecutor(mock_engine)
        cmd = StandardAnalysisCommand(
            node=create_mock_node(),
            engine=mock_engine,
            ponder=True,
        )

        executor.submit(cmd)
        cb = mock_engine.send_query.call_args[0][1]

        # Activate the command
        cb({"id": "QUERY:1", "moveInfos": []}, True)

        # Stop with terminate (default)
        executor.stop_pondering(terminate=True)

        assert cmd.status == "cancelled"
        # terminate_query should be called
        mock_engine.terminate_query.assert_called_once_with("QUERY:1", ignore_further_results=True)
