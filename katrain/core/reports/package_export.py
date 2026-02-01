# katrain/core/reports/package_export.py
"""LLM Package Export - ZIP生成ロジック（Kivy非依存）

責務:
- ZIP生成
- manifest.json構築
- coach.md読み込み
- 出力先ディレクトリ解決
- 匿名化ヘルパー関数（GUI層から呼び出される）

匿名化処理自体はGUI層の責務。このモジュールは最終文字列を受け取るだけ。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import json
import os
import random
import string
import sys
import zipfile

from katrain.core.constants import VERSION

if TYPE_CHECKING:
    from katrain.core.sgf_parser import SGFNode

# 将来の拡張用（Phase 25では使用しない）
EXTENDED_ANONYMIZE_PROPS = ["PC", "EV", "GN", "GC", "US", "AN", "SO"]

# フォールバック用coach.md
COACH_MD_FALLBACK = """# Coach Guide

See docs/03-llm-validation.md for the full coaching instructions.

## Quick Start

1. Upload this package (karte.md + game.sgf) to your LLM (Claude, ChatGPT, etc.)
2. Ask: "Please analyze this Go game based on the karte and suggest improvements."
3. Follow the suggested action rules (max 3 at a time).

## Tips

- Focus on one weakness at a time.
- Practice 5 games before re-evaluating.
- Track your progress with weekly summaries.
"""


@dataclass
class PackageContent:
    """ZIPパッケージの内容（匿名化済みの最終文字列）"""

    karte_md: str  # 匿名化済み（必要な場合）
    sgf_content: str  # 匿名化済み（必要な場合）
    coach_md: str
    game_info: dict[str, Any]
    skill_preset: str = "standard"
    anonymized: bool = False  # manifest用フラグ


@dataclass
class PackageResult:
    """エクスポート結果"""

    success: bool
    output_path: Optional[Path]
    error_message: Optional[str] = None


# --- ユーティリティ関数（GUI層でも使用） ---


def get_player_names_from_tree(root_node: "SGFNode") -> tuple[str, str]:
    """SGFツリーからプレイヤー名を取得

    APIシグネチャ（検証済み）:
    - get_property(property, default=None) -> Any
    - プロパティが存在しない場合は default を返す
    """
    pb = root_node.get_property("PB", "")
    pw = root_node.get_property("PW", "")
    return pb, pw


def anonymize_sgf_string(sgf_content: str, pb: str, pw: str) -> str:
    """SGF文字列内のPB/PWプロパティを匿名化（文字列ベース）

    元のSGFNodeツリーは変更せず、文字列レベルで置換を行う。

    Args:
        sgf_content: SGF文字列（game.root.sgf()の出力）
        pb: 元の黒番プレイヤー名
        pw: 元の白番プレイヤー名

    Returns:
        PB/PWが "Black"/"White" に置換されたSGF文字列
    """
    result = sgf_content

    # PB[name] → PB[Black]
    if pb:
        # SGFでは ] は \] としてエスケープされる
        escaped_pb = pb.replace("\\", "\\\\").replace("]", "\\]")
        result = result.replace(f"PB[{escaped_pb}]", "PB[Black]", 1)

    # PW[name] → PW[White]
    if pw:
        escaped_pw = pw.replace("\\", "\\\\").replace("]", "\\]")
        result = result.replace(f"PW[{escaped_pw}]", "PW[White]", 1)

    return result


def anonymize_karte_content(karte_content: str, pb: str, pw: str) -> str:
    """Karte内のPlayersセクションでプレイヤー名を匿名化

    対象範囲（厳格）:
    - "- Black: {pb}" → "- Black: Black"
    - "- White: {pw}" → "- White: White"

    本文やその他のセクションは一切変更しない。

    Args:
        karte_content: 元のカルテコンテンツ
        pb: 黒番プレイヤー名（元の名前）
        pw: 白番プレイヤー名（元の名前）

    Returns:
        Playersセクションのみ匿名化されたカルテ
    """
    if not pb and not pw:
        return karte_content

    lines = karte_content.split("\n")
    result_lines = []
    in_players_section = False

    for line in lines:
        # ## Players セクションの開始を検出
        if line.strip().startswith("## Players"):
            in_players_section = True
            result_lines.append(line)
            continue

        # 次のセクション（## で始まる）でPlayersセクション終了
        if in_players_section and line.strip().startswith("## "):
            in_players_section = False

        # Playersセクション内の "- Black:" / "- White:" 行のみ置換
        if in_players_section:
            if pb and line.strip().startswith("- Black:"):
                line = line.replace(pb, "Black", 1)
            elif pw and line.strip().startswith("- White:"):
                line = line.replace(pw, "White", 1)

        result_lines.append(line)

    return "\n".join(result_lines)


# --- 出力先ディレクトリ解決 ---


def get_downloads_folder() -> Path:
    """クロスプラットフォームでダウンロードフォルダを取得"""
    if sys.platform == "win32":
        # Windows: USERPROFILE\Downloads
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            downloads = Path(userprofile) / "Downloads"
            if downloads.is_dir():
                return downloads
    # macOS/Linux または Windows フォールバック
    return Path.home() / "Downloads"


def _is_writable_directory(path: Optional[Path]) -> bool:
    """ディレクトリが存在し、書込可能か"""
    if path is None:
        return False
    try:
        p = Path(path) if not isinstance(path, Path) else path
        return p.is_dir() and os.access(p, os.W_OK)
    except (OSError, TypeError):
        # Expected: Invalid path or wrong type
        return False
    except Exception:
        # Unexpected: Internal bug - log with traceback
        import logging
        logging.getLogger(__name__).debug(
            f"Unexpected directory check error: {path}", exc_info=True
        )
        return False


def resolve_output_directory(config_dir: str) -> Path:
    """出力ディレクトリを解決（優先順位付き）

    優先順位:
    1. karte_output_directory（設定済み AND 存在 AND 書込可能）
    2. ダウンロードフォルダ（存在 AND 書込可能）
    3. ホームディレクトリ（フォールバック）
    """
    candidates = [
        Path(config_dir) if config_dir else None,
        get_downloads_folder(),
        Path.home(),
    ]

    for candidate in candidates:
        if candidate and _is_writable_directory(candidate):
            return candidate

    return Path.home()


# --- coach.md 読み込み ---


def load_coach_md() -> str:
    """coach.md を読み込み（複数フォールバック）

    戦略（v5 - 単一フォールバック）:
    1. 開発時パス: katrain/core/reports/ から ../../../docs/03-llm-validation.md
    2. 埋め込みフォールバック（パッケージ/PyInstaller環境）

    Note: importlib.resources は使用しない（docsはパッケージに含まれないため）
    """
    # 開発時パス（__file__ から相対）
    # package_export.py の場所: katrain/core/reports/
    # docs/ の場所: katrain-1.17.0/docs/
    # 相対パス: ../../../docs/
    try:
        dev_path = (
            Path(__file__).parent.parent.parent.parent
            / "docs"
            / "03-llm-validation.md"
        )
        if dev_path.exists():
            return dev_path.read_text(encoding="utf-8")
    except OSError:
        # Expected: File not found or permission denied (PyInstaller environment)
        pass
    except Exception:
        # Unexpected: Internal bug - log with traceback, but still use fallback
        import logging
        logging.getLogger(__name__).debug(
            "Unexpected error loading coach.md", exc_info=True
        )

    # フォールバック（パッケージ環境、PyInstaller等）
    return COACH_MD_FALLBACK


# --- ファイル名生成 ---


def generate_package_filename() -> str:
    """衝突回避付きファイル名を生成

    形式: llm_package_YYYYMMDD-HHMMSS_XXXX.zip
    XXXX: 4桁のランダム英数字
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    random_suffix = "".join(
        random.choices(string.ascii_lowercase + string.digits, k=4)
    )
    return f"llm_package_{timestamp}_{random_suffix}.zip"


# --- manifest生成 ---


def build_manifest(
    game_info: dict[str, Any],
    skill_preset: str,
    anonymized: bool,
) -> dict[str, Any]:
    """manifest.json を生成

    プライバシー保護: 絶対パス、ユーザー名、ファイルサイズは含めない
    """
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generator": {
            "name": "myKatrain",
            "version": VERSION,
        },
        "files": [
            {"name": "karte.md", "type": "karte"},
            {"name": "game.sgf", "type": "sgf"},
            {"name": "coach.md", "type": "reference"},
        ],
        "game_info": {
            "board_size": game_info.get("board_size", 19),
            "handicap": game_info.get("handicap", 0),
            "komi": game_info.get("komi", 6.5),
            "result": game_info.get("result", ""),
            "date": game_info.get("date", ""),
        },
        "settings": {
            "skill_preset": skill_preset,
        },
        "anonymized": anonymized,
    }


# --- メインエクスポート関数（v5: 匿名化はGUI層の責務） ---


def create_llm_package(
    content: PackageContent,
    output_path: Path,
) -> PackageResult:
    """LLMパッケージ（ZIP）を生成

    v5の責務分離:
    - 匿名化は呼び出し元（GUI層）で完了済み
    - この関数は最終文字列をZIPにパッケージするだけ

    Args:
        content: パッケージに含めるコンテンツ（匿名化済み）
                 content.anonymized: manifestのフラグ用
        output_path: 出力先パス

    Returns:
        PackageResult（成功/失敗、出力パス、エラーメッセージ）
    """
    try:
        # manifest 生成
        manifest = build_manifest(
            content.game_info,
            content.skill_preset,
            content.anonymized,
        )

        # ZIP 生成
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("karte.md", content.karte_md.encode("utf-8"))
            zf.writestr("game.sgf", content.sgf_content.encode("utf-8"))
            zf.writestr("coach.md", content.coach_md.encode("utf-8"))
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
            )

        return PackageResult(success=True, output_path=output_path)

    except OSError as e:
        # Expected: File I/O error (includes PermissionError, FileNotFoundError)
        return PackageResult(
            success=False,
            output_path=None,
            error_message=f"File I/O error: {e}",
        )
    except zipfile.BadZipFile as e:
        # Expected: ZIP format error
        return PackageResult(
            success=False,
            output_path=None,
            error_message=f"ZIP format error: {e}",
        )
    except Exception as e:
        # Unexpected: Internal bug - log with traceback
        import logging
        import traceback
        logging.getLogger(__name__).debug(
            f"Unexpected package creation error: {e}\n{traceback.format_exc()}"
        )
        return PackageResult(
            success=False,
            output_path=None,
            error_message=f"Unexpected error: {e}",
        )
