# Phase 89 実装計画: 自動（まず動かす）モード

> **ステータス**: ✅ 完了（2026-01-30）
> **PR**: #230

## 1. 概要

**Phase**: 89
**タイトル**: "まず動かす" 自動モード
**修正レベル**: Lv4（大規模: 4ファイル超）
**Git フロー**: `feature/2026-01-30-phase89-auto-setup-mode` → PR

### 目的
PC初心者が初回起動で「解析が1回成功」する確率を最大化する。
- 最小要件で確実に動く設定を自動選択
- OpenCL失敗時はCPUへ自動フォールバック
- 軽量モデル（b10c128）を固定使用

### 非目的（この Phase ではやらない）
- 軽量モデルの自動ダウンロード（Phase 90以降）
- CUDA/TensorRTの自動セットアップ（Phase 90以降）
- 性能最適化の自動チューニング
- Standard/Advanced モードのUI変更（Phase 90以降）

---

## 2. 実装成果物

### 新規ファイル
- `katrain/core/auto_setup.py` (~352行) - 自動セットアップコアロジック
- `katrain/core/test_analysis.py` (~188行) - エラー分類・テスト解析結果
- `katrain/gui/features/auto_mode_popup.py` (~743行) - 自動セットアップUI
- `tests/test_auto_setup.py` (~339行) - 23テスト
- `tests/test_test_analysis.py` (~318行) - 43テスト

### 変更ファイル
- `katrain/__main__.py` (+200行) - engine_unhealthy属性、restart_engine_with_fallback()等
- `katrain/core/engine.py` (+57行) - get_backend_type()、create_minimal_analysis_query()
- `katrain/gui/features/settings_popup.py` (+45行) - Auto Setupタブ（tab4）
- `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` (+70行) - 24翻訳キー
- `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` (+70行) - 24翻訳キー

### 追加API
- `ErrorCategory` Enum - ENGINE_START_FAILED, MODEL_LOAD_FAILED, BACKEND_ERROR, TIMEOUT, LIGHTWEIGHT_MISSING, UNKNOWN
- `TestAnalysisResult` frozen dataclass - success, error_category, error_message
- `classify_engine_error()` - 2段階パターンマッチング（強/弱シグナル）
- `get_auto_setup_config()` - 新規/既存ユーザー判定とモード決定
- `should_show_auto_tab_first()` - Autoタブ優先表示判定
- `find_lightweight_model()` - b10c128軽量モデル検索
- `find_cpu_katago()` - CPU版KataGo（Eigen）検索
- `resolve_auto_engine_settings()` - 自動モード用エンジン設定構築

---

## 3. 技術仕様

### 新規ユーザー検出
- USER_CONFIG_FILE存在チェックに基づく
- 新規ユーザー → mode="auto"
- 既存ユーザー（カスタム設定あり）→ mode="advanced"
- 既存ユーザー（カスタム設定なし）→ mode="standard"

### エラー分類
2段階パターンマッチング:
- 強シグナル: clGetPlatformIDs, cl_out_of_resources, OpenCL error等
- 弱シグナル: GPU error, CUDA failed等

### CPUフォールバック
- OpenCL失敗時にEigen版へ自動切替
- 検証付き永続化（検証成功時のみengine.katagoを保存）

### スレッド安全性
- AutoModeStateクラス（per-popup状態管理）
- Clock.schedule_once()によるメインスレッドUI更新

### パス解決
- DATA_FOLDER定数使用（ハードコードなし）
- get_model_search_dirs()でユーザー/パッケージディレクトリ検索

---

## 4. テスト結果

- 全テスト: 3297件パス（+66件）
- CI安全: 実KataGoバイナリ・GPU・OpenCL不要
