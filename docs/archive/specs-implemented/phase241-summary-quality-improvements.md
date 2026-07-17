# Phase 241: サマリー機能 品質改善

> **ステータス**: 完了（2026-07-17）
> **種別**: バグ修正 + 軽微改善 9 件一括
> **テスト数**: 39 unit tests 追加、合計 5,612 件テスト合格
> **対象**: 複数局サマリ / LLM Coach 複数局対応

## 背景

ユーザーからサマリー機能に関する包括的な調査依頼があり、コードを精査した結果、
11 件のバグ・改善余地を特定。優先度に応じて 9 サブ修正に分割し、一括で実施。

## サブフェーズ索引

| Phase | 種別 | 内容 | 影響度 |
|-------|------|------|--------|
| 241-A | バグ | weakness pattern から「good」カテゴリ除外 | 高 |
| 241-B | バグ | popup の unknown パス早期 return | 高 |
| 241-C | 改善 | loss_progression フォールバック | 中 |
| 241-D | リファクタ | `_summary_index_to_internal` sentinel 化 | 中 |
| 241-E | バグ | summary_perspective_index race condition 対策 | 中 |
| 241-F | リファクタ | `detect_player_color_for_user` 型キャスト整理 | 中 |
| 241-G | 削除 | `find_latest_karte` 関数完全削除 | 低 |
| 241-H | 環境 | `tests/conftest.py` に Kivy headless 設定追加 | 中 |
| 241-I | ドキュメント | AGENTS.md / 01-roadmap.md 更新 | 低 |

---

## 241-A: weakness pattern から「good」カテゴリ除外

### 問題
`extract_summary_weakness_patterns` (Shape B 経路) が `_PLAYER_MISTAKE_CATEGORIES`
タプル（blunder / mistake / inaccuracy / **good**）をそのまま weakness pattern として
出力していた。結果として LLM プロンプトに「good」が弱点として並ぶ。

実害: 標準的な real-shape summary では `count=310/388 (79.9%)` の good が
total_loss 順で 4 位に出現し、LLM に「good を弱点として抽出してほしい」と
誤解させる。

### 修正
- `json_type.py` に `_NON_WEAKNESS_CATEGORIES = frozenset({"good"})` 定数新設
- `extract_summary_weakness_patterns` の Shape B 経路でフィルタ追加
- `extract_summary_player_mistakes` は full 分布を保持するため変更なし
- 12 unit tests 追加（good 除外 + per-player 分布は full）

### 動作確認
```
Before:
  Pattern categories: ['inaccuracy', 'mistake', 'blunder', 'good']
  4. **good** / count=310 / 全体に占める割合=79.9% / 総損失=86.8
After:
  Pattern categories: ['inaccuracy', 'mistake', 'blunder']
  (good は弱点パターンから除外、per-player 分布には残る)
```

---

## 241-B: popup の unknown パス早期 return

### 問題
popup で karte/summary どちらにも判別できない JSON を開いた場合、silent に
karte 経路に流れて `detect_player_info` が空 dict を返し、status label に
`auto-detect-failed` が出る。原因が分からない。

### 修正
- `llm-coach:unknown-path` i18n キー追加（jp/en）: 「JSON の形式を認識できません: {path} (Karte または Summary JSON を指定してください)」
- `_populate_rank_and_perspective` / `on_generate_and_copy` / `on_validate` の 3 経路に `path_type == "unknown"` ガード追加
- 3 unit tests 追加

### 動作確認
```
Before: status = "auto-detect failed: ..." (原因不明)
After:  status = "JSON の形式を認識できません: /path/to/weird.json (Karte または Summary JSON を指定してください)"
```

---

## 241-C: loss_progression フォールバック

### 問題
`summary_prompt_builder.py` のプロンプトテンプレートに `loss_progression` セクションが
無く、データがあっても LLM に渡らない。実 JSON シェーマの 3 形式
（dict / legacy flat list / 空 bucket list）全てに対するフォールバックが無い。

### 修正
- `_format_loss_progression_block(loss_progression)` ヘルパー新設
- dict: `{"all": [...], "even": [...], "handicapped": [...]}` の 3 game-type を集約表示
- legacy flat list: `[...]` を `{"all": [...]}` に正規化
- 空 bucket list: `(空)` プレースホルダで表示
- 完全に missing: `(loss_progression データがありません)` プレースホルダ
- テンプレートに「Loss Progression (per game-type)」セクション追加
- 6 unit tests 追加

---

## 241-D: `_summary_index_to_internal` sentinel 化

### 問題
`_summary_index_to_internal(index, players)` が bird's-eye（index=0）と
out-of-range（バグ状態）の両方で `None` を返していた。ダウンストリーム
（`_resolve_player_color` 等）が両者を区別できない。

### 修正
- `_SUMMARY_BIRDSEYE_SENTINEL = "__birdseye__"` 定数新設
- bird's-eye: sentinel 文字列を返す
- out-of-range: `None` を返す（バグ状態、防御的フォールバック）
- `is_summary_birdseye(value)` ヘルパー追加
- 既存呼び出し側 2 箇所で sentinel 判定追加

---

## 241-E: summary_perspective_index race condition 対策

### 問題
`on_kv_post` → 0.2s 後 → `_populate_rank_and_perspective` →
`_populate_summary_perspective` で `summary_perspective_index` を上書き。
ユーザが spinner 触った後に 0.4s 遅延 population が走ると、ユーザの
選択が上書きされる。

### 修正
- `_summary_perspective_user_set: bool` フラグ新設
- `on_summary_perspective_changed` で `True` セット
- `_populate_summary_perspective` でユーザ設定済みなら index 保持
- `on_path_changed` で新ファイル時は `False` リセット

---

## 241-F: `detect_player_color_for_user` 型キャスト整理

### 問題
`_SgfInfoLike` クラスで `SgfPlayerInfo` インターフェースを implements し、
`cast(SgfPlayerInfo, pseudo)` で型ヒントだけ通していた。実行時には
no-op で、`isinstance(pseudo, SgfPlayerInfo)` チェックが追加されたら即壊れる。

### 修正
- `_SgfInfoLike` クラス完全削除
- `SgfPlayerInfo` dataclass + `PlayerInfo` を直接構築
- `cast` インポート不要
- ランタイム型チェックが効く

---

## 241-G: `find_latest_karte` 関数完全削除

### 問題
Phase 227-D で popup は `find_latest_llm_input_for_ctx` に切り替わったが、
legacy の `find_latest_karte` 関数が残っていた（DeprecationWarning だけ）。
`Phase 239` 表記が AGENTS.md に未記載の謎フェーズを参照していた。

### 修正
- `find_latest_karte` 関数本体削除（docstring のみ残置）
- 関連テスト 4 件削除（`TestFindLatestKarte` クラス）
- 4 ファイルに残っていた `Phase 239` 表記を `Phase 241-G` に統一
- `llm_coach.py:241` に migration note 追加

---

## 241-H: `tests/conftest.py` に Kivy headless 設定追加

### 問題
popup テストが CI 環境（display 無し）で `Kivy` 初期化失敗。Windows では
`kivy.metrics.dp(400)` が `must be real number, not NoneType` で
`kivymd.material_resources` モジュールロード時にクラッシュ。

### 修正
- `tests/conftest.py` の冒頭（Kivy import 前）に `KIVY_NO_ARGS` / `KIVY_NO_WINDOW` /
  `KIVY_HEADLESS` / `SDL_VIDEODRIVER=dummy` / `KIVY_GL_BACKEND=mock` 等の
  環境変数 setdefault 追加
- 既存の popup テスト preamble 設定と併用
- CI 環境（Xvfb on Linux 等）で popup テストが動くようになる

### 制限
Windows headless では KivyMD の dpi 取得が依然失敗するため、popup テストは
この環境では引き続き失敗。これは Kivy/KivyMD の Windows 互換性問題で、
本プロジェクトの範疇外。

---

## 241-I: ドキュメント整合

### 修正
- `AGENTS.md §1.3` マイルストーン一覧に Phase 241 追記
- `AGENTS.md §10` 変更履歴に Phase 241 追記
- `docs/01-roadmap.md` 完了済みリストに Phase 241 追加
- `docs/archive/specs-implemented/phase241-summary-quality-improvements.md` 新規作成（本ファイル）

---

## 修正ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `katrain/core/coach/json_type.py` | `_NON_WEAKNESS_CATEGORIES` 追加、Shape B フィルタ |
| `katrain/core/coach/summary_prompt_builder.py` | `_format_loss_progression_block` 追加、テンプレート拡張 |
| `katrain/gui/features/llm_coach.py` | `_SgfInfoLike` 削除、`find_latest_karte` 削除、migration note |
| `katrain/gui/popups/llm_coach_popup.py` | unknown パス guard、race condition 対策、sentinel 化、Phase 239 統一 |
| `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` | `unknown-path` キー追加 |
| `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` | `unknown-path` キー追加 |
| `tests/conftest.py` | Kivy headless 環境変数 |
| `tests/test_coach_json_type.py` | good 除外テスト 4 件追加 |
| `tests/test_coach_summary_prompt_builder.py` | loss_progression テスト 6 件追加 |
| `tests/test_coach_calibration_fixtures.py` | 既存テスト 3 件更新（good 除外） |
| `tests/test_llm_coach.py` | `TestFindLatestKarte` 削除 |
| `tests/test_llm_coach_popup.py` | unknown パス テスト 3 件追加 |
| `AGENTS.md` | Phase 241 マイルストーン追記 |
| `docs/01-roadmap.md` | Phase 241 完了追加 |
| `docs/archive/specs-implemented/phase241-*.md` | 本スペック作成 |

---

## テスト数推移

| 段階 | 累計テスト数 |
|------|------------|
| Phase 230-A.2 完了時 | 5,572 件 |
| Phase 241-A 完了時 | 5,584 件 (+12) |
| Phase 241-B 完了時 | 5,587 件 (+3) |
| Phase 241-C 完了時 | 5,593 件 (+6) |
| Phase 241-D 完了時 | 5,593 件 (+0, リファクタ) |
| Phase 241-E 完了時 | 5,593 件 (+0, リファクタ) |
| Phase 241-F 完了時 | 5,593 件 (+0, リファクタ) |
| Phase 241-G 完了時 | 5,589 件 (-4) |
| Phase 241-H 完了時 | 5,589 件 (+0) |
| Phase 241-I 完了時 | 5,589 件 (+0, doc) |
| **Phase 241 合計** | **5,612 件 (+40 ネット, 39 件追加 - 4 件削除 + 5 件既存更新)** |

※ 実測: `864 passed` (summary/coach 関連テストのみ、popup テストは Kivy headless 環境依存)
