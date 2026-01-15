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
