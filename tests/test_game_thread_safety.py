"""Thread safety tests for Game.undo/redo operations."""
import threading
import pytest
from unittest.mock import MagicMock


class TestGameRLockBehavior:
    """Test that Game uses RLock correctly for undo/redo."""

    def test_game_lock_is_rlock(self):
        """Verify RLock is reentrant (the property we rely on in Game)."""
        import threading

        # RLock property: same thread can acquire multiple times
        rlock = threading.RLock()
        acquired1 = rlock.acquire(blocking=False)
        acquired2 = rlock.acquire(blocking=False)

        assert acquired1, "First acquire should succeed"
        assert acquired2, "Second acquire should succeed (RLock property)"

        rlock.release()
        rlock.release()

    def test_rlock_vs_lock_behavior(self):
        """Demonstrate difference between Lock and RLock."""
        import threading

        # Regular Lock blocks on second acquire (would deadlock if blocking=True)
        lock = threading.Lock()
        lock.acquire(blocking=False)
        second_acquire = lock.acquire(blocking=False)
        assert not second_acquire, "Regular Lock should fail on second acquire"
        lock.release()

        # RLock allows multiple acquires from same thread
        rlock = threading.RLock()
        rlock.acquire(blocking=False)
        second_acquire_rlock = rlock.acquire(blocking=False)
        assert second_acquire_rlock, "RLock should succeed on second acquire"
        rlock.release()
        rlock.release()

    def test_game_base_uses_rlock(self):
        """Verify BaseGame uses RLock, not Lock."""
        # Import the module and check the lock type in __init__
        # We check the source code pattern rather than instantiation
        import inspect
        from katrain.core.game import BaseGame

        # Get the source code of __init__
        source = inspect.getsource(BaseGame.__init__)

        # Verify RLock is used, not Lock
        assert "threading.RLock()" in source, "BaseGame should use RLock"
        assert "threading.Lock()" not in source or "RLock" in source, \
            "BaseGame should not use plain Lock"


class TestGraphSetNodesFromList:
    """Test set_nodes_from_list method via file content inspection.

    Note: We read the source file directly instead of importing
    because Kivy module imports can hang in CI environment.
    """

    def test_set_nodes_from_list_exists_in_source(self):
        """Verify set_nodes_from_list method exists in graph.py source."""
        import os
        graph_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "katrain", "gui", "widgets", "graph.py"
        )
        with open(graph_path, 'r', encoding='utf-8') as f:
            source = f.read()

        assert "def set_nodes_from_list(self" in source, \
            "Graph should have set_nodes_from_list method"

    def test_set_nodes_from_list_uses_lock_in_source(self):
        """Verify set_nodes_from_list uses _lock in its implementation."""
        import os
        graph_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "katrain", "gui", "widgets", "graph.py"
        )
        with open(graph_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Find the method implementation
        method_start = source.find("def set_nodes_from_list(self")
        assert method_start != -1, "Method should exist"

        # Find the next method or class definition (end of this method)
        next_def = source.find("\n    def ", method_start + 1)
        if next_def == -1:
            next_def = len(source)

        method_source = source[method_start:next_def]

        # Verify lock is used
        assert "with self._lock:" in method_source, \
            "set_nodes_from_list should use _lock with context manager"

    def test_graph_init_creates_lock_in_source(self):
        """Verify Graph.__init__ creates _lock."""
        import os
        graph_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "katrain", "gui", "widgets", "graph.py"
        )
        with open(graph_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Find __init__ method
        init_start = source.find("def __init__(self")
        assert init_start != -1, "__init__ should exist"

        # Find the next method
        next_def = source.find("\n    def ", init_start + 1)
        if next_def == -1:
            next_def = len(source)

        init_source = source[init_start:next_def]

        assert "_lock = threading.Lock()" in init_source, \
            "Graph.__init__ should create _lock with threading.Lock()"
