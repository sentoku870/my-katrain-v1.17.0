# KaTrain Kivy→Qt 移行まとめ

> **作成日**: 2026-01-09
> **対象**: 他のAIや開発者向けの技術移行ドキュメント
> **ステータス**: M6.0 (Kivy削除) 完了

---

## 1. 概要

### 1.1 プロジェクトについて

**KaTrain** は、囲碁AIエンジン KataGo を用いた囲碁学習・解析ツールです。
本プロジェクト (myKatrain) は KaTrain v1.17.0 をフォークし、独自のカルテ機能追加とGUIフレームワーク移行を行いました。

### 1.2 移行の目的

| 観点 | Kivy | Qt (PySide6) |
|------|------|--------------|
| **安定性** | Windows/macOS で DPI問題、起動トラブル多発 | 安定した商用品質 |
| **配布** | PyInstaller 設定が複雑 | 標準的なバンドル |
| **メンテナンス** | KivyMD 依存、更新停滞 | 長期サポート |
| **学習コスト** | Kivy独自のkv言語 | 広く使われるQt |

### 1.3 移行戦略

**段階的移行 (Incremental Migration)**:
1. Qtフロントエンドを並行開発 (`katrain_qt/`)
2. コアロジック (`katrain/core/`) は読み取り専用で保持
3. 機能パリティ達成後、Kivyコードを削除

---

## 2. アーキテクチャ比較

### 2.1 移行前 (Kivy)

```
katrain/
├── __main__.py          ← Kivy App エントリーポイント (1,432行)
├── gui/                 ← Kivy GUI コード (28ファイル)
│   ├── badukpan.py      ← 碁盤描画 (1,295行)
│   ├── controlspanel.py ← 右パネル (350行)
│   ├── popups.py        ← ダイアログ (960行)
│   ├── kivyutils.py     ← Kivy ヘルパー (685行)
│   ├── widgets/         ← カスタムウィジェット
│   └── features/        ← 機能モジュール
├── gui.kv               ← Kivy レイアウト (1,264行)
├── popups.kv            ← ポップアップレイアウト (918行)
└── core/                ← ゲームロジック (保持)
```

**依存関係**:
- `kivy>=2.3.1`
- `kivymd==0.104.1`
- `ffpyplayer>=4.5.1`

### 2.2 移行後 (Qt)

```
katrain_qt/                    ← 新規 Qt パッケージ
├── __init__.py
├── __main__.py                ← python -m katrain_qt
├── app_qt.py                  ← メインウィンドウ (~1,300行)
├── core_adapter.py            ← コアラッパー (~600行)
├── settings.py                ← 設定管理
├── analysis/
│   ├── models.py              ← データクラス
│   └── katago_engine.py       ← QProcess ベースエンジン
├── widgets/
│   ├── board_widget.py        ← 碁盤ウィジェット
│   ├── candidates_panel.py    ← 候補手パネル
│   ├── analysis_panel.py      ← 解析パネル
│   └── score_graph.py         ← スコアグラフ
└── dialogs/
    └── settings_dialog.py     ← 設定ダイアログ

katrain/
├── __main__.py                ← Qt へリダイレクト (12行)
└── core/                      ← ゲームロジック (保持、Kivyインポート削除)
```

**依存関係**:
- `PySide6>=6.6.0`

---

## 3. 移行フェーズとマイルストーン

### 3.1 フェーズ概要

| フェーズ | 期間 | 目標 |
|----------|------|------|
| Phase 3 | M3.0-M3.4 | 基本Qt UI、Kivyシム、KataGo統合 |
| Phase 4 | M4.1-M4.5 | フル機能 (MVR: Minimum Viable Replacement) |
| Phase 5 | M5.0-M5.2 | 機能パリティ、Kivy不要化 |
| Phase 6 | M6.0 | Kivy完全削除 |

### 3.2 詳細マイルストーン

#### Phase 3: 基盤構築

| マイルストーン | 内容 | 成果物 |
|----------------|------|--------|
| M3.0 | Qt プロジェクト構造 | `katrain_qt/` パッケージ |
| M3.1 | Kivy シム | `compat/kivy_shim.py` |
| M3.2 | GameAdapter | `core_adapter.py` |
| M3.3 | クリックプレイ | 碁盤クリックで石を置く |
| M3.4 | KataGo 統合 | `analysis/katago_engine.py` |

#### Phase 4: フル機能 (MVR)

| マイルストーン | 内容 | テスト数 |
|----------------|------|----------|
| M4.1 | スコアグラフ | `score_graph.py` |
| M4.2 | 解析パネル + PV表示 | `analysis_panel.py` |
| M4.3 | 設定ダイアログ + 永続化 | `settings_dialog.py`, `settings.py` |
| M4.4 | SGF保存 + ラウンドトリップ | Save/Save As |
| M4.5 | ダーティ状態管理 | 172テスト |

#### Phase 5: 機能パリティ

| マイルストーン | 内容 | テスト数 |
|----------------|------|----------|
| M5.0 | Kivy不要ランタイム | `pip install .` でQt動作 |
| M5.0b | Windows配布 (PyInstaller) | `KaTrainQt.exe` |
| M5.1a | バリエーション選択 | 30テスト追加 (計202) |
| M5.1b | コメント編集 | 20テスト追加 (計222) |
| M5.2 | テリトリーオーバーレイ | 11テスト追加 (計233) |

#### Phase 6: Kivy削除

| マイルストーン | 内容 | 削除行数 |
|----------------|------|----------|
| M6.0 | Kivy GUI 完全削除 | ~13,000行 |

---

## 4. 削除されたKivyコード

### 4.1 削除ファイル一覧 (38ファイル)

#### メインエントリーポイント
| ファイル | 行数 | 役割 |
|----------|------|------|
| `katrain/__main__.py` | 1,432→12 | Kivy App → Qt リダイレクト |

#### GUI コンポーネント (7ファイル)
| ファイル | 行数 | 役割 |
|----------|------|------|
| `katrain/gui.kv` | 1,264 | Kivy レイアウト定義 |
| `katrain/gui/badukpan.py` | 1,295 | 碁盤描画 |
| `katrain/gui/controlspanel.py` | 350 | 右パネル |
| `katrain/gui/popups.py` | 960 | ダイアログ管理 |
| `katrain/gui/kivyutils.py` | 685 | Kivy ヘルパー |
| `katrain/gui/theme.py` | 222 | テーマ管理 |
| `katrain/gui/sound.py` | 37 | サウンド再生 |

#### ウィジェット (6ファイル)
| ファイル | 行数 | 役割 |
|----------|------|------|
| `katrain/gui/widgets/graph.py` | 353 | スコアグラフ |
| `katrain/gui/widgets/movetree.py` | 331 | 手順ツリー |
| `katrain/gui/widgets/filebrowser.py` | 490 | ファイルブラウザ |
| `katrain/gui/widgets/progress_loader.py` | 129 | プログレス表示 |
| `katrain/gui/widgets/selection_slider.py` | 135 | スライダー |
| `katrain/gui/widgets/helpers.py` | 121 | ヘルパー関数 |

#### 機能モジュール (13ファイル)
| モジュール | 主要ファイル | 行数合計 |
|------------|--------------|----------|
| クイズ | `quiz_popup.py`, `quiz_session.py` | ~400 |
| バッチ解析 | `batch_core.py`, `batch_ui.py` | ~870 |
| カルテ出力 | `karte_export.py` | ~200 |
| 設定 | `settings_popup.py` | ~440 |
| サマリ | `summary_*.py` (5ファイル) | ~1,800 |
| 共通 | `context.py`, `types.py` | ~200 |

#### レイアウトファイル
| ファイル | 行数 |
|----------|------|
| `katrain/popups.kv` | 918 |

### 4.2 削除の影響

| 項目 | 削除前 | 削除後 | 削減率 |
|------|--------|--------|--------|
| **GUIコード行数** | ~13,000 | ~5,000 (Qt) | 62%削減 |
| **ファイル数** | 38 | 15 (Qt) | 60%削減 |
| **依存パッケージ** | 3 (kivy, kivymd, ffpyplayer) | 1 (PySide6) | 67%削減 |

---

## 5. 新規作成されたQtコード

### 5.1 ファイル構造

```
katrain_qt/                          # ~5,000行
├── __init__.py                      # パッケージ初期化
├── __main__.py                      # エントリーポイント
├── app_qt.py                        # メインウィンドウ (~1,300行)
├── core_adapter.py                  # コアラッパー (~600行)
├── settings.py                      # 設定管理 (~400行)
│
├── analysis/                        # KataGo 統合
│   ├── __init__.py
│   ├── models.py                    # データクラス (~300行)
│   └── katago_engine.py             # QProcess エンジン (~500行)
│
├── widgets/                         # UI コンポーネント
│   ├── __init__.py
│   ├── board_widget.py              # 碁盤 (~600行)
│   ├── candidates_panel.py          # 候補手 (~200行)
│   ├── analysis_panel.py            # 解析詳細 (~300行)
│   └── score_graph.py               # スコアグラフ (~400行)
│
└── dialogs/                         # ダイアログ
    ├── __init__.py
    └── settings_dialog.py           # 設定 (~400行)
```

### 5.2 主要クラス

#### MainWindow (app_qt.py)

```python
class MainWindow(QMainWindow):
    """メインアプリケーションウィンドウ"""

    # 主要コンポーネント
    adapter: GameAdapter           # コアラッパー
    engine: KataGoEngine           # 解析エンジン
    board_widget: GoBoardWidget    # 碁盤
    candidates_panel: CandidatesPanel
    analysis_panel: AnalysisPanel
    score_graph: ScoreGraphWidget

    # 主要機能
    def _open_sgf()                # SGF読み込み
    def _do_save()                 # SGF保存
    def _toggle_analysis()         # 解析ON/OFF
    def _on_position_changed()     # 局面変更時の更新
```

#### GameAdapter (core_adapter.py)

```python
class GameAdapter(QObject):
    """KaTrain コアのQtラッパー"""

    # シグナル
    position_changed = Signal()
    status_changed = Signal(str)
    error_occurred = Signal(str)

    # ゲーム操作
    def new_game(size, komi, rules)
    def load_sgf_file(path)
    def play_move_qt(qt_col, qt_row)  # Qt座標で石を置く

    # ナビゲーション
    def nav_first() / nav_prev() / nav_next() / nav_last()
    def nav_to_move(move_number)

    # バリエーション
    def has_variations()
    def switch_to_sibling(index)

    # 座標変換 (内部)
    # Core (row=0 at bottom) ↔ Qt (row=0 at top)
```

#### KataGoEngine (analysis/katago_engine.py)

```python
class KataGoEngine(QObject):
    """QProcess ベースの KataGo マネージャー"""

    # シグナル
    ready = Signal()
    analysis_received = Signal(AnalysisResult)
    error_occurred = Signal(str)

    # 主要メソッド
    def start()                    # プロセス起動
    def stop()                     # プロセス終了
    def query_async(snapshot)      # 非同期クエリ
```

### 5.3 データモデル (analysis/models.py)

```python
@dataclass
class CandidateMove:
    """候補手"""
    col: int               # Qt列 (0-18)
    row: int               # Qt行 (0-18, 0=上)
    rank: int              # 順位 (0=最善)
    score_lead: float      # 目数リード
    visits: int            # 探索数
    winrate: float         # 勝率
    pv: list[str]          # 読み筋 (GTP形式)

@dataclass
class AnalysisResult:
    """解析結果"""
    candidates: list[CandidateMove]
    score_lead_black: float    # 黒から見た目数リード
    winrate_black: float       # 黒の勝率 (0.0-1.0)
    next_player: str           # "B" or "W"
    ownership: list[list[float]]  # テリトリー (-1.0〜+1.0)
```

---

## 6. コア部分への変更

### 6.1 保持されたファイル

`katrain/core/` ディレクトリは**ほぼそのまま保持**:

| ファイル | 役割 | 変更 |
|----------|------|------|
| `game.py` | BaseGame クラス | Kivy import 削除のみ |
| `game_node.py` | GameNode クラス | 変更なし |
| `engine.py` | KataGo プロセス管理 | platform 取得方法変更 |
| `sgf_parser.py` | SGF パース | 変更なし |
| `base_katrain.py` | 抽象ベースクラス | Kivy Config/JsonStore 削除 |
| `lang.py` | 多言語対応 | Observable 削除 |
| `analysis/` | 解析ロジック | 変更なし |

### 6.2 Kivy インポートの削除

#### game.py
```python
# 削除
from kivy.clock import Clock  # 未使用だった
```

#### engine.py
```python
# 変更前
from kivy.utils import platform as kivy_platform

# 変更後
import sys
kivy_platform = sys.platform
if kivy_platform == "win32":
    kivy_platform = "win"
elif kivy_platform == "darwin":
    kivy_platform = "macosx"
```

#### base_katrain.py
```python
# 削除
from kivy import Config
from kivy.storage.jsonstore import JsonStore

# 追加 (純Python実装)
class JsonStore:
    """Kivy JsonStore 互換の純Python実装"""
    def __init__(self, filename, indent=4):
        self.filename = filename
        self._data = {}
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
```

#### lang.py
```python
# 削除
from kivy._event import Observable

# 変更: Lang クラスを簡略化
class Lang:
    """多言語対応クラス (Kivy Observable 不要)"""
```

---

## 7. 座標系とスコア規約

### 7.1 3つの座標系

| 座標系 | Row原点 | 使用箇所 | 例 (D4) |
|--------|---------|----------|---------|
| **KaTrain Core** | row=0 が下 | `katrain.core`, `Move.coords` | `(3, 3)` |
| **Qt Rendering** | row=0 が上 | `board_widget.py`, UI | `(3, 15)` |
| **GTP String** | 1始まり、下から | KataGo JSON, 表示 | `"D4"` |

### 7.2 変換公式

```python
# Core → Qt
qt_row = (board_size - 1) - core_row

# Qt → Core
core_row = (board_size - 1) - qt_row

# Qt → GTP
gtp_col = "ABCDEFGHJKLMNOPQRST"[col]  # 'I'をスキップ
gtp_num = board_size - qt_row
```

### 7.3 変換レイヤー

| レイヤー | 責務 | ファイル |
|----------|------|----------|
| Layer 1 | Core ↔ Qt 行フリップ | `core_adapter.py` |
| Layer 2 | Qt ↔ GTP 文字列 | `analysis/models.py` |

### 7.4 スコア規約

**すべてのスコアは黒視点で正規化**:

| 値 | 意味 |
|-----|------|
| `score_lead_black > 0` | 黒有利 |
| `score_lead_black < 0` | 白有利 |
| `winrate_black` | 黒の勝率 (0.0-1.0) |

```python
# KataGo は手番視点で返すので変換
score_lead_black = score_lead_to_play if next_player == "B" else -score_lead_to_play
winrate_black = winrate_to_play if next_player == "B" else 1.0 - winrate_to_play
```

---

## 8. テスト戦略

### 8.1 テスト構造

```
tests/
├── conftest.py              ← ルート (eval_metrics テスト用)
└── katrain_qt/              ← Qt テスト専用
    ├── conftest.py          ← Kivy シム不要
    ├── test_coordinate_conversion.py   # 48テスト
    ├── test_katago_parsing.py          # 66テスト
    ├── test_settings.py                # 14テスト
    ├── test_variations.py              # 30テスト
    ├── test_comments.py                # 20テスト
    ├── test_ownership.py               # 12テスト
    ├── test_dirty_state.py             # 23テスト
    ├── test_sgf_save.py                # 19テスト
    └── test_window_state.py            # 5テスト
```

### 8.2 テスト数の推移

| マイルストーン | テスト数 | 追加数 |
|----------------|----------|--------|
| M4.5 (MVR) | 172 | - |
| M5.1a (バリエーション) | 202 | +30 |
| M5.1b (コメント) | 222 | +20 |
| M5.2 (テリトリー) | 233 | +11 |
| M6.0 (Kivy削除後) | 239 | +6 |

### 8.3 テスト実行

```bash
# Qt テストのみ (Kivy不要)
uv run pytest tests/katrain_qt/ -v

# 特定テスト
uv run pytest tests/katrain_qt/test_variations.py -v
```

---

## 9. 未実装機能

### 9.1 現在未実装

| 機能 | 優先度 | 備考 |
|------|--------|------|
| サウンド効果 | P3 | QMediaPlayer で実装予定 |
| 多言語対応 (i18n) | P3 | Qt翻訳 (.qm) 必要 |
| テーマ/ダークモード | P4 | QSS スタイルシート |
| 対局タイマー | P4 | QTimer で実装可能 |
| AI vs AI 対局 | P5 | 延期 |
| 教育モード | P5 | 延期 |

### 9.2 延期の理由

- **P3-P4**: 機能的には重要だが、基本的な囲碁解析には不要
- **P5**: 個人利用では不要と判断

---

## 10. ビルドと配布

### 10.1 開発環境

```bash
# インストール
pip install -e .

# または uv を使用
uv sync
```

### 10.2 Windows 実行ファイル

```powershell
# ビルド
.\tools\build_windows.ps1

# 出力
dist\KaTrainQt\KaTrainQt.exe
```

### 10.3 KataGo 設定

KataGo は**バンドルされません**。ユーザーが手動で設定:

1. KataGo を https://github.com/lightvector/KataGo/releases からダウンロード
2. モデルファイルをダウンロード
3. 設定ダイアログでパスを指定:
   - Executable: `C:\KataGo\katago.exe`
   - Config: `C:\KataGo\analysis.cfg`
   - Model: `C:\KataGo\model.bin.gz`

---

## 11. 参考資料

### 11.1 関連ドキュメント

| ドキュメント | 場所 |
|--------------|------|
| ロードマップ | `docs/01-roadmap.md` |
| コード構造 | `docs/02-code-structure.md` |
| Qt README | `katrain_qt/README.md` |

### 11.2 主要コミット

| コミット | 内容 |
|----------|------|
| `e423f2b` | Phase 1-2 Kivy残骸クリーンアップ |
| `62b4549` | Phase 2 簡略化マージ |

### 11.3 ブランチ

| ブランチ | 用途 |
|----------|------|
| `main` | 現在の開発 (Qt のみ) |
| `legacy-kivy` | Kivy バージョンのアーカイブ |

---

## 12. 移行のポイントまとめ

### 12.1 成功要因

1. **段階的移行**: 一気に置き換えず、並行開発してから切り替え
2. **コア分離**: `katrain/core/` を読み取り専用として保護
3. **シム活用**: Kivy インポートをモックして Qt テストを先行実行
4. **テスト駆動**: 各マイルストーンで十分なテストカバレッジ

### 12.2 注意点

1. **座標系の違い**: Core (下原点) vs Qt (上原点) の変換を一箇所に集約
2. **スコア規約**: 常に黒視点で正規化して混乱を防止
3. **シグナル設計**: Qt シグナルで疎結合を維持

### 12.3 他のプロジェクトへの適用

この移行パターンは以下の条件で有効:
- コアロジックとGUIが明確に分離されている
- 段階的な機能移植が可能
- 十分なテストインフラがある

---

*このドキュメントは KaTrain Kivy→Qt 移行プロジェクトの完了記録として作成されました。*
