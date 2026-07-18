"""Phase 265: Curated weak-axis realtime re-label

リアルタイム対局中 (node.meaning_tag_id がない状況) でも、
既存の beginner hint があれば、それがユーザーの弱点 (weak_tags)
に該当するときに curator メタデータを hint.context に追加する。

テスト:
- HintCategory.related_meaning_tag_ids の各カテゴリのマッピング
- apply_curator_weak_axis_label の発火条件 (hint / weak_tags 必須)
- 既存 hint はそのまま (category/severity/coords 不変)
- threshold (min_occurrences) 未満は無視
- 複数 related tag のうち最初のマッチが採用される
- frozen dataclass の immutability
"""

import ast
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_PATH = REPO_ROOT / "katrain" / "core" / "beginner" / "models.py"
DETECTOR_PATH = REPO_ROOT / "katrain" / "core" / "beginner" / "detector_curator.py"


# -----------------------------------------------------------------------------
# Helper: 関数ロード (Kivy 非依存)
# -----------------------------------------------------------------------------


def _load_apply_label() -> callable:
    """``apply_curator_weak_axis_label`` を AST 経由で隔離ロード。"""
    tree = ast.parse(DETECTOR_PATH.read_text(encoding="utf-8"))
    func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "apply_curator_weak_axis_label":
            func = node
            break
    assert func is not None

    from dataclasses import replace
    from typing import Any, Optional

    # HintCategory と BeginnerHint は import が必要
    models = importlib.import_module("katrain.core.beginner.models")
    HintCategory = models.HintCategory
    BeginnerHint = models.BeginnerHint

    ns: dict = {
        "Any": Any,
        "Optional": Optional,
        "replace": replace,
        "BeginnerHint": BeginnerHint,
        "HintCategory": HintCategory,
    }
    exec(compile(ast.Module(body=[func], type_ignores=[]), "<test>", "exec"), ns)
    return ns["apply_curator_weak_axis_label"]


def _hint(category, *, severity: int = 1, coords=None, context: dict | None = None):
    """``BeginnerHint`` 構築ヘルパー。"""
    from katrain.core.beginner.models import BeginnerHint

    return BeginnerHint(
        category=category,
        coords=coords,
        severity=severity,
        context=context or {},
    )


# -----------------------------------------------------------------------------
# 1. HintCategory.related_meaning_tag_ids のマッピング整合
# -----------------------------------------------------------------------------


def test_related_meaning_tag_ids_returns_tuple() -> None:
    from katrain.core.beginner.models import HintCategory

    # 主要カテゴリが空でない tuple を返す
    for cat in (
        HintCategory.SELF_ATARI,
        HintCategory.MISTAKE_BLUNDER,
        HintCategory.MISTAKE_MISTAKE,
        HintCategory.POLICY_CONFLICT,
    ):
        result = HintCategory.related_meaning_tag_ids(cat)
        assert isinstance(result, tuple)
        assert len(result) > 0, f"{cat} should map to at least one meaning tag"


def test_related_meaning_tag_ids_empty_for_non_weakness() -> None:
    """MISTAKE_GOOD / FREEDOM_WIDE / POLICY_CONFIDENT は弱点ではない。"""
    from katrain.core.beginner.models import HintCategory

    assert HintCategory.related_meaning_tag_ids(HintCategory.MISTAKE_GOOD) == ()
    assert HintCategory.related_meaning_tag_ids(HintCategory.FREEDOM_WIDE) == ()
    assert HintCategory.related_meaning_tag_ids(HintCategory.FREEDOM_NARROW) == ()
    assert HintCategory.related_meaning_tag_ids(HintCategory.DIFFICULTY_CALM) == ()
    assert HintCategory.related_meaning_tag_ids(HintCategory.POLICY_CONFIDENT) == ()


def test_related_meaning_tag_ids_unknown_category_returns_empty() -> None:
    from katrain.core.beginner.models import HintCategory

    # Some edge case - even if we pass an unknown category, the function
    # should not crash and return ()
    result = HintCategory.related_meaning_tag_ids(HintCategory.CURATOR_WEAK_AXIS)
    assert result == ()


# -----------------------------------------------------------------------------
# 2. apply_curator_weak_axis_label の発火条件
# -----------------------------------------------------------------------------


def test_label_noop_when_hint_is_none() -> None:
    fn = _load_apply_label()
    assert fn(None, {"life_death_error": 5}) is None


def test_label_noop_when_weak_tags_empty() -> None:
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    assert fn(hint, None) is hint
    assert fn(hint, {}) is hint


def test_label_noop_when_category_has_no_related() -> None:
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_GOOD)
    assert fn(hint, {"life_death_error": 5}) is hint


def test_label_noop_when_below_threshold() -> None:
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    # MISTAKE_BLUNDER → life_death_error が first、count=2 < threshold=3
    assert fn(hint, {"life_death_error": 2}, min_occurrences=3) is hint


# -----------------------------------------------------------------------------
# 3. 発火パス
# -----------------------------------------------------------------------------


def test_label_adds_curator_metadata() -> None:
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    result = fn(hint, {"life_death_error": 5}, min_occurrences=3)
    assert result is not None
    assert result is not hint  # 新規オブジェクト

    meta = (result.context or {}).get("curator_weak_axis")
    assert meta is not None
    assert meta["tag_id"] == "life_death_error"
    assert meta["occurrence_count"] == 5
    assert meta["min_occurrences"] == 3


def test_label_preserves_other_fields() -> None:
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER, severity=3, coords=(3, 4))
    result = fn(hint, {"life_death_error": 5}, min_occurrences=3)
    assert result is not None
    assert result.category == HintCategory.MISTAKE_BLUNDER
    assert result.severity == 3
    assert result.coords == (3, 4)


def test_label_picks_first_related_match() -> None:
    """MISTAKE_BLUNDER の related は (life_death_error, capture_race_loss, reading_failure)
    → life_death_error が user_weak_tags にあればそれが選択される。"""
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    # life_death_error が 5、capture_race_loss が 10 → life_death_error が first
    result = fn(
        hint,
        {"life_death_error": 5, "capture_race_loss": 10},
        min_occurrences=3,
    )
    assert result is not None
    meta = (result.context or {}).get("curator_weak_axis")
    assert meta["tag_id"] == "life_death_error"
    assert meta["occurrence_count"] == 5


def test_label_falls_back_to_next_related() -> None:
    """first が threshold 未満なら next にフォールバック。"""
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    # life_death_error = 2 (< 3), capture_race_loss = 7 (>= 3)
    result = fn(
        hint,
        {"life_death_error": 2, "capture_race_loss": 7},
        min_occurrences=3,
    )
    assert result is not None
    meta = (result.context or {}).get("curator_weak_axis")
    assert meta["tag_id"] == "capture_race_loss"
    assert meta["occurrence_count"] == 7


def test_label_noop_when_no_related_in_weak_tags() -> None:
    """related タグが user_weak_tags に一つも無ければ無反応。"""
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    result = fn(hint, {"endgame_slip": 5}, min_occurrences=3)
    assert result is hint  # no change


# -----------------------------------------------------------------------------
# 4. frozen dataclass の immutability
# -----------------------------------------------------------------------------


def test_label_returns_new_object() -> None:
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    result = fn(hint, {"life_death_error": 5}, min_occurrences=3)
    assert result is not hint
    # オリジナル hint.context は変更されていない
    assert "curator_weak_axis" not in (hint.context or {})
    # 新 result.context には入っている
    assert "curator_weak_axis" in (result.context or {})


def test_label_handles_invalid_weak_tag_types() -> None:
    """user_weak_tags に不正な値 (None / str) が混じっててもクラッシュしない。"""
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER)
    # "life_death_error": "abc" は int 変換失敗 → カウント 0
    result = fn(hint, {"life_death_error": "abc", "capture_race_loss": 5}, min_occurrences=3)
    assert result is not None
    meta = (result.context or {}).get("curator_weak_axis")
    assert meta["tag_id"] == "capture_race_loss"
    assert meta["occurrence_count"] == 5


# -----------------------------------------------------------------------------
# 5. 既存 context との共存
# -----------------------------------------------------------------------------


def test_label_preserves_existing_context_keys() -> None:
    """既存 context の他のキーは触らない。"""
    from katrain.core.beginner.models import HintCategory

    fn = _load_apply_label()
    hint = _hint(HintCategory.MISTAKE_BLUNDER, context={"original_key": "value", "loss": 2.5})
    result = fn(hint, {"life_death_error": 5}, min_occurrences=3)
    assert result is not None
    ctx = result.context or {}
    assert ctx.get("original_key") == "value"
    assert ctx.get("loss") == 2.5
    assert "curator_weak_axis" in ctx
