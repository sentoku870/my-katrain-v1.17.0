"""LLM Package Export のユニットテスト

重要: このテストはKivyをインポートしない。
Core層のみをテストし、CIで確実に実行可能。
"""
import json
import zipfile
from pathlib import Path

import pytest

from katrain.core.reports.package_export import (
    COACH_MD_FALLBACK,
    PackageContent,
    PackageResult,
    anonymize_karte_content,
    anonymize_sgf_string,
    build_manifest,
    create_llm_package,
    generate_package_filename,
    get_downloads_folder,
    load_coach_md,
    resolve_output_directory,
    _is_writable_directory,
)


class TestSgfAnonymization:
    """SGF匿名化ロジックのテスト（v4: 文字列ベース）"""

    def test_anonymize_sgf_replaces_pb_pw(self):
        """PB/PWが置換されること"""
        sgf = "(;GM[1]PB[Alice]PW[Bob])"
        result = anonymize_sgf_string(sgf, "Alice", "Bob")
        assert "PB[Black]" in result
        assert "PW[White]" in result

    def test_anonymize_sgf_handles_escaped_brackets(self):
        """エスケープされた ] を含む名前でも正常動作"""
        sgf = "(;GM[1]PB[Name\\]Test]PW[Bob])"
        result = anonymize_sgf_string(sgf, "Name]Test", "Bob")
        assert "PB[Black]" in result
        assert "PW[White]" in result

    def test_anonymize_sgf_empty_names(self):
        """空の名前でもクラッシュしない"""
        sgf = "(;GM[1])"
        result = anonymize_sgf_string(sgf, "", "")
        assert result == sgf

    def test_anonymize_sgf_preserves_other_properties(self):
        """他のプロパティは変更されない"""
        sgf = "(;GM[1]PB[Alice]PW[Bob]SZ[19]KM[6.5])"
        result = anonymize_sgf_string(sgf, "Alice", "Bob")
        assert "SZ[19]" in result
        assert "KM[6.5]" in result

    def test_anonymize_sgf_only_pb(self):
        """PBのみ存在する場合"""
        sgf = "(;GM[1]PB[Alice])"
        result = anonymize_sgf_string(sgf, "Alice", "")
        assert "PB[Black]" in result

    def test_anonymize_sgf_only_pw(self):
        """PWのみ存在する場合"""
        sgf = "(;GM[1]PW[Bob])"
        result = anonymize_sgf_string(sgf, "", "Bob")
        assert "PW[White]" in result

    def test_anonymize_sgf_japanese_names(self):
        """日本語の名前でも動作する"""
        sgf = "(;GM[1]PB[山田太郎]PW[鈴木花子])"
        result = anonymize_sgf_string(sgf, "山田太郎", "鈴木花子")
        assert "PB[Black]" in result
        assert "PW[White]" in result
        assert "山田太郎" not in result
        assert "鈴木花子" not in result


class TestKarteAnonymization:
    """Karte匿名化ロジックのテスト（v4: Playersセクション限定）"""

    def test_anonymize_karte_replaces_players_section(self):
        """Playersセクション内のプレイヤー名が置換されること"""
        karte = """## Players
- Black: Alice (5d)
- White: Bob (3d)

## Summary (Black)
Alice played well in the opening.
"""
        result = anonymize_karte_content(karte, "Alice", "Bob")

        # Playersセクション内は置換される
        assert "- Black: Black (5d)" in result
        assert "- White: White (3d)" in result

        # Summary内の名前は置換されない（意図的）
        assert "Alice played well" in result

    def test_anonymize_karte_only_affects_players_section(self):
        """Playersセクション外の名前は置換されないこと"""
        karte = """## Meta
Alice vs Bob

## Players
- Black: Alice
- White: Bob

## Notes
Alice made a mistake.
"""
        result = anonymize_karte_content(karte, "Alice", "Bob")

        # Metaセクションは変更されない
        assert "Alice vs Bob" in result
        # Notesセクションは変更されない
        assert "Alice made a mistake" in result
        # Playersセクションのみ変更
        assert "- Black: Black" in result
        assert "- White: White" in result

    def test_anonymize_karte_empty_names(self):
        """空の名前でもクラッシュしないこと"""
        karte = "## Players\n- Black: \n- White: "
        result = anonymize_karte_content(karte, "", "")
        assert result == karte

    def test_anonymize_karte_no_players_section(self):
        """Playersセクションがない場合も正常動作"""
        karte = """## Summary
This is a test.
"""
        result = anonymize_karte_content(karte, "Alice", "Bob")
        assert result == karte

    def test_anonymize_karte_with_rank(self):
        """ランク付きの名前でも正常に置換"""
        karte = """## Players
- Black: 山田太郎 (5d)
- White: 鈴木花子 (3d)
"""
        result = anonymize_karte_content(karte, "山田太郎", "鈴木花子")
        assert "- Black: Black (5d)" in result
        assert "- White: White (3d)" in result


class TestManifest:
    """manifest.json 生成のテスト"""

    def test_manifest_schema_version(self):
        """スキーマバージョンが 1.0 であること"""
        manifest = build_manifest({}, "standard", False)
        assert manifest["schema_version"] == "1.0"

    def test_manifest_contains_generator_info(self):
        """generator.name と generator.version が含まれること"""
        manifest = build_manifest({}, "standard", False)
        assert "generator" in manifest
        assert manifest["generator"]["name"] == "myKatrain"
        assert "version" in manifest["generator"]

    def test_manifest_contains_skill_preset(self):
        """settings.skill_preset が含まれること"""
        manifest = build_manifest({}, "advanced", False)
        assert manifest["settings"]["skill_preset"] == "advanced"

    def test_manifest_files_are_relative_only(self):
        """ファイルパスが相対パス（ファイル名のみ）であること"""
        manifest = build_manifest({}, "standard", False)
        for f in manifest["files"]:
            assert "/" not in f["name"]
            assert "\\" not in f["name"]

    def test_manifest_does_not_contain_pii(self):
        """PII（絶対パス、ユーザー名）が含まれないこと"""
        manifest = build_manifest({}, "standard", False)
        manifest_str = json.dumps(manifest)
        assert "C:\\" not in manifest_str
        assert "/Users/" not in manifest_str
        assert "/home/" not in manifest_str

    def test_manifest_game_info(self):
        """game_info が正しく格納されること"""
        game_info = {
            "board_size": 19,
            "handicap": 2,
            "komi": 0.5,
            "result": "B+R",
            "date": "2026-01-17",
        }
        manifest = build_manifest(game_info, "standard", False)
        assert manifest["game_info"]["board_size"] == 19
        assert manifest["game_info"]["handicap"] == 2
        assert manifest["game_info"]["komi"] == 0.5
        assert manifest["game_info"]["result"] == "B+R"
        assert manifest["game_info"]["date"] == "2026-01-17"

    def test_manifest_anonymized_flag(self):
        """匿名化フラグが正しく設定されること"""
        manifest_off = build_manifest({}, "standard", False)
        manifest_on = build_manifest({}, "standard", True)
        assert manifest_off["anonymized"] is False
        assert manifest_on["anonymized"] is True


class TestFilename:
    """ファイル名生成のテスト"""

    def test_filename_format(self):
        """ファイル名形式が正しいこと"""
        filename = generate_package_filename()
        assert filename.startswith("llm_package_")
        assert filename.endswith(".zip")
        # llm_package_YYYYMMDD-HHMMSS_XXXX.zip
        # len = 12 + 15 + 1 + 4 + 4 = 36
        assert len(filename) == 36

    def test_filename_uniqueness(self):
        """連続生成でファイル名が異なること（ランダム部分）"""
        filenames = [generate_package_filename() for _ in range(10)]
        # 少なくとも一部は異なるはず（同一秒内でもランダム部分が異なる）
        assert len(set(filenames)) > 1


class TestZipGeneration:
    """ZIP生成のテスト"""

    def test_create_package_success(self, tmp_path):
        """正常にZIPが生成されること"""
        content = PackageContent(
            karte_md="# Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={"board_size": 19},
        )
        output_path = tmp_path / "test.zip"
        result = create_llm_package(content, output_path)

        assert result.success
        assert output_path.exists()

    def test_zip_contains_required_files(self, tmp_path):
        """ZIPに必須ファイルが含まれること"""
        content = PackageContent(
            karte_md="# Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={},
        )
        output_path = tmp_path / "test.zip"
        create_llm_package(content, output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert "karte.md" in names
            assert "game.sgf" in names
            assert "coach.md" in names
            assert "manifest.json" in names

    def test_zip_content_encoding(self, tmp_path):
        """ZIP内のファイルがUTF-8でエンコードされていること"""
        content = PackageContent(
            karte_md="# カルテ（日本語テスト）",
            sgf_content="(;GM[1]PB[山田太郎])",
            coach_md="# コーチ",
            game_info={},
        )
        output_path = tmp_path / "test.zip"
        create_llm_package(content, output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            karte = zf.read("karte.md").decode("utf-8")
            sgf = zf.read("game.sgf").decode("utf-8")
            coach = zf.read("coach.md").decode("utf-8")

            assert "カルテ" in karte
            assert "山田太郎" in sgf
            assert "コーチ" in coach

    def test_zip_manifest_content(self, tmp_path):
        """manifestの内容が正しいこと"""
        content = PackageContent(
            karte_md="# Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={"board_size": 13, "komi": 5.5},
            skill_preset="advanced",
            anonymized=True,
        )
        output_path = tmp_path / "test.zip"
        create_llm_package(content, output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            assert manifest["game_info"]["board_size"] == 13
            assert manifest["game_info"]["komi"] == 5.5
            assert manifest["settings"]["skill_preset"] == "advanced"
            assert manifest["anonymized"] is True

    def test_create_package_permission_error(self, tmp_path):
        """書き込み不可の場合エラーが返ること"""
        content = PackageContent(
            karte_md="# Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={},
        )
        # 存在しないディレクトリを指定
        output_path = tmp_path / "nonexistent" / "test.zip"
        result = create_llm_package(content, output_path)

        assert not result.success
        assert result.error_message is not None


class TestOutputDirectory:
    """出力先ディレクトリ解決のテスト"""

    def test_priority_config_dir_first(self, tmp_path):
        """設定ディレクトリが最優先されること"""
        config_dir = tmp_path / "config_output"
        config_dir.mkdir()

        result = resolve_output_directory(str(config_dir))
        assert result == config_dir

    def test_fallback_when_config_invalid(self):
        """設定ディレクトリが無効な場合、フォールバック"""
        result = resolve_output_directory("/nonexistent/path")
        assert result.exists()

    def test_fallback_to_home(self):
        """最終フォールバックはホームディレクトリ"""
        result = resolve_output_directory("")
        assert result.exists()

    def test_downloads_folder_exists(self):
        """ダウンロードフォルダ取得が動作すること"""
        downloads = get_downloads_folder()
        # パスが返ること（存在は保証しない）
        assert isinstance(downloads, Path)

    def test_is_writable_directory_valid(self, tmp_path):
        """書き込み可能なディレクトリを正しく判定"""
        assert _is_writable_directory(tmp_path) is True

    def test_is_writable_directory_nonexistent(self):
        """存在しないディレクトリはFalse"""
        assert _is_writable_directory(Path("/nonexistent/path")) is False

    def test_is_writable_directory_none(self):
        """Noneの場合はFalse"""
        assert _is_writable_directory(None) is False


class TestCoachMd:
    """coach.md 読み込みのテスト"""

    def test_load_coach_md_returns_content(self):
        """何らかの内容が返ること"""
        content = load_coach_md()
        assert len(content) > 0

    def test_load_coach_md_contains_guide_content(self):
        """ガイド的な内容が含まれること"""
        content = load_coach_md()
        # フォールバックまたは実ファイルのどちらか
        assert "Coach" in content or "coach" in content or "LLM" in content

    def test_fallback_content_exists(self):
        """フォールバックコンテンツが定義されていること"""
        assert len(COACH_MD_FALLBACK) > 0
        assert "Coach" in COACH_MD_FALLBACK


class TestPackageContentDataclass:
    """PackageContent dataclass のテスト"""

    def test_default_values(self):
        """デフォルト値が正しいこと"""
        content = PackageContent(
            karte_md="# Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={},
        )
        assert content.skill_preset == "standard"
        assert content.anonymized is False

    def test_custom_values(self):
        """カスタム値が設定できること"""
        content = PackageContent(
            karte_md="# Karte",
            sgf_content="(;GM[1])",
            coach_md="# Coach",
            game_info={},
            skill_preset="advanced",
            anonymized=True,
        )
        assert content.skill_preset == "advanced"
        assert content.anonymized is True


class TestPackageResultDataclass:
    """PackageResult dataclass のテスト"""

    def test_success_result(self):
        """成功結果が正しく作成できること"""
        result = PackageResult(success=True, output_path=Path("/tmp/test.zip"))
        assert result.success is True
        assert result.output_path == Path("/tmp/test.zip")
        assert result.error_message is None

    def test_failure_result(self):
        """失敗結果が正しく作成できること"""
        result = PackageResult(
            success=False,
            output_path=None,
            error_message="Permission denied",
        )
        assert result.success is False
        assert result.output_path is None
        assert result.error_message == "Permission denied"
