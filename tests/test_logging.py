r"""Tests for the Karte generation error-handling path.

Originally the test was a copy-and-mutate of a manual debug script
(\`tests/test_logging.py\`): it set ``sys.path`` to a Windows-only
absolute path, ran ``build_karte_json_string(game, raise_on_error=True)``
with a deliberately-broken ``game.root``, then *printed* the result
and asserted on the contents of a fictional ``debug_error.log``. The
test had no actual ``assert`` statements -- it passed as long as the
fixture raised any exception, and produced no real coverage signal.

This rewrite replaces it with two well-scoped unit tests:

- ``test_build_karte_json_string_propagates_karte_generation_error``
  verifies the documented ``raise_on_error=True`` contract: any
  exception inside the build path is wrapped in
  :class:`katrain.core.reports.karte.builder.KarteGenerationError`
  whose ``game_id`` matches the game.

- ``test_build_karte_json_string_swallows_and_returns_error_karte``
  verifies the documented ``raise_on_error=False`` contract: the
  exception is *not* re-raised, the returned string is the error
  karte markdown, and (because the implementation does not log via
  the stdlib logger) we explicitly assert that no log records leak
  out of the call path.

Both tests run against a real (broken) ``MagicMock``-based game
object, exercise the public function, and use ``caplog`` /
``pytest.raises`` for verification -- no filesystem side effects,
no Windows-only paths.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from katrain.core.reports.karte.builder import (
    KARTE_ERROR_CODE_GENERATION_FAILED,
    KarteGenerationError,
    build_karte_json_string,
)


def _broken_game(game_id: str = "test_game_id") -> MagicMock:
    """Return a ``MagicMock`` whose ``root`` access raises on every call.

    ``build_karte_json_string`` -> ``game.build_eval_snapshot()`` ->
    eventually ``game.root.get_property(...)``. We make ``build_eval_snapshot``
    raise directly so the failure is reached as early as possible
    without depending on the full Kifu/SGF module graph.
    """
    game = MagicMock()
    game.game_id = game_id
    game.sgf_filename = "test.sgf"
    game.build_eval_snapshot.side_effect = RuntimeError("Intentional Crash for test")
    # Defensive: if a later refactor defers the read, ``root`` is also
    # rigged to raise so the test stays deterministic.
    type(game).root = PropertyMock(side_effect=RuntimeError("Intentional Crash (root)"))
    return game


class TestBuildKarteJsonStringErrorHandling:
    """``build_karte_json_string`` must honour both error-mode contracts."""

    def test_propagates_karte_generation_error_with_game_id(self, caplog: pytest.LogCaptureFixture) -> None:
        """``raise_on_error=True`` wraps the underlying exception in
        :class:`KarteGenerationError` carrying the offending ``game_id``.
        """
        caplog.set_level("DEBUG")
        game = _broken_game(game_id="propagation_test_game")

        with pytest.raises(KarteGenerationError) as excinfo:
            build_karte_json_string(game, raise_on_error=True)

        # The wrapped exception must carry the game's id verbatim
        # so downstream callers can surface it to the user.
        assert excinfo.value.game_id == "propagation_test_game"
        # The original RuntimeError must be chained for traceback
        # analysis (PEP 3134 / ``raise ... from ...``).
        assert isinstance(excinfo.value.__cause__, RuntimeError)
        assert "Intentional Crash" in str(excinfo.value.__cause__)
        # The error karte sentinel must be present in the message.
        assert KARTE_ERROR_CODE_GENERATION_FAILED in str(excinfo.value)

    def test_swallows_and_returns_error_karte_markdown(self, caplog: pytest.LogCaptureFixture) -> None:
        """``raise_on_error=False`` returns the error-karte markdown
        and does not raise.

        We also assert that the implementation does not log via the
        stdlib ``logging`` module -- historically the test asserted
        against a fake ``debug_error.log`` file that does not exist
        anywhere in the codebase. Pinning the absence of log records
        keeps that behaviour honest.
        """
        caplog.set_level("DEBUG")
        game = _broken_game(game_id="swallow_test_game")

        with caplog.at_level("DEBUG", logger="katrain.core.reports.karte.builder"):
            result = build_karte_json_string(game, raise_on_error=False)

        # Sanity: no exception escaped; result is a non-empty string.
        assert isinstance(result, str)
        assert result.strip()
        # Error-karte marker is present so the UI can render the
        # failure state rather than treat the empty string as a
        # successful report.
        assert KARTE_ERROR_CODE_GENERATION_FAILED in result
        assert "swallow_test_game" in result or KARTE_ERROR_CODE_GENERATION_FAILED in result
        # No log records should be emitted by the build path itself.
        # ``caplog.records`` contains any record produced under the
        # captured logger; asserting it is empty ensures future
        # refactors do not silently introduce a file logger.
        builder_records = [record for record in caplog.records if record.name == "katrain.core.reports.karte.builder"]
        assert builder_records == [], (
            "build_karte_json_string should not emit log records via "
            "the 'katrain.core.reports.karte.builder' logger; got: "
            f"{[r.getMessage() for r in builder_records]}"
        )
