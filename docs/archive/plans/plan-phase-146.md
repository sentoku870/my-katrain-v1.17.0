# Phase 146: Kivy ヘッドレステスト基盤

> 開始日: 2026-06-26
> 規模: XL (Lv5)
> 主成果物: `KivyUnitTest` モックレイヤー
> ブランチ: `feature/phase-146-kivy-headless-base`

---

## 1. 目的

GUI 層 (`katrain/gui/`) のテスト自動化を可能にするため、Kivy ランタイムを
**メモリ内でスタブ化**する `KivyUnitTest` ベースクラスと 4 つの代表クラス
スタブを整備する。

### ゴール

| 項目 | 目標 |
|------|------|
| GUI テストカバレッジ | 21% → 40% へ引き上げ（Phase 147+ で実施） |
| CI での GUI テスト自動実行 | 既存 CI フローに統合 |
| テスト基盤の保守性 | Phase 147 以降のテスト追加がコピペで可能 |
| アーキテクチャ整合性 | core 層の Kivy 非依存を維持 |

### 非ゴール

- 実際の GUI テスト追加（Phase 147）
- pytest-kivy プラグイン採用（外部依存最小化）
- BadukPanWidget の完全モック（公開メソッドのみ）
- 実 KaTrainGui インスタンスの生成
- KV ファイルの読み込み

---

## 2. 背景

### 2.1 現状

- 125 テストファイルが存在
- 既存テストは `MagicMock` / `sys.modules` パッチ経由で Kivy を扱う
- ただし `katrain/gui/` 配下のテストは皆無
- ロードマップ L159-165 で「GUI テストカバレッジ 21% → 40-50% (Kivy mock 基盤)」
  が将来拡張候補として挙げられている

### 2.2 アーキテクチャレビュー結果（2026-06-26）

- `architecture-review-2026-06-26.md:286-293` で **P2-7: Kivy ヘッドレステスト
  基盤の整備** が提案されている
- 評価: 効果=H、コスト=**XL**（Kivy ヘッドレスモック導入）、リスク=M、**Lv: Lv5**

### 2.3 既存資産

- `MockKaTrainStub` (`tests/conftest.py:401-439`): KaTrainBase の最小スタブ
- `MockEngine` (`tests/conftest.py:442-491`): engine の呼び出し追跡 mock
- `MockKaTrainWithAI` (`tests/conftest.py:654-810`): AI config 拡張 mock
- CI 環境変数 (`test_and_build.yaml:75-82`): `KIVY_HEADLESS` 系の実証済
- 既存 skipif パターン: `tests/test_stability_phase18.py:18-33`

---

## 3. アーキテクチャ方針

### 3.1 採用案: KivyUnitTest ベースクラス

**判断基準**:
- 軸(対象範囲) = A 局所機能
- 軸(継続性) = C 長期
- 軸(精度要求) = B ある程度信頼
- 軸(自動化) = C ほぼ全自動

**採用理由**:
1. 既存 `MockKaTrainStub` パターンの自然な拡張
2. 環境変数パッチを 1 箇所に集約
3. 派生クラスは opt-in（既存テストへの副作用なし）
4. Phase 147 でテスト追加時に再利用容易

### 3.2 採用しなかった案

| 案 | 不採用理由 |
|----|------------|
| conftest.py の autouse フィクスチャ化 | 既存 125 ファイルへの影響大、意図しない副作用リスク |
| pytest-kivy プラグイン | 外部依存追加、Kivy 公式サポートが薄く CI 互換性未確認 |
| ハイブリッド（KivyUnitTest + autouse） | 柔軟性高だが Phase 147 で評価、現時点では過剰 |

### 3.3 core/gui 境界ルール厳守

- Phase 143-A 完了状態（`kivy_import_allowlist.json: entries={}`）を**壊さない**
- 新規 import はテストファイルのみ
- `katrain/` 配下には1行も追加しない
- `TestKivyIsolation` の既存テスト範囲を明示

---

## 4. 成果物

### 4.1 新規ファイル

| ファイル | 行数目安 | 役割 |
|----------|---------|------|
| `tests/kivy_test_base.py` | 60-80 | `KivyUnitTest` ベースクラス |
| `tests/kivy_stubs.py` | 100-130 | 4 クラススタブ＋`make_*_stub` ファクトリ |
| `tests/test_kivy_headless_smoke.py` | 80-120 | 基盤自身のスモークテスト（6-8 テスト） |
| `docs/06-kivy-headless-testing.md` | 80-120 | 使い方ガイド |
| `docs/archive/plans/plan-phase-146.md` | 200-300 | 本計画書 |

### 4.2 修正ファイル

| ファイル | 変更内容 |
|----------|---------|
| `tests/test_architecture.py` | `TestKivyHeadlessIsolation` クラス追加（20-30行） |
| `pyproject.toml` | `kivy_headless` マーカー追加（1行） |
| `.github/workflows/test_and_build.yaml` | `KIVY_NO_WINDOW: 1` 追加（2箇所） |
| `docs/01-roadmap.md` | Phase 146 完了記録（5行） |

**合計**: 新規 5 / 修正 4 ファイル、**追加コード ~500-700行**

---

## 5. 設計詳細

### 5.1 `KivyUnitTest` ベースクラス

```python
class KivyUnitTest:
    KIVY_ENV_VARS: ClassVar[dict[str, str]] = {
        "KIVY_NO_ARGS": "1",
        "KIVY_NO_FILELOG": "1",
        "KIVY_NO_CONSOLELOG": "1",
        "KIVY_NO_ENV_CONFIG": "1",
        "KIVY_HEADLESS": "1",
        "KIVY_NO_WINDOW": "1",
        "KIVY_GL_BACKEND": "mock",
        "SDL_VIDEODRIVER": "dummy",
    }

    def setup_method(self, method):
        self._original_env = {k: os.environ.get(k) for k in self.KIVY_ENV_VARS}
        os.environ.update(self.KIVY_ENV_VARS)

    def teardown_method(self, method):
        for k, v in self._original_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
```

**設計判断**:
- `unittest.TestCase` を継承**しない**（pytest の setup/teardown メソッドを使う）
- 環境変数パッチは**メソッド単位**で自動復元（CI 安全）
- autouse フィクスチャには**しない**（明示的に継承する＝意図的な opt-in）
- `KIVY_NO_WINDOW=1` を含めることで `Window` インスタンス化を回避

### 5.2 4 クラススタブ

`tests/kivy_stubs.py` に以下を定義:

| スタブ | 実体の場所 | 提供メソッド/属性 |
|--------|-----------|------------------|
| `KaTrainGuiStub` | `katrain/__main__.py:140` | `engine`, `controls`, `ivar`, `game`, `current_node`, `update_state()`, `config()`, `log()` |
| `ControlsPanelStub` | `katrain/gui/controlspanel.py:514` | `update_state()`, `set_active()`, `switch_control_panel()`, `new_game()`, `set_status()` |
| `BadukPanWidgetStub` | `katrain/gui/badukpan.py:1630` | `update_state()`, `draw_board()`, `set_handicap()`, `animate_stone_placement()`, `redraw()` |
| `PopupStub` | `kivy.uix.popup.Popup` | `open()`, `dismiss()`, `content`, `title`, `size_hint`, `auto_dismiss` |

それぞれ `MagicMock` ベース、属性タプルで API surface を明示。
`make_*_stub()` ファクトリ関数で生成。

### 5.3 環境変数の根拠

| 環境変数 | 効果 | 既存出典 |
|---------|------|---------|
| `KIVY_NO_ARGS=1` | Kivy 引数パーサ抑止 | `katrain/tools/batch_analyze_sgf.py:25` |
| `KIVY_NO_FILELOG=1` | ファイルログ抑止 | `test_and_build.yaml:76` |
| `KIVY_NO_CONSOLELOG=1` | コンソールログ抑止 | `test_and_build.yaml:77` |
| `KIVY_NO_ENV_CONFIG=1` | 環境設定読込抑止 | `test_and_build.yaml:78` |
| `KIVY_HEADLESS=1` | ヘッドレスモード | `spec/KaTrain.spec:8` |
| `KIVY_NO_WINDOW=1` | ウィンドウ作成抑止 | `spec/KaTrain.spec:9` |
| `KIVY_GL_BACKEND=mock` | GL バックエンドモック | `test_and_build.yaml:79` |
| `SDL_VIDEODRIVER=dummy` | SDL2 ダミー | `test_and_build.yaml:80` |

---

## 6. 実装手順

### 6.1 事前準備
```bash
git checkout -b feature/phase-146-kivy-headless-base
```

### 6.2 ファイル作成（opencode 実行）

1. `tests/kivy_test_base.py`
2. `tests/kivy_stubs.py`
3. `tests/test_kivy_headless_smoke.py`

### 6.3 既存ファイル修正

4. `tests/test_architecture.py` に `TestKivyHeadlessIsolation` 追加
5. `pyproject.toml` の markers に `kivy_headless` 追加
6. `.github/workflows/test_and_build.yaml` に `KIVY_NO_WINDOW: 1` 追加

### 6.4 ドキュメント

7. `docs/06-kivy-headless-testing.md` 新規作成
8. `docs/01-roadmap.md` を更新

### 6.5 動作確認

```bash
# UTF-8 強制（Windows PowerShell）
$env:PYTHONUTF8 = "1"

# スモークテスト
uv run pytest tests/test_kivy_headless_smoke.py -v

# アーキテクチャテスト
uv run pytest tests/test_architecture.py -v

# 既存テスト無影響
uv run pytest tests -v

# mypy strict
uv run mypy katrain tests
```

### 6.6 PR 作成

```bash
git add .
git commit -m "Phase 146: KivyUnitTest ヘッドレステスト基盤を追加"
git push -u origin feature/phase-146-kivy-headless-base
gh pr create --title "Phase 146: Kivy ヘッドレステスト基盤" --body "..."
```

---

## 7. テスト戦略

### 7.1 Phase 146 内で書くテスト（スモーク）

`tests/test_kivy_headless_smoke.py`:

| テスト | 検証内容 |
|--------|---------|
| `test_kivy_env_vars_set_in_method` | setup_method で環境変数がセットされる |
| `test_setup_and_teardown_idempotent` | 連続実行でも安全 |
| `test_ka_train_gui_stub_has_all_required_attrs` | KaTrainGuiStub の API surface |
| `test_controls_panel_stub_has_all_required_attrs` | ControlsPanelStub |
| `test_baduk_pan_widget_stub_has_all_required_attrs` | BadukPanWidgetStub |
| `test_popup_stub_has_all_required_attrs` | PopupStub |
| `test_popup_stub_open_dismiss` | open/dismiss シーケンス |
| `test_all_stubs_creatable` | 4 種スタブ生成可能 |

### 7.2 Phase 147 で書くテスト（範囲外・計画のみ）

- orchestration.py / curator/ の Manager 経由テスト
- 4 スタブを使った統合テスト
- badukpan.py の draw 系メソッド

---

## 8. リスク評価

| リスク | 影響 | 確率 | 軽減策 |
|--------|------|------|--------|
| R1: Kivy import 時の SDL 初期化失敗 | テスト実行不可 | M | `KIVY_GL_BACKEND=mock` + `SDL_VIDEODRIVER=dummy` で完全抑止（CI で実証済） |
| R2: スタブの drift（実クラス API 変更時の追従漏れ） | 偽陽性テスト | M | 4 クラス最小、現実的 API surface のみ。Phase 147 で拡張時に更新 |
| R3: `KivyUnitTest` と既存テストの import 順序競合 | 既存テスト破壊 | L | autouse にしない、setup_method で完全初期化 |
| R4: core 層への Kivy 漏れ（境界違反） | アーキ破壊 | L | `TestKivyIsolation` 既存テスト + 新規 `TestKivyHeadlessIsolation` で二重ガード |
| R5: conftest.py 追加でテスト全体が遅延 | CI 遅延 | L | KivyUnitTest は明示的継承のみ。既存 125 ファイルへの影響なし |
| R6: Phase 147 でテスト書けず基盤が形骸化 | 投資浪費 | L | 147 着手前提だが、Phase 146 内にスモークテストで実用性確認 |

---

## 9. 完了判定（Definition of Done）

- [ ] `tests/kivy_test_base.py` / `kivy_stubs.py` / `test_kivy_headless_smoke.py` 作成
- [ ] `tests/test_architecture.py` / `pyproject.toml` / `test_and_build.yaml` 更新
- [ ] `docs/06-kivy-headless-testing.md` 作成
- [ ] `docs/01-roadmap.md` の Phase 146 行を ✅ に
- [ ] `docs/archive/plans/plan-phase-146.md` 作成
- [ ] ローカル: 8 スモークテスト + 既存全テスト + mypy パス
- [ ] CI: 3 ジョブ（typecheck/test/coverage）すべて緑
- [ ] `kivy_import_allowlist.json` 変更なし
- [ ] PR レビュー承認・マージ

---

## 10. 変更履歴

- 2026-06-26: 計画書作成（Phase 146 着手）
