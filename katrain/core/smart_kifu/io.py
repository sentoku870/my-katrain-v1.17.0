"""Smart Kifu Learning - File I/O (Phase 13).

This module handles file operations for Smart Kifu Learning.
- manifest.json read/write
- player_profile.json read/write
- SGF import

v0.2 Scope:
- Training Set manifest management
- Player Profile persistence
- SGF folder import with duplicate detection
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, cast
import uuid

from katrain.core.constants import DATA_FOLDER
from katrain.core.smart_kifu.logic import (
    compute_analyzed_ratio_from_sgf_file,
    compute_game_id,
)
from katrain.core.smart_kifu.models import (
    Context,
    ContextProfile,
    GameEntry,
    GameSource,
    ImportErrorCode,
    ImportResult,
    PlayerProfile,
    TrainingSetManifest,
)

if TYPE_CHECKING:
    from katrain.core.smart_kifu.models import BucketProfile


logger = logging.getLogger(__name__)


# =============================================================================
# Directory Management
# =============================================================================


def get_smart_kifu_dir() -> Path:
    """smart_kifu データディレクトリを取得。

    Returns:
        ~/.katrain/smart_kifu/ のパス

    Note:
        ディレクトリが存在しない場合は作成しない（呼び出し側で作成）
    """
    base = Path(os.path.expanduser(DATA_FOLDER))
    return base / "smart_kifu"


def get_training_sets_dir() -> Path:
    """training_sets ディレクトリを取得。"""
    return get_smart_kifu_dir() / "training_sets"


def get_profiles_dir() -> Path:
    """profiles ディレクトリを取得。"""
    return get_smart_kifu_dir() / "profiles"


def ensure_smart_kifu_dirs() -> None:
    """smart_kifu関連ディレクトリを作成。"""
    get_smart_kifu_dir().mkdir(parents=True, exist_ok=True)
    get_training_sets_dir().mkdir(parents=True, exist_ok=True)
    get_profiles_dir().mkdir(parents=True, exist_ok=True)


# =============================================================================
# Training Set - List
# =============================================================================


def list_training_sets() -> List[str]:
    """Training Setの一覧を取得。

    Returns:
        set_idのリスト（ディレクトリ名）
    """
    ts_dir = get_training_sets_dir()
    if not ts_dir.exists():
        return []

    result = []
    for entry in ts_dir.iterdir():
        if entry.is_dir() and (entry / "manifest.json").exists():
            result.append(entry.name)
    return sorted(result)


# =============================================================================
# Training Set - Manifest I/O
# =============================================================================


def _game_entry_to_dict(entry: GameEntry) -> dict[str, Any]:
    """GameEntryを辞書に変換。"""
    return {
        "game_id": entry.game_id,
        "path": entry.path,
        "added_at": entry.added_at,
        "context": entry.context.value,
        "source": {
            "source_type": entry.source.source_type,
            "origin": entry.source.origin,
            "note": entry.source.note,
        },
        "tags": entry.tags,
        "board_size": entry.board_size,
        "handicap": entry.handicap,
        "move_count": entry.move_count,
        "result": entry.result,
        "analyzed_ratio": entry.analyzed_ratio,
        "engine_profile_id": entry.engine_profile_id,
    }


def _dict_to_game_entry(d: dict[str, Any]) -> GameEntry:
    """辞書をGameEntryに変換。"""
    source_dict = d.get("source", {})
    return GameEntry(
        game_id=d.get("game_id", ""),
        path=d.get("path", ""),
        added_at=d.get("added_at", ""),
        context=Context(d.get("context", "human")),
        source=GameSource(
            source_type=source_dict.get("source_type", "file"),
            origin=source_dict.get("origin", ""),
            note=source_dict.get("note", ""),
        ),
        tags=d.get("tags", []),
        board_size=d.get("board_size"),
        handicap=d.get("handicap"),
        move_count=d.get("move_count"),
        result=d.get("result"),
        analyzed_ratio=d.get("analyzed_ratio"),
        engine_profile_id=d.get("engine_profile_id"),
    )


def load_manifest(set_id: str) -> Optional[TrainingSetManifest]:
    """manifest.jsonを読み込み。

    Args:
        set_id: Training SetのID

    Returns:
        TrainingSetManifest、存在しない場合はNone
    """
    manifest_path = get_training_sets_dir() / set_id / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        games = [_dict_to_game_entry(g) for g in data.get("games", [])]

        return TrainingSetManifest(
            manifest_version=data.get("manifest_version", 1),
            set_id=data.get("set_id", set_id),
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            games=games,
        )
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load manifest for {set_id}: {e}")
        return None


def save_manifest(manifest: TrainingSetManifest) -> None:
    """manifest.jsonを保存。

    Args:
        manifest: 保存するマニフェスト

    Note:
        書き込みエラー時はlogger.error()でログ出力し、例外は再raiseしない。
    """
    ensure_smart_kifu_dirs()
    set_dir = get_training_sets_dir() / manifest.set_id
    set_dir.mkdir(parents=True, exist_ok=True)
    (set_dir / "sgf").mkdir(parents=True, exist_ok=True)

    manifest_path = set_dir / "manifest.json"

    data = {
        "manifest_version": manifest.manifest_version,
        "set_id": manifest.set_id,
        "name": manifest.name,
        "created_at": manifest.created_at,
        "games": [_game_entry_to_dict(g) for g in manifest.games],
    }

    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(
            "Failed to save manifest: set_id=%s, path=%s, error=%s: %s",
            manifest.set_id,
            manifest_path,
            type(e).__name__,
            e,
        )


def create_training_set(name: str) -> TrainingSetManifest:
    """新しいTraining Setを作成。

    Args:
        name: 表示名

    Returns:
        作成されたTrainingSetManifest
    """
    set_id = f"ts_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()

    manifest = TrainingSetManifest(
        manifest_version=1,
        set_id=set_id,
        name=name,
        created_at=now,
        games=[],
    )
    save_manifest(manifest)
    return manifest


# =============================================================================
# Player Profile I/O
# =============================================================================


def _bucket_profile_to_dict(profile: "BucketProfile") -> dict[str, Any]:
    """BucketProfileを辞書に変換。"""
    from katrain.core.smart_kifu.models import BucketProfile
    return {
        "viewer_level": profile.viewer_level,
        "viewer_preset": profile.viewer_preset.value,
        "confidence": profile.confidence.value,
        "samples": profile.samples,
        "analyzed_ratio": profile.analyzed_ratio,
        "engine_profile_id": profile.engine_profile_id,
        "use_for_reports": profile.use_for_reports,
        "updated_at": profile.updated_at,
        "recent_winrate": profile.recent_winrate,
        "recent_games_count": profile.recent_games_count,
    }


def _dict_to_bucket_profile(d: dict[str, Any]) -> "BucketProfile":
    """辞書をBucketProfileに変換。"""
    from katrain.core.smart_kifu.models import BucketProfile, Confidence, ViewerPreset
    return BucketProfile(
        viewer_level=d.get("viewer_level", 5),
        viewer_preset=ViewerPreset(d.get("viewer_preset", "standard")),
        confidence=Confidence(d.get("confidence", "low")),
        samples=d.get("samples", 0),
        analyzed_ratio=d.get("analyzed_ratio"),
        engine_profile_id=d.get("engine_profile_id"),
        use_for_reports=d.get("use_for_reports", True),
        updated_at=d.get("updated_at", ""),
        recent_winrate=d.get("recent_winrate"),
        recent_games_count=d.get("recent_games_count", 0),
    )


def load_player_profile() -> PlayerProfile:
    """player_profile.jsonを読み込み。

    Returns:
        PlayerProfile（存在しない場合は新規作成）
    """
    ensure_smart_kifu_dirs()
    profile_path = get_profiles_dir() / "player_profile.json"

    if not profile_path.exists():
        now = datetime.now().isoformat()
        return PlayerProfile(
            profile_version=1,
            created_at=now,
            updated_at=now,
            per_context={},
        )

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        per_context = {}
        for ctx_key, ctx_data in data.get("per_context", {}).items():
            buckets = {}
            for bucket_key, bucket_data in ctx_data.get("buckets", {}).items():
                buckets[bucket_key] = _dict_to_bucket_profile(bucket_data)
            per_context[ctx_key] = ContextProfile(
                context=Context(ctx_key),
                buckets=buckets,
            )

        return PlayerProfile(
            profile_version=data.get("profile_version", 1),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            per_context=per_context,
        )
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load player profile: {e}")
        now = datetime.now().isoformat()
        return PlayerProfile(
            profile_version=1,
            created_at=now,
            updated_at=now,
            per_context={},
        )


def save_player_profile(profile: PlayerProfile) -> None:
    """player_profile.jsonを保存。

    Args:
        profile: 保存するプロファイル

    Note:
        書き込みエラー時はlogger.error()でログ出力し、例外は再raiseしない。
    """
    ensure_smart_kifu_dirs()
    profile_path = get_profiles_dir() / "player_profile.json"

    per_context_data = {}
    for ctx_key, ctx_profile in profile.per_context.items():
        buckets_data = {}
        for bucket_key, bucket_profile in ctx_profile.buckets.items():
            buckets_data[bucket_key] = _bucket_profile_to_dict(bucket_profile)
        per_context_data[ctx_key] = {
            "context": ctx_key,
            "buckets": buckets_data,
        }

    data = {
        "profile_version": profile.profile_version,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "per_context": per_context_data,
    }

    try:
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(
            "Failed to save player profile: path=%s, error=%s: %s",
            profile_path,
            type(e).__name__,
            e,
        )


# =============================================================================
# SGF Import
# =============================================================================


def _extract_sgf_metadata(sgf_content: str) -> dict[str, int | str | None]:
    """SGFからメタデータを抽出（簡易版）。

    Args:
        sgf_content: SGFファイルの内容

    Returns:
        抽出されたメタデータ（board_size, handicap, move_count, result）
    """
    import re

    metadata: dict[str, int | str | None] = {
        "board_size": None,
        "handicap": None,
        "move_count": None,
        "result": None,
    }

    # SZ (board size)
    sz_match = re.search(r"SZ\[(\d+)\]", sgf_content)
    if sz_match:
        metadata["board_size"] = int(sz_match.group(1))

    # HA (handicap)
    ha_match = re.search(r"HA\[(\d+)\]", sgf_content)
    if ha_match:
        metadata["handicap"] = int(ha_match.group(1))
    else:
        metadata["handicap"] = 0  # デフォルト

    # RE (result)
    re_match = re.search(r"RE\[([^\]]*)\]", sgf_content)
    if re_match:
        metadata["result"] = re_match.group(1)

    # Move count (簡易: ;B[ または ;W[ の数をカウント)
    moves = re.findall(r";[BW]\[", sgf_content)
    metadata["move_count"] = len(moves)

    return metadata


def import_sgf_to_training_set(
    set_id: str,
    sgf_path: Path,
    context: Context,
    origin: str = "",
    tags: Optional[List[str]] = None,
    compute_ratio: bool = False,
) -> Tuple[Optional[GameEntry], Optional[ImportErrorCode]]:
    """SGFファイルをTraining Setにインポート。

    Args:
        set_id: Training SetのID
        sgf_path: SGFファイルのパス
        context: 対戦コンテキスト
        origin: ソースの元情報
        tags: タグリスト
        compute_ratio: 解析率を計算するか（Phase 28）

    Returns:
        (GameEntry, None): 成功時
        (None, ImportErrorCode): 失敗時（エラーコードで分類）
    """
    if tags is None:
        tags = []

    # manifest読み込み
    manifest = load_manifest(set_id)
    if manifest is None:
        return None, ImportErrorCode.FILE_NOT_FOUND

    # SGF読み込み
    try:
        with open(sgf_path, "r", encoding="utf-8") as f:
            sgf_content = f.read()
    except OSError:
        return None, ImportErrorCode.FILE_NOT_FOUND

    # game_id計算
    game_id = compute_game_id(sgf_content)

    # 重複チェック
    existing_ids = manifest.get_game_ids()
    if game_id in existing_ids:
        return None, ImportErrorCode.DUPLICATE

    # メタデータ抽出
    metadata = _extract_sgf_metadata(sgf_content)

    # ファイルコピー
    set_dir = get_training_sets_dir() / set_id / "sgf"
    set_dir.mkdir(parents=True, exist_ok=True)

    # ファイル名を生成（元のファイル名を保持しつつ衝突回避）
    base_name = sgf_path.stem
    dest_name = f"{base_name}.sgf"
    dest_path = set_dir / dest_name
    counter = 1
    while dest_path.exists():
        dest_name = f"{base_name}_{counter}.sgf"
        dest_path = set_dir / dest_name
        counter += 1

    try:
        shutil.copy2(sgf_path, dest_path)
    except OSError:
        return None, ImportErrorCode.COPY_FAILED

    # analyzed_ratio計算（オプション）
    ratio = None
    if compute_ratio:
        ratio = compute_analyzed_ratio_from_sgf_file(str(dest_path))

    # GameEntry作成
    now = datetime.now().isoformat()
    entry = GameEntry(
        game_id=game_id,
        path=f"sgf/{dest_name}",
        added_at=now,
        context=context,
        source=GameSource(
            source_type="file",
            origin=origin or str(sgf_path),
            note="",
        ),
        tags=tags,
        board_size=cast("int | None", metadata["board_size"]),
        handicap=cast("int | None", metadata["handicap"]),
        move_count=cast("int | None", metadata["move_count"]),
        result=cast("str | None", metadata["result"]),
        analyzed_ratio=ratio,
        engine_profile_id=None,
    )

    # manifest更新
    manifest.games.append(entry)
    save_manifest(manifest)

    return entry, None


def import_sgf_folder(
    set_id: str,
    folder_path: Path,
    context: Context,
    origin: str = "",
) -> ImportResult:
    """フォルダ内のSGFファイルを一括インポート。

    Args:
        set_id: Training SetのID
        folder_path: SGFフォルダのパス
        context: 対戦コンテキスト
        origin: ソースの元情報

    Returns:
        ImportResult（成功/失敗/スキップの件数）
    """
    result = ImportResult()

    if not folder_path.is_dir():
        result.failed_count = 1
        result.failed_files.append((str(folder_path), "Not a directory"))
        return result

    # *.sgf ファイルを列挙
    sgf_files = list(folder_path.glob("*.sgf"))
    if not sgf_files:
        return result  # 空のまま返す

    for sgf_path in sgf_files:
        entry, error_code = import_sgf_to_training_set(
            set_id=set_id,
            sgf_path=sgf_path,
            context=context,
            origin=origin,
        )

        if entry is not None:
            result.success_count += 1
            logger.info(f"Imported: {sgf_path.name}")
        elif error_code == ImportErrorCode.DUPLICATE:
            result.skipped_count += 1
            result.skipped_files.append(sgf_path.name)
            logger.info(f"Skipped (duplicate): {sgf_path.name}")
        else:
            result.failed_count += 1
            error_msg = error_code.value if error_code else "Unknown error"
            result.failed_files.append((sgf_path.name, error_msg))
            logger.warning(f"Failed: {sgf_path.name} - {error_msg}")

    return result


def import_analyzed_sgf_folder(
    set_id: str,
    folder_path: Path,
    context: Context,
    origin: str = "",
) -> ImportResult:
    """バッチ解析出力フォルダからインポート（解析率計算付き）。

    Phase 28: バッチ解析の出力フォルダをTraining Setにインポート。
    各SGFの解析率を計算してGameEntry.analyzed_ratioに設定。

    Args:
        set_id: Training SetのID
        folder_path: 解析済みSGFフォルダのパス
        context: 対戦コンテキスト
        origin: ソースの元情報

    Returns:
        ImportResult（成功/失敗/スキップの件数、平均解析率）
    """
    result = ImportResult()
    computed_ratios: List[Optional[float]] = []

    if not folder_path.is_dir():
        result.failed_count = 1
        result.failed_files.append((str(folder_path), "Not a directory"))
        return result

    # *.sgf ファイルを列挙
    sgf_files = list(folder_path.glob("*.sgf"))
    if not sgf_files:
        return result  # 空のまま返す

    for sgf_path in sgf_files:
        entry, error_code = import_sgf_to_training_set(
            set_id=set_id,
            sgf_path=sgf_path,
            context=context,
            origin=origin,
            compute_ratio=True,
        )

        if entry is not None:
            result.success_count += 1
            computed_ratios.append(entry.analyzed_ratio)
            logger.info(f"Imported: {sgf_path.name} (ratio={entry.analyzed_ratio})")
        elif error_code == ImportErrorCode.DUPLICATE:
            result.skipped_count += 1
            result.skipped_files.append(sgf_path.name)
            logger.info(f"Skipped (duplicate): {sgf_path.name}")
        else:
            result.failed_count += 1
            error_msg = error_code.value if error_code else "Unknown error"
            result.failed_files.append((sgf_path.name, error_msg))
            logger.warning(f"Failed: {sgf_path.name} - {error_msg}")

    # 平均解析率を計算（None除外）
    valid_ratios = [r for r in computed_ratios if r is not None]
    result.average_analyzed_ratio = (
        sum(valid_ratios) / len(valid_ratios) if valid_ratios else None
    )

    return result


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    # Directory
    "get_smart_kifu_dir",
    "get_training_sets_dir",
    "get_profiles_dir",
    "ensure_smart_kifu_dirs",
    # Training Set
    "list_training_sets",
    "load_manifest",
    "save_manifest",
    "create_training_set",
    # Player Profile
    "load_player_profile",
    "save_player_profile",
    # SGF Import
    "import_sgf_to_training_set",
    "import_sgf_folder",
    "import_analyzed_sgf_folder",
]
