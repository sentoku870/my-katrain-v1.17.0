"""PR-05 regression tests for exception-handling symmetry.

PR-05 (H-i): the karte path catches only ``FileNotFoundError`` and
``(JSONDecodeError, KeyError, ValueError)`` — ``TypeError`` (e.g.
wrong schema shape passed to ``build_prompt``) leaks out and the
GUI button appears unresponsive. The summary path uses a single
``except Exception`` that masks every failure (including validator
crashes) as ``summary-build-failed``.

This test pins the new behaviour: the two paths are symmetric, and
the summary path distinguishes build errors from validate errors.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from katrain.gui.features import llm_coach
from katrain.gui.features.llm_coach import validate_summary_llm_response


class TestKarteExceptionSymmetry:
    def test_type_error_is_caught_as_invalid_karte(self) -> None:
        """Karte path: TypeError must surface as 'invalid-karte', not
        crash the GUI thread."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump({"meta": {"schema_version": "3.5"}}, fh)
            path = fh.name
        try:
            with patch(
                "katrain.core.coach.cli.build_prompt",
                side_effect=TypeError("schema shape mismatch"),
            ):
                ok, msg = llm_coach.build_llm_prompt(
                    ctx=None,
                    karte_path=path,
                    rank="5k",
                    player_color=None,
                )
            assert ok is False, "TypeError must not raise out of build_llm_prompt"
            assert msg, "expected non-empty user-facing message"
        finally:
            os.unlink(path)


class TestSummaryValidateSeparateFromBuild:
    def _summary(self) -> dict[str, Any]:
        return {
            "meta": {"schema_version": "3.5"},
            "weaknesses": [],
            "games": [],
        }

    def test_validator_crash_surfaces_as_validate_failed(self) -> None:
        """When the validator raises (but build succeeds), the user
        must see ``summary-validate-failed`` rather than the misleading
        ``summary-build-failed``."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(self._summary(), fh)
            summary_path = fh.name
        try:
            with (
                patch(
                    "katrain.core.coach.summary_prompt_builder.build_summary_weakness_prompt",
                    return_value=MagicMock(),
                ),
                patch(
                    "katrain.core.coach.summary_validator.validate_summary_llm_output",
                    side_effect=RuntimeError("validator boom"),
                ),
            ):
                ok, msg = validate_summary_llm_response(
                    ctx=None,
                    summary_path=summary_path,
                    llm_text="dummy answer body\n",
                    rank="5k",
                    player_name=None,
                )
            assert ok is False
            assert "検証失敗" in msg or "validate-failed" in msg, (
                "validator crash must surface as validate failure, not "
                f"build failure (got {msg!r}). PR-05 (H-i) regression."
            )
            assert "生成失敗" not in msg and "build-failed" not in msg
        finally:
            os.unlink(summary_path)

    def test_build_crash_surfaces_as_build_failed(self) -> None:
        import os
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(self._summary(), fh)
            summary_path = fh.name
        try:
            with patch(
                "katrain.core.coach.summary_prompt_builder.build_summary_weakness_prompt",
                side_effect=ValueError("bad config"),
            ):
                ok, msg = validate_summary_llm_response(
                    ctx=None,
                    summary_path=summary_path,
                    llm_text="dummy answer body\n",
                    rank="5k",
                    player_name=None,
                )
            assert ok is False
            assert "build failed" in msg.lower() or "build-failed" in msg
        finally:
            os.unlink(summary_path)
