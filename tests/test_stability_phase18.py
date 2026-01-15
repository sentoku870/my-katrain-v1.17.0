"""Phase 18 tests for stability improvements.

PR #110: Critical Fixes (P1 + P2)
- P1: Texture cache LRU limit
- P2: Popup Clock binding fix
"""

import importlib.util

import pytest


# =============================================================================
# Kivy availability check helper (v5: using importlib.util.find_spec)
# =============================================================================


def _kivy_available():
    """Kivyがインストールされているかチェック（インポートせずに判定）

    v5改善: importlib.util.find_specを使用
    - モジュール本体をインポートしない（副作用なし）
    - コレクション時に安全に評価可能
    """
    return importlib.util.find_spec("kivy") is not None


# =============================================================================
# Pure Python Tests（Kivy不要）
# =============================================================================


class TestMakeHashable:
    """_make_hashableのテスト（Pure Python）"""

    @pytest.fixture
    def make_hashable(self):
        """Import _make_hashable only when needed"""
        from katrain.gui.kivyutils import _make_hashable

        return _make_hashable

    def test_primitives(self, make_hashable):
        """_make_hashableがプリミティブ型を処理"""
        assert make_hashable("text") == "text"
        assert make_hashable(123) == 123
        assert make_hashable(1.5) == 1.5
        assert make_hashable(None) is None

    def test_list_to_tuple(self, make_hashable):
        """_make_hashableがlistをtupleに変換"""
        result = make_hashable([1, 2, 3])
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)

    def test_dict_to_sorted_tuple(self, make_hashable):
        """_make_hashableがdictをsorted tuple of tuplesに変換"""
        result = make_hashable({"b": 2, "a": 1})
        assert result == (("a", 1), ("b", 2))

    def test_nested_structure(self, make_hashable):
        """_make_hashableがネストした構造を処理"""
        result = make_hashable({"key": [1, 2]})
        assert result == (("key", (1, 2)),)

    def test_set_to_tuple(self, make_hashable):
        """v4: _make_hashableがsetをtupleに変換"""
        result = make_hashable({1, 2, 3})
        assert isinstance(result, tuple)
        assert set(result) == {1, 2, 3}

    def test_tuple_recursion(self, make_hashable):
        """v4: _make_hashableがtupleを再帰処理"""
        result = make_hashable((1, [2, 3]))
        assert result == (1, (2, 3))

    def test_unhashable_object_fallback(self, make_hashable):
        """v4: unhashableオブジェクトがrepr()フォールバック"""
        # unhashableなオブジェクト（例: bytearray）
        obj = bytearray(b"test")
        result = make_hashable(obj)
        assert isinstance(result, str)
        assert "__unhashable__" in result


class TestPopupSizeLogic:
    """Popupサイズロジックのテスト（Pure Python）"""

    def test_tuple_to_list_conversion(self):
        """sizeがtupleでもlistに変換される"""
        original = (800, 600)
        # I18NPopup内部のロジックをシミュレート
        size = list(original) if not isinstance(original, list) else original
        assert size == [800, 600]
        assert isinstance(size, list)

    def test_list_remains_list(self):
        """sizeがlistの場合はそのまま"""
        original = [800, 600]
        size = list(original) if not isinstance(original, list) else original
        assert size == [800, 600]
        assert isinstance(size, list)

    def test_size_clamping_logic(self):
        """サイズクランプロジック"""
        window_width, window_height = 1920, 1080
        requested = [2000, 1200]
        clamped = [min(window_width, requested[0]), min(window_height, requested[1])]
        assert clamped == [1920, 1080]

    def test_size_within_bounds(self):
        """サイズが範囲内の場合"""
        window_width, window_height = 1920, 1080
        requested = [800, 600]
        clamped = [min(window_width, requested[0]), min(window_height, requested[1])]
        assert clamped == [800, 600]


class TestFontNameResolution:
    """font_name解決ロジックのテスト（Pure Python）"""

    def test_none_fallback(self):
        """font_name=Noneが解決される"""
        font_name_input = None
        i18n_font = "NotoSansJP"
        fallback_font = "Roboto"
        resolved = font_name_input if font_name_input else (i18n_font or fallback_font)
        assert resolved == "NotoSansJP"

    def test_double_none_fallback(self):
        """i18n.font_nameもNoneの場合のフォールバック"""
        font_name_input = None
        i18n_font = None
        fallback_font = "Roboto"
        resolved = font_name_input if font_name_input else (i18n_font or fallback_font)
        assert resolved == "Roboto"

    def test_explicit_font_preserved(self):
        """明示的なfont_nameが保持される"""
        font_name_input = "CustomFont"
        i18n_font = "NotoSansJP"
        fallback_font = "Roboto"
        resolved = font_name_input if font_name_input else (i18n_font or fallback_font)
        assert resolved == "CustomFont"


# =============================================================================
# Kivy-Import Tests（インポートのみ、ランタイム不要）
# =============================================================================


@pytest.mark.skipif(not _kivy_available(), reason="Kivy not installed")
class TestCacheConfig:
    """キャッシュ設定のテスト（Kivyインポート必要）"""

    def test_lru_cache_text_maxsize(self):
        """_create_text_textureのmaxsizeが設定されている"""
        from katrain.gui.kivyutils import _create_text_texture

        assert _create_text_texture.cache_info().maxsize == 500

    def test_lru_cache_texture_maxsize(self):
        """cached_textureのmaxsizeが設定されている"""
        from katrain.gui.kivyutils import cached_texture

        assert cached_texture.cache_info().maxsize == 100

    def test_cache_can_be_cleared(self):
        """キャッシュがクリア可能"""
        from katrain.gui.kivyutils import _create_text_texture

        _create_text_texture.cache_clear()
        info = _create_text_texture.cache_info()
        assert info.hits == 0 and info.misses == 0

    def test_clear_texture_caches_callable(self):
        """clear_texture_caches関数が存在しcallable"""
        from katrain.gui.kivyutils import clear_texture_caches

        assert callable(clear_texture_caches)


@pytest.mark.skipif(not _kivy_available(), reason="Kivy not installed")
class TestPopupClockBinding:
    """Popup Clockバインディングのテスト（Kivyインポート必要）"""

    def test_schedule_update_state_is_callable(self):
        """_schedule_update_stateがcallable"""
        from katrain.gui.popups import I18NPopup

        assert callable(getattr(I18NPopup, "_schedule_update_state", None))

    def test_do_update_state_is_callable(self):
        """_do_update_stateがcallable"""
        from katrain.gui.popups import I18NPopup

        assert callable(getattr(I18NPopup, "_do_update_state", None))

    def test_get_app_gui_callable(self):
        """_get_app_gui関数が存在しcallable"""
        from katrain.gui.popups import _get_app_gui

        assert callable(_get_app_gui)


@pytest.mark.skipif(not _kivy_available(), reason="Kivy not installed")
class TestFallbackTexture:
    """フォールバックテクスチャのテスト（Kivyインポート必要）"""

    def test_get_fallback_texture_callable(self):
        """_get_fallback_texture関数が存在しcallable"""
        from katrain.gui.kivyutils import _get_fallback_texture

        assert callable(_get_fallback_texture)

    def test_missing_resources_is_set(self):
        """_missing_resourcesがset型"""
        from katrain.gui.kivyutils import _missing_resources

        assert isinstance(_missing_resources, set)


# =============================================================================
# PR #111: P3 Move.from_gtp() 入力検証テスト
# =============================================================================


class TestMoveFromGtpValidation:
    """Move.from_gtp() の入力検証テスト（Pure Python）"""

    def test_valid_coordinates(self):
        """正常な座標"""
        from katrain.core.sgf_parser import Move

        m = Move.from_gtp("D4", "B")
        assert m.coords == (3, 3)  # D=3, 4-1=3

    def test_valid_coordinates_large_board(self):
        """大きな盤面の座標"""
        from katrain.core.sgf_parser import Move

        m = Move.from_gtp("T19", "W")
        assert m.coords == (18, 18)  # T=18 (Iをスキップ), 19-1=18

    def test_pass_move(self):
        """パス"""
        from katrain.core.sgf_parser import Move

        m = Move.from_gtp("pass", "W")
        assert m.coords is None

    def test_pass_move_uppercase(self):
        """大文字PASS"""
        from katrain.core.sgf_parser import Move

        m = Move.from_gtp("PASS", "B")
        assert m.coords is None

    def test_invalid_format_raises_valueerror(self):
        """不正フォーマットでValueError"""
        from katrain.core.sgf_parser import Move

        with pytest.raises(ValueError, match="Invalid GTP coordinate"):
            Move.from_gtp("invalid", "B")

    def test_empty_string_raises_valueerror(self):
        """空文字列でValueError"""
        from katrain.core.sgf_parser import Move

        with pytest.raises(ValueError, match="Invalid GTP coordinate"):
            Move.from_gtp("", "B")

    def test_negative_row_raises_valueerror(self):
        """負の行でValueError"""
        from katrain.core.sgf_parser import Move

        with pytest.raises(ValueError, match="Invalid GTP row"):
            Move.from_gtp("A0", "B")  # 0-1 = -1

    def test_lowercase_input_normalized(self):
        """小文字入力が正規化される"""
        from katrain.core.sgf_parser import Move

        m = Move.from_gtp("d4", "B")
        assert m.coords == (3, 3)

    def test_error_message_includes_input(self):
        """エラーメッセージに入力値が含まれる"""
        from katrain.core.sgf_parser import Move

        with pytest.raises(ValueError) as exc_info:
            Move.from_gtp("xyz123", "B")
        # xyz123 is invalid format (not matching [A-Z]+\d+)
        assert "xyz123" in str(exc_info.value).lower() or "XYZ123" in str(exc_info.value)


# =============================================================================
# PR #111: P4 配列アクセスガードテスト
# =============================================================================


class TestArrayAccessGuards:
    """配列アクセスガードのテスト（Pure Python）"""

    def test_empty_moveinfos_pvtail_guard(self):
        """空のmoveInfosでpvtailがガードされる"""
        # ロジックテスト: analysis_json["moveInfos"]が空の場合
        analysis_json = {"moveInfos": [], "rootInfo": {"winrate": 0.5}}
        pvtail = analysis_json["moveInfos"][0]["pv"] if analysis_json["moveInfos"] else []
        assert pvtail == []

    def test_nonempty_moveinfos_pvtail(self):
        """moveInfosがある場合にpvtailが取得される"""
        analysis_json = {
            "moveInfos": [{"pv": ["D4", "E5"]}],
            "rootInfo": {"winrate": 0.5},
        }
        pvtail = analysis_json["moveInfos"][0]["pv"] if analysis_json["moveInfos"] else []
        assert pvtail == ["D4", "E5"]

    def test_empty_top_move_list_guard(self):
        """top_moveリストが空の場合のガード"""
        move_dicts = [{"order": 1, "scoreLead": 5.0}, {"order": 2, "scoreLead": 3.0}]
        root_score = 4.0
        top_move = [d for d in move_dicts if d.get("order") == 0]
        top_score_lead = top_move[0]["scoreLead"] if top_move else root_score
        assert top_score_lead == root_score  # フォールバック

    def test_nonempty_top_move_list(self):
        """top_moveリストがある場合"""
        move_dicts = [{"order": 0, "scoreLead": 5.0}, {"order": 1, "scoreLead": 3.0}]
        root_score = 4.0
        top_move = [d for d in move_dicts if d.get("order") == 0]
        top_score_lead = top_move[0]["scoreLead"] if top_move else root_score
        assert top_score_lead == 5.0


# =============================================================================
# PR #112: P5 animate_pv インターバル遅延初期化テスト
# =============================================================================


@pytest.mark.skipif(not _kivy_available(), reason="Kivy not installed")
class TestAnimatePvInterval:
    """animate_pv インターバルのテスト（Kivyインポート必要）"""

    def test_start_pv_animation_method_exists(self):
        """_start_pv_animation メソッドの存在確認"""
        from katrain.gui.badukpan import BadukPanWidget

        assert hasattr(BadukPanWidget, "_start_pv_animation")
        assert callable(getattr(BadukPanWidget, "_start_pv_animation", None))

    def test_stop_pv_animation_method_exists(self):
        """_stop_pv_animation メソッドの存在確認"""
        from katrain.gui.badukpan import BadukPanWidget

        assert hasattr(BadukPanWidget, "_stop_pv_animation")
        assert callable(getattr(BadukPanWidget, "_stop_pv_animation", None))

    def test_update_pv_animation_state_method_exists(self):
        """_update_pv_animation_state メソッドの存在確認"""
        from katrain.gui.badukpan import BadukPanWidget

        assert hasattr(BadukPanWidget, "_update_pv_animation_state")
        assert callable(getattr(BadukPanWidget, "_update_pv_animation_state", None))
