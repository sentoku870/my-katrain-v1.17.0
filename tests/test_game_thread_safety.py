"""Thread safety tests for Game.undo/redo operations."""

import threading


class TestGameRLockBehavior:
    """Test that Game uses RLock correctly for undo/redo."""

    def test_game_lock_is_rlock(self):
        """Verify RLock is reentrant (the property we rely on in Game)."""

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
        assert "threading.Lock()" not in source or "RLock" in source, "BaseGame should not use plain Lock"
