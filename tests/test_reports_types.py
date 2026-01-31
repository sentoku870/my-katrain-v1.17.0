"""Protocol互換性テスト（v5: 型を実際の実装に合わせて検証）

PR #115: Phase B2 - reports/パッケージ骨格

v5改善:
- 属性存在テスト
- Gameインスタンスを作成して検証
- 実際の戻り値型を検証（board_size: Tuple[int, int]等）
- FeatureContext.configとConfigReaderの互換性を確認
"""

import inspect

import pytest

from katrain.core.base_katrain import KaTrainBase
from katrain.core.game import Game
from katrain.core.game_node import GameNode
from katrain.core.reports.types import (
    CONFIG_READER_REQUIRED_ATTRS,
    GAME_METADATA_REQUIRED_ATTRS,
    ROOT_NODE_REQUIRED_ATTRS,
)


class MockKaTrain(KaTrainBase):
    """テスト用のKaTrainモック"""
    pass


class MockEngine:
    """テスト用のEngineモック"""
    def request_analysis(self, *args, **kwargs):
        pass

    def stop_pondering(self):
        return

    def has_query_capacity(self, headroom: int = 10) -> bool:
        return True


@pytest.fixture
def sample_game():
    """テスト用のGameインスタンスを作成"""
    move_tree = GameNode(properties={"SZ": 19})
    return Game(MockKaTrain(force_package_config=True), MockEngine(), move_tree=move_tree)


class TestGameMetadataProviderCompatibility:
    """GameクラスがGameMetadataProviderを満たすことを検証"""

    def test_game_has_required_attributes(self, sample_game):
        """Game が必須属性を持っている"""
        for attr in GAME_METADATA_REQUIRED_ATTRS:
            assert hasattr(sample_game, attr), (
                f"Game must have '{attr}' attribute/method. "
                f"GameMetadataProvider protocol requires: {GAME_METADATA_REQUIRED_ATTRS}"
            )

    def test_game_attributes_types(self, sample_game):
        """属性の型が正しい（v5: 実際の型を検証）"""
        # board_size は Tuple[int, int]（非正方形盤面対応）
        board_size = sample_game.board_size
        assert isinstance(
            board_size, tuple
        ), f"board_size should be tuple, got {type(board_size)}"
        assert len(board_size) == 2, f"board_size should be (x, y), got {board_size}"
        assert all(
            isinstance(d, int) for d in board_size
        ), f"board_size elements should be int"

        # komi は float
        assert isinstance(sample_game.komi, (int, float))

        # rules は str
        assert isinstance(sample_game.rules, str)

        # sgf_filename は None または str
        assert sample_game.sgf_filename is None or isinstance(
            sample_game.sgf_filename, str
        )

        # root プロパティ
        assert hasattr(sample_game, "root")
        root = sample_game.root
        assert root is not None

    def test_root_node_has_required_attributes(self, sample_game):
        """rootノードが必須属性を持っている"""
        root = sample_game.root
        for attr in ROOT_NODE_REQUIRED_ATTRS:
            assert hasattr(root, attr), (
                f"root node must have '{attr}' attribute/method. "
                f"RootNodeProvider protocol requires: {ROOT_NODE_REQUIRED_ATTRS}"
            )

    def test_root_get_property_works(self, sample_game):
        """root.get_property()が動作する"""
        root = sample_game.root
        # デフォルト値付きで取得
        result = root.get_property("PB", "unknown")
        assert result is not None  # デフォルト値が返される
        # 存在しないキー
        result = root.get_property("NONEXISTENT", "default")
        assert result == "default"


class TestConfigReaderCompatibility:
    """ConfigReader Protocol の検証"""

    def test_dict_wrapper_satisfies_protocol(self):
        """dictをラップしたConfigReaderの例"""

        class DictConfigReader:
            def __init__(self, data: dict):
                self._data = data

            def __call__(self, key: str, default=None):
                # スラッシュ区切りのキーをサポート（実際のconfig互換）
                if "/" in key:
                    cat, k = key.split("/", 1)
                    return self._data.get(cat, {}).get(k, default)
                return self._data.get(key, default)

        config = DictConfigReader({"karte": {"show_variation_pv": True}})

        # Protocol要件を満たす
        for attr in CONFIG_READER_REQUIRED_ATTRS:
            assert hasattr(config, attr)

        # 動作確認（スラッシュ区切りキー）
        assert config("karte/show_variation_pv") is True
        assert config("nonexistent", "default") == "default"

    def test_feature_context_config_signature(self):
        """FeatureContext.configのシグネチャがConfigReaderと互換（v5: 確認済み）

        FeatureContext.config(setting: str, default: Any = None) -> Any
        ConfigReader.__call__(key: str, default: Any = None) -> Any
        """
        from katrain.gui.features.context import FeatureContext

        # FeatureContext.config のシグネチャを取得
        sig = inspect.signature(FeatureContext.config)
        params = list(sig.parameters.keys())

        # 期待するパラメータ: self, setting, default
        assert "setting" in params or len(params) >= 2
        # default パラメータが存在
        assert "default" in params


class TestProtocolDefinitions:
    """Protocol定義自体のテスト"""

    def test_required_attrs_lists_exist(self):
        """必須属性リストが定義されている"""
        assert len(GAME_METADATA_REQUIRED_ATTRS) >= 5
        assert len(CONFIG_READER_REQUIRED_ATTRS) >= 1

    def test_protocol_import_succeeds(self):
        """Protocol定義がインポート可能"""
        from katrain.core.reports.types import (
            ConfigReader,
            GameMetadataProvider,
        )

        # 型ヒントとして使用可能か確認
        def example_func(game: GameMetadataProvider, config: ConfigReader) -> str:
            return ""

        # 関数定義が成功すればOK
        assert callable(example_func)

    def test_reports_package_import(self):
        """reportsパッケージがインポート可能"""
        from katrain.core.reports import (
            CONFIG_READER_REQUIRED_ATTRS,
            GAME_METADATA_REQUIRED_ATTRS,
            ROOT_NODE_REQUIRED_ATTRS,
            ConfigReader,
            GameMetadataProvider,
            RootNodeProvider,
        )

        assert GameMetadataProvider is not None
        assert RootNodeProvider is not None
        assert ConfigReader is not None
        assert len(GAME_METADATA_REQUIRED_ATTRS) >= 5
        assert len(ROOT_NODE_REQUIRED_ATTRS) >= 1
        assert len(CONFIG_READER_REQUIRED_ATTRS) >= 1


class TestReportsNoGuiImport:
    """reports/パッケージがgui/をインポートしていないことを検証"""

    def test_types_no_gui_import(self):
        """types.pyがgui/をインポートしていない"""
        from pathlib import Path

        types_file = (
            Path(__file__).parent.parent / "katrain" / "core" / "reports" / "types.py"
        )
        content = types_file.read_text(encoding="utf-8")

        # モジュールレベルのguiインポートがないことを確認
        assert "from katrain.gui" not in content
        assert "import katrain.gui" not in content

    def test_init_no_gui_import(self):
        """__init__.pyがgui/をインポートしていない"""
        from pathlib import Path

        init_file = (
            Path(__file__).parent.parent
            / "katrain"
            / "core"
            / "reports"
            / "__init__.py"
        )
        content = init_file.read_text(encoding="utf-8")

        # モジュールレベルのguiインポートがないことを確認
        assert "from katrain.gui" not in content
        assert "import katrain.gui" not in content
