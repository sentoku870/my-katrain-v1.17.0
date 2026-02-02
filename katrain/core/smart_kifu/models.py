"""Smart Kifu Learning - Data Models (Phase 13).

This module defines Enums and Dataclasses for Smart Kifu Learning.
These are UI-independent, pure data structures.

v0.2 Scope:
- Training Set management
- Player Profile tracking
- vs_katago practice reporting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Set

if TYPE_CHECKING:
    pass


# =============================================================================
# Enums
# =============================================================================


class Context(Enum):
    """棋譜のコンテキスト（対戦相手の種類）。

    v0.2ではユーザー選択（自動判定しない）。
    """

    HUMAN = "human"  # 対人戦
    VS_KATAGO = "vs_katago"  # vs KataGo練習
    GENERATED = "generated"  # AI生成棋譜


class ViewerPreset(Enum):
    """解説詳細度のプリセット。

    内部では1-10のviewer_levelを使用し、表示時にこの3段階に変換。
    """

    LITE = "lite"  # 簡潔（viewer_level 1-3）
    STANDARD = "standard"  # 標準（viewer_level 4-7）
    DEEP = "deep"  # 詳細（viewer_level 8-10）


class Confidence(Enum):
    """データ品質の信頼度。

    Note:
        既存の ConfidenceLevel (analysis) とは用途が異なる。
        - ConfidenceLevel: 解析結果の信頼度
        - Confidence: データ収集量・品質の信頼度
    """

    LOW = "low"  # samples < 10 または analyzed_ratio < 0.4 または None
    MEDIUM = "medium"  # samples >= 10 かつ analyzed_ratio >= 0.4
    HIGH = "high"  # samples >= 30 かつ analyzed_ratio >= 0.7


# =============================================================================
# Dataclasses - Source and Entry
# =============================================================================


@dataclass
class GameSource:
    """棋譜のソース情報。

    Attributes:
        source_type: ソースの種類（file/url/manual等）
        origin: 元の場所（ファイルパス、URL等）
        note: 補足メモ
    """

    source_type: str = "file"
    origin: str = ""
    note: str = ""


@dataclass
class GameEntry:
    """manifest.json内のゲームエントリ。

    Attributes:
        game_id: 正規化後SGFのSHA1ハッシュ（sha1:{40hex}）
        path: manifest.jsonからの相対パス（例: "sgf/game_001.sgf"）
        added_at: 登録日時（ISO 8601）← recent N の基準
        context: 対戦コンテキスト（ユーザー選択）
        source: ソース情報
        tags: タグリスト
        board_size: 盤サイズ（キャッシュ）
        handicap: 置石数（キャッシュ）
        move_count: 手数（キャッシュ）
        result: 結果文字列（キャッシュ）
        analyzed_ratio: 解析率 0.0-1.0、None=未解析
        engine_profile_id: 解析エンジン設定ID（ep_{16hex}）
    """

    game_id: str
    path: str
    added_at: str
    context: Context
    source: GameSource = field(default_factory=GameSource)
    tags: list[str] = field(default_factory=list)
    # Cached metadata
    board_size: int | None = None
    handicap: int | None = None
    move_count: int | None = None
    result: str | None = None
    analyzed_ratio: float | None = None
    engine_profile_id: str | None = None


# =============================================================================
# Dataclasses - Training Set
# =============================================================================


@dataclass
class TrainingSetManifest:
    """Training Set全体のマニフェスト。

    Attributes:
        manifest_version: スキーマバージョン（将来の互換性用）
        set_id: 一意のセットID
        name: 表示名
        created_at: 作成日時（ISO 8601）
        games: ゲームエントリのリスト
    """

    manifest_version: int = 1
    set_id: str = ""
    name: str = ""
    created_at: str = ""
    games: list[GameEntry] = field(default_factory=list)

    def get_game_ids(self) -> Set[str]:
        """重複チェック用にgame_idセットを返す。"""
        return {g.game_id for g in self.games}

    def get_recent_games(self, n: int, context: Context | None = None) -> list[GameEntry]:
        """added_at降順で直近N局を取得。

        Args:
            n: 取得する局数
            context: フィルタするコンテキスト（Noneなら全て）

        Returns:
            added_at降順でソートされた直近N局
        """
        filtered = self.games if context is None else [g for g in self.games if g.context == context]
        sorted_games = sorted(filtered, key=lambda g: g.added_at, reverse=True)
        return sorted_games[:n]


# =============================================================================
# Dataclasses - Engine Profile
# =============================================================================


@dataclass
class EngineProfileSnapshot:
    """解析エンジン設定のスナップショット。

    engine_profile_id計算に使用するフィールドのみを保持。

    Attributes:
        model_name: モデル名（None/空文字は除外）
        max_visits: 最大探索数（None除外、0は有効値）
        komi: コミ（None除外、0.0は有効値）
    """

    model_name: str | None = None
    max_visits: int | None = None
    komi: float | None = None


# =============================================================================
# Dataclasses - Player Profile
# =============================================================================


@dataclass
class BucketProfile:
    """Bucket毎のプロファイル。

    Bucket = board_size × handicap_group の組み合わせ。
    例: "19_even", "19_handicap", "9_even"

    Attributes:
        viewer_level: 解説詳細度レベル（1-10）
        viewer_preset: 表示用プリセット（Lite/Standard/Deep）
        confidence: データ品質の信頼度
        samples: 集計に使用した局数
        analyzed_ratio: 平均解析率（None=解析データなし → Confidence=LOW）
        engine_profile_id: 集計に使用したエンジン設定ID
        use_for_reports: レポートに使用するか
        updated_at: 更新日時（ISO 8601）
        recent_winrate: 直近N局の勝率（Phase 2）
        recent_games_count: 直近N局の数（Phase 2）
    """

    viewer_level: int = 5
    viewer_preset: ViewerPreset = ViewerPreset.STANDARD
    confidence: Confidence = Confidence.LOW
    samples: int = 0
    analyzed_ratio: float | None = None
    engine_profile_id: str | None = None
    use_for_reports: bool = True
    updated_at: str = ""
    # Phase 2: Practice tracking
    recent_winrate: float | None = None
    recent_games_count: int = 0


@dataclass
class ContextProfile:
    """Context毎のプロファイル。

    Attributes:
        context: 対戦コンテキスト
        buckets: bucket_key -> BucketProfile のマッピング
    """

    context: Context = Context.HUMAN
    buckets: dict[str, BucketProfile] = field(default_factory=dict)


@dataclass
class PlayerProfile:
    """ユーザーのプロファイル全体。

    Attributes:
        profile_version: スキーマバージョン
        created_at: 作成日時
        updated_at: 更新日時
        per_context: Context毎のプロファイル
    """

    profile_version: int = 1
    created_at: str = ""
    updated_at: str = ""
    per_context: dict[str, ContextProfile] = field(default_factory=dict)

    def get_bucket_profile(
        self, context: Context, bucket_key: str
    ) -> BucketProfile | None:
        """指定されたContext×Bucketのプロファイルを取得。

        Args:
            context: 対戦コンテキスト
            bucket_key: Bucketキー（例: "19_even"）

        Returns:
            BucketProfile、存在しない場合はNone
        """
        ctx_profile = self.per_context.get(context.value)
        if ctx_profile is None:
            return None
        return ctx_profile.buckets.get(bucket_key)


# =============================================================================
# Enums - Import Error Code
# =============================================================================


class ImportErrorCode(Enum):
    """インポートエラーコード（文字列マッチング回避）。

    Phase 28: import_sgf_to_training_set() の戻り値で使用。
    """

    DUPLICATE = "duplicate"
    PARSE_FAILED = "parse_failed"
    FILE_NOT_FOUND = "file_not_found"
    COPY_FAILED = "copy_failed"
    UNKNOWN = "unknown"


# =============================================================================
# Dataclasses - Import Result
# =============================================================================


@dataclass
class ImportResult:
    """SGFインポート結果。

    Attributes:
        success_count: 成功件数
        failed_count: 失敗件数
        skipped_count: 重複スキップ件数
        failed_files: 失敗ファイルリスト（filename, error_message）
        skipped_files: スキップファイル名リスト
        average_analyzed_ratio: 成功インポートの平均解析率（Phase 28）
    """

    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    failed_files: list[tuple[str, str]] = field(default_factory=list)  # (filename, error_message)
    skipped_files: list[str] = field(default_factory=list)
    average_analyzed_ratio: float | None = None

    @property
    def has_failures(self) -> bool:
        """失敗があるか。"""
        return self.failed_count > 0

    @property
    def total_processed(self) -> int:
        """処理した総件数。"""
        return self.success_count + self.failed_count + self.skipped_count


# =============================================================================
# Dataclasses - Training Set Summary
# =============================================================================


@dataclass
class TrainingSetSummary:
    """Training Set の集計サマリー（オンデマンド計算）。

    Phase 28: compute_training_set_summary() で生成。

    Attributes:
        total_games: 総局数
        analyzed_games: 解析データありの局数（analyzed_ratio is not None）
        fully_analyzed_games: 完全解析済み局数（analyzed_ratio >= 1.0）
        average_analyzed_ratio: 平均解析率（None除外）、全てNoneならNone
        unanalyzed_games: 未解析局数（analyzed_ratio is None）
    """

    total_games: int = 0
    analyzed_games: int = 0
    fully_analyzed_games: int = 0
    average_analyzed_ratio: float | None = None
    unanalyzed_games: int = 0


# =============================================================================
# Constants - Confidence Thresholds
# =============================================================================

# High Confidence: samples >= 30 かつ analyzed_ratio >= 0.7
CONFIDENCE_HIGH_MIN_SAMPLES = 30
CONFIDENCE_HIGH_MIN_ANALYZED_RATIO = 0.7

# Medium Confidence: samples >= 10 かつ analyzed_ratio >= 0.4
CONFIDENCE_MEDIUM_MIN_SAMPLES = 10
CONFIDENCE_MEDIUM_MIN_ANALYZED_RATIO = 0.4


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    # Enums
    "Context",
    "ViewerPreset",
    "Confidence",
    "ImportErrorCode",
    # Dataclasses
    "GameSource",
    "GameEntry",
    "TrainingSetManifest",
    "EngineProfileSnapshot",
    "BucketProfile",
    "ContextProfile",
    "PlayerProfile",
    "ImportResult",
    "TrainingSetSummary",
    # Constants
    "CONFIDENCE_HIGH_MIN_SAMPLES",
    "CONFIDENCE_HIGH_MIN_ANALYZED_RATIO",
    "CONFIDENCE_MEDIUM_MIN_SAMPLES",
    "CONFIDENCE_MEDIUM_MIN_ANALYZED_RATIO",
]
