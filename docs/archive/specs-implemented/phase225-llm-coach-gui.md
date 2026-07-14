# Phase 225.6: LLM Coach 視点自動判定 + SGF 棋力自動取得

> 起票日: 2026-07-17
> 完了: 2026-07-17
> ステータス: ✅ 完了

## 1. 概要

Phase 225 で導入した LLM Coach GUI に **2 つの改善** を追加:

1. **視点自動判定**: mykatrain settings の `default_user_name` から Karte JSON / SGF の PB/PW を照合し、ユーザーが黒番か白番かを自動判定
2. **SGF 棋力自動取得**: 野狐 / KGS 等の SGF が持つ BR/WR プロパティを Karte JSON meta に格納し、LLM Coach Popup で棋力入力を **自動充填**

ユーザーが野狐から DL した SGF を Karte Export → LLM Coach で使う際、毎回手入力していた棋力・視点を **自動判定** する。

## 2. 動機と背景

### ユーザー報告

> **視点が黒視点が選択されているみたいですができればmykatrainの出力設定のデフォルトユーザーを読み取るか選択できる方が望ましい**
> 野狐からダウンロードしたSGFファイルですが棋力の情報も入っているのでカルテやサマリーに反映したりして棋力入力をしなくていいように改善してほしい

### 問題

| 現状 | 問題 |
|------|------|
| `PromptConfig` に `player_color` フィールド無し | LLM にどの視点か伝わらず、結果が黒/白両方を含む曖昧な解説になる |
| `MetaExtractor.extract_game_meta` が BR/WR を読まない | SGF が持つ棋力情報が Karte JSON に残らない |
| LLM Coach Popup に棋力手動入力必須 | 毎回「5k」「4d」と入力する手間、SGF と Karte の二重管理 |
| `default_user_name` 連携無し | ユーザーがどちらの視点か毎回手動指定 |

### 副次的バグ修正

`validate_llm_output` で症状 ID が player_color と一致しない場合に HIGH 警告が出ていた（例: `life_death_error`, `reading_failure`, `overplay` は Karte JSON に存在しない）。

これは Phase 225.7 で対応予定（validator 拡張）。本 Phase では PromptConfig に player_color を追加して LLM に「この側の弱点のみ参照」と指示することで、将来の validator 拡張の前提を作る。

## 3. 実装ファイル

### 新規（2 ファイル）

| ファイル | 行数 | 役割 |
|---------|------|------|
| `katrain/core/coach/sgf_player_info.py` | ~180 | `parse_sgf_player_info`, `extract_player_info_from_sgf`, `extract_player_info_for_user` |
| `tests/test_sgf_player_info.py` | ~190 | 17 件 SGF パース / fuzzy match テスト |

### 変更（10 ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `katrain/core/reports/extractors.py` | MetaExtractor が `ranks: {black, white}` を返すよう拡張 |
| `katrain/core/reports/karte/json_export.py` | meta dict に `player_info: {black: {name, rank}, white: {name, rank}}` 追加 |
| `katrain/core/coach/prompt_builder.py` | `PromptConfig.player_color` 追加、SystemInstruction に PlayerColor 行 |
| `katrain/core/coach/cli.py` | `build_prompt()` に `player_color` 引数 |
| `katrain/gui/features/llm_coach.py` | `detect_player_info`, `detect_player_color_for_user` ヘルパー |
| `katrain/gui/popups/llm_coach_popup.py` | 視点スピナー + 棋力自動表示ロジック |
| `katrain/gui/kv/llm_coach_popup.kv` | `perspective_select` Spinner + auto-hint Label |
| `katrain/i18n/locales/{jp,en}/...katrain.po` | 7 新規キー追加 |
| `tests/fixtures/golden/karte_sgf_*.golden` | player_info フィールド追加で更新 |
| `tests/test_karte_player_info_meta.py`, `tests/test_prompt_builder_player_color.py`, `tests/test_llm_coach_popup.py`, `tests/test_llm_coach_popup_layout.py` | 32 件テスト追加 |

**合計: 12 ファイル・約 1,100 行追加**

## 4. UI 設計

### 4.1 LLM Coach Popup（Phase 225.6 改善版）

```
┌──────────────────────────────────────────────────────────┐
│ LLM コーチ — KataGo 出力を LLM に翻訳         ✕         │
├──────────────────────────────────────────────────────────┤
│ 【使い方】                                              │
│ 1. ... (省略)                                            │
├──────────────────────────────────────────────────────────┤
│ Karte JSON: [/path/to/karte_xxx.json ] [参照]          │
│                                                          │
│ 棋力: [4d]                              ← 自動充填       │
│       (SGF から自動取得: 4d)                            │
│                                                          │
│ 視点: [自動 (default user) ▼]          ← 新規スピナー   │
│       (SGF から自動判定: 黒 (B))                        │
├──────────────────────────────────────────────────────────┤
│ [プロンプト生成 & コピー]  [応答をクリア]              │
│   ... (省略)                                              │
└──────────────────────────────────────────────────────────┘
```

### 4.2 スピナー動作

| 選択 | 動作 |
|------|------|
| **自動 (default user)** | mykatrain settings の `default_user_name` で Karte/SGF の名前マッチ判定 |
| **黒 (B)** | 強制的に黒視点で LLM に渡す |
| **白 (W)** | 強制的に白視点で LLM に渡す |

自動判定成功時: `(SGF から自動判定: 黒 (B))` のヒント表示
判定失敗時: `(判定不可 — 手動で黒/白を選択してください)` のヒント表示

## 5. Karte JSON meta 拡張

**Phase 225.6 の Karte JSON 出力例**:
```json
{
  "schema_version": "3.4",
  "meta": {
    "schema_version": "3.4",
    "schema_hash": "...",
    "game_id": "g1",
    "generated_at": "2026-07-17T...",
    "source_filename": "D:/.../karte_xxx.sgf",
    "date": "2026-07-14",
    "players": {"black": "醉舞", "white": "仙得"},
    "player_info": {                       // ← 新規追加
      "black": {"name": "醉舞", "rank": "4d"},
      "white": {"name": "仙得", "rank": "4d"}
    },
    "result": "B+R",
    ...
  },
  ...
}
```

**後方互換**: 新フィールド追加のみ。既存テストは `--update-goldens` で更新。

## 6. PromptConfig 拡張

```python
@dataclass(frozen=True)
class PromptConfig:
    voice: ToneVoice
    mode: CoachMode
    detected_symptom_ids: tuple[SymptomId, ...]
    llm_required_symptom_ids: tuple[SymptomId, ...] = ()
    max_lexicon_entries: int = 7
    include_expanded: bool = True
    schema_version: str = "3.4"
    player_rank_str: str | None = None
    average_points_lost: float | None = None
    # Phase 225.6:
    player_color: str | None = None      # "B" / "W" / None
```

`build_translation_prompt` で SystemInstruction に追加:
```
<!--
[SYSTEM INSTRUCTION FOR LLM]
...
PlayerColor: black (or white / unknown)

[STRICT RULES — DO NOT VIOLATE]
3. Every symptom_id you mention MUST exist in the Karte JSON's
   ``weaknesses[<player_color>]`` or ``important_moves[*].meaning_tag_id``
   field. When ``PlayerColor`` is set, focus your review on that side's
   weaknesses only.
...
-->
```

## 7. SGF パーサー実装詳細

`sgf_player_info.py` は **Kivy 非依存の正規表現パーサー**：

```python
@dataclass(frozen=True)
class PlayerInfo:
    name: str | None = None
    rank: str | None = None

@dataclass(frozen=True)
class SgfPlayerInfo:
    black: PlayerInfo
    white: PlayerInfo
    sgf_path: str | None = None

def parse_sgf_player_info(sgf_text, *, sgf_path=None) -> SgfPlayerInfo:
    """Parse raw SGF text and return black/white player info."""

def extract_player_info_for_user(sgf_info, username) -> tuple[str | None, str | None]:
    """Return (color, rank) for the side matching username.

    Fuzzy match: strips whitespace/punctuation/CJK brackets,
    case-insensitive. 'sentoku' matches 'sentoku870' and '醉舞'
    matches '醉舞(野狐)'.
    """
```

**CJK 文字対応**: `re.sub(r'[^0-9a-z぀-ヿ一-鿿]+', '', s)` で ASCII + かな + 漢字 を保持しつつ記号除去。

## 8. テスト結果

| 指標 | 値 |
|------|-----|
| 機能テスト | **5017 passed, 5 skipped**（4968 baseline + **49 件新規**） |
| アーキテクチャ | **44 passed** |
| **累計** | **5061 passed** |

### 内訳（49 件新規）

| テストファイル | 件数 |
|---------------|------|
| `tests/test_sgf_player_info.py` | 17 |
| `tests/test_karte_player_info_meta.py` | 7 |
| `tests/test_prompt_builder_player_color.py` | 4 |
| `tests/test_llm_coach.py` (+detect_player_info) | 6 |
| `tests/test_llm_coach_popup.py` (Phase 225.6) | 11 |
| `tests/test_llm_coach_popup_layout.py` (+spinner) | 4 |

## 9. 申し送り・Phase 225.7 以降

### Phase 225.7: validator 拡張（症状 ID ↔ player_color 整合性）

`validate_llm_output` の HIGH 警告「unknown_symptom_id」を player_color で降格:
- 症状 ID が `weaknesses[<player_color>]` に無くて他方の色にある場合、MEDIUM に降格
- ユーザー視点では LLM が間違えた可能性が高いが、誤検知ではなく **意図した言及** かもしれない

### Phase 226: Karte JSON schema v3.5 昇格

`weaknesses.<color>.<item>` に `player_color` キーを追加し、各 weakness がどちらの色由来かを明示。

### Phase 225.8+: Summary 対応

複数局まとめ (Summary) でも各対局の player_info を保持する拡張。

## 10. 動作確認手順

```bash
# 1. 野狐 SGF を KaTrain で開いて対局解析
python -m katrain

# 2. MyKatrain → カルテ出力（Phase 225.6 で BR/WR が Karte に自動反映）
# → 出力される karte_xxx.json を確認:
#    meta.player_info.black.rank = "4d" 等が入っている

# 3. MyKatrain → LLM コーチ（手動貼付）
# → 棋力フィールドに "4d" が自動入力
# → "(SGF から自動取得: 4d)" のヒント表示
# → 視点スピナーがデフォルト「自動」、ヒントで「黒 (B)」と表示
# → mykatrain settings の default_user_name が "醉舞" の場合

# 4. 「プロンプト生成 & コピー」→ ステータス: ✅
# → クリップボードの Markdown に以下が含まれる:
#    PlayerColor: black
#    Rule 3 で weaknesses[<player_color>] を参照

# 5. 視点スピナーを手動で「白 (W)」に変更
# → ヒント再検出で "(SGF から自動判定: 白 (W))" 表示 (もし該当ユーザーが白の場合)
# → 再ビルドで PlayerColor: white

# 6. テスト
UV_PROJECT_ENVIRONMENT=/tmp/katrain-venv uv run pytest tests/ -n auto
# → 5017 passed
```

## 11. 関連ドキュメント

- `docs/01-roadmap.md` Phase 203+ 章: Phase 225.6 追記
- `AGENTS.md §1.3`: Phase 225.6 完了マイルストーン
- `docs/archive/specs-planned/phase203-llm-translator.md`: 翻訳特化の元設計
- `katrain/core/coach/prompt_builder.py:50-77`: PromptConfig 拡張
- `katrain/gui/features/llm_coach.py`: detect_player_info / detect_player_color_for_user