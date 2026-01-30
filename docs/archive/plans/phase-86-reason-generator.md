# Phase 86: Reason Generator（限定実装）

## 概要

MistakeSignature（phase/area/tag）から自然言語の「理由文」を生成する限定実装。
単発タグと主要な組み合わせのみ自然文を生成し、それ以外はタグ表示にフォールバック。

## 修正レベル

**Lv3**: 複数ファイル（3-4ファイル）、新規モジュール追加 + 既存セクション統合

## ファイル構成

### 新規作成

| ファイル | 内容 | 行数目安 |
|----------|------|----------|
| `katrain/core/analysis/reason_generator.py` | コアモジュール（テンプレート + 生成関数） | ~200行 |
| `tests/test_reason_generator.py` | ユニットテスト | ~140行 |

### 変更

| ファイル | 変更内容 | 行数目安 |
|----------|----------|----------|
| `katrain/core/analysis/__init__.py` | エクスポート追加 | +3行 |
| `katrain/core/reports/karte/sections/important_moves.py` | Critical 3にReason行追加 | +15行 |
| `katrain/gui/features/summary_formatter.py` | Recurring PatternsにReason行追加 | +12行 |

## 言語コード仕様（確定版）

### 方針
- **シグネチャ**: `lang: Optional[str] = None`（デフォルト None）
- **None の扱い**: reason_generator 内部で `"jp"` に変換（日本語デフォルト）
- **空文字の扱い**: `"en"` に変換
- **その他**: `normalize_lang_code()` に委譲（例外時は `"en"`）
- **防御的クランプ**: 正規化後の値が `{"jp", "en"}` 以外なら `"en"` に強制

### 実装
```python
from katrain.common.locale_utils import normalize_lang_code

_VALID_LANGS: frozenset[str] = frozenset({"jp", "en"})

def _normalize_lang(lang: Optional[str]) -> str:
    """言語コードを正規化。reason_generator 専用。

    Args:
        lang: 入力言語コード（None 許容）

    Returns:
        "jp" or "en"

    Behavior:
        - None → "jp"（日本語デフォルト）
        - "" or whitespace-only → "en"
        - Otherwise → normalize_lang_code() に委譲
        - normalize_lang_code() が例外を投げた場合 → "en"
        - 結果が {"jp","en"} 以外 → "en"（防御的クランプ）
    """
    if lang is None:
        return "jp"
    if not lang.strip():
        return "en"
    try:
        normalized = normalize_lang_code(lang)
    except Exception:
        return "en"
    if normalized not in _VALID_LANGS:
        return "en"
    return normalized
```

### 言語コード変換表

| 入力 | 出力 | 理由 |
|------|------|------|
| `None` | `"jp"` | 日本語アプリデフォルト |
| `""` | `"en"` | 空→英語フォールバック |
| `"  "` | `"en"` | 空白のみ→英語フォールバック |
| `"jp"` | `"jp"` | 正規形 |
| `"ja"` | `"jp"` | ISO→内部変換 |
| `"ja_JP"` | `"jp"` | 地域バリアント |
| `"ja-JP"` | `"jp"` | 地域バリアント |
| `"en"` | `"en"` | 正規形 |
| `"en_US"` | `"en"` | 地域バリアント |
| `"fr"` | `"en"` | 未知→英語フォールバック |
| (例外発生) | `"en"` | 例外→英語フォールバック |

## データ構造

### ReasonTemplate（frozen dataclass）

```python
@dataclass(frozen=True)
class ReasonTemplate:
    jp: str  # 日本語テンプレート
    en: str  # 英語テンプレート

    def get(self, lang: str) -> str:
        """正規化済み言語コードでテンプレート取得。"""
        return self.jp if lang == "jp" else self.en
```

### SUPPORTED_TAGS（Phase 86 対象タグ）

```python
SUPPORTED_TAGS: frozenset[str] = frozenset({
    "life_death_error",
    "overplay",
    "direction_error",
    "capture_race_loss",
    "connection_miss",
    "reading_failure",
    "shape_mistake",
    "slow_move",
    "missed_tesuji",
    "endgame_slip",
    "territorial_loss",
    "uncertain",
})
```

### PHASE_VOCABULARY / AREA_VOCABULARY

```python
# MistakeSignature.phase の有効値
PHASE_VOCABULARY: frozenset[str] = frozenset({"opening", "middle", "endgame"})

# MistakeSignature.area / BoardArea enum の .value
AREA_VOCABULARY: frozenset[str] = frozenset({"corner", "edge", "center"})
```

### SINGLE_TAG_REASONS（12エントリ、JP+EN）

| MeaningTagId | 日本語 (jp) | 英語 (en) |
|--------------|-------------|-----------|
| life_death_error | 石の生死に関わる読み間違いです。 | A reading mistake involving life and death. |
| overplay | 無理な手で損失が発生しました。 | An overplay that led to a loss. |
| direction_error | 攻める方向を間違えました。 | Attacked in the wrong direction. |
| capture_race_loss | 攻め合いで負けました。 | Lost a capturing race. |
| connection_miss | 石の連絡を見逃しました。 | Missed a connection opportunity. |
| reading_failure | 読み抜けがありました。 | A reading oversight occurred. |
| shape_mistake | 石の形が悪くなりました。 | Created bad shape. |
| slow_move | 緩い手で先手を失いました。 | A slow move that lost initiative. |
| missed_tesuji | 手筋を見逃しました。 | Missed a tesuji. |
| endgame_slip | ヨセで計算ミスがありました。 | A calculation mistake in endgame. |
| territorial_loss | 地を損しました。 | Lost territory. |
| uncertain | 分類困難な局面です。 | Difficult to classify. |

### COMBINATION_REASONS（8エントリ、JP+EN）

| phase | area | tag | 日本語 (jp) | 英語 (en) |
|-------|------|-----|-------------|-----------|
| opening | corner | direction_error | 隅での方向判断ミス。布石の基本を復習しましょう。 | Direction misjudgment in the corner. Review opening fundamentals. |
| opening | edge | direction_error | 辺での展開方向を見誤りました。 | Misjudged the direction of development on the side. |
| middle | corner | life_death_error | 隅の死活で読み間違いが発生しました。 | A reading mistake in corner life and death. |
| middle | edge | connection_miss | 辺での石の連絡を見逃しました。 | Missed a connection opportunity on the side. |
| middle | center | capture_race_loss | 中央の攻め合いで負けました。 | Lost a capturing race in the center. |
| endgame | corner | endgame_slip | 隅のヨセで計算ミスがありました。 | A calculation mistake in corner endgame. |
| endgame | edge | territorial_loss | 辺のヨセで地を損しました。 | Lost territory in side endgame. |
| middle | * | overplay | 中盤での無理な攻めが裏目に出ました。 | An overplay in the midgame backfired. |

## コア関数

### generate_reason() → Optional[str]

```python
def generate_reason(
    meaning_tag_id: Optional[str],
    phase: Optional[str] = None,
    area: Optional[str] = None,
    lang: Optional[str] = None,
) -> Optional[str]:
    """自然言語の理由文を生成。

    Args:
        meaning_tag_id: MeaningTagId.value (e.g., "overplay") or None
        phase: "opening" / "middle" / "endgame" or None
        area: "corner" / "edge" / "center" or None
        lang: 言語コード or None（None → "jp"）

    Returns:
        理由文字列、またはマッチしない場合 None
    """
```

### マッチング順序（確定版）

```
1. (phase, area, tag) 完全一致
2. (phase, "*", tag)  area ワイルドカード
3. ("*", area, tag)   phase ワイルドカード
4. tag のみ           SINGLE_TAG_REASONS
5. None               フォールバック
```

### ワイルドカードと None の扱い（確定版）

**ワイルドカード `"*"` の意味**:
- キー `(phase, "*", tag)` は「area スロットを検査しない」を意味する
- **入力の area 値が何であっても（None を含む）マッチ対象となる**
- 同様に `("*", area, tag)` は「phase スロットを検査しない」を意味する

**マッチングアルゴリズム**:
```python
def _find_combo_match(phase, area, tag, lang):
    # Step 1: 完全一致（phase と area が両方 non-None の場合のみ）
    if phase is not None and area is not None:
        key = (phase, area, tag)
        if key in COMBINATION_REASONS:
            return COMBINATION_REASONS[key].get(lang)

    # Step 2: area ワイルドカード（phase が non-None の場合）
    # area の値は検査しない（None でも OK）
    if phase is not None:
        key = (phase, "*", tag)
        if key in COMBINATION_REASONS:
            return COMBINATION_REASONS[key].get(lang)

    # Step 3: phase ワイルドカード（area が non-None の場合のみ）
    if area is not None:
        key = ("*", area, tag)
        if key in COMBINATION_REASONS:
            return COMBINATION_REASONS[key].get(lang)

    return None  # コンボなし → 単発タグへ
```

**area=None の場合の動作**:
- 完全一致 `(phase, area, tag)` → 不可（area が None なので）
- `(phase, "*", tag)` → **有効**（`"*"` は area を検査しない）
- `("*", area, tag)` → 不可（area が None なので）
- 単発タグ → 有効

**phase=None の場合の動作**:
- 完全一致 → 不可
- `(phase, "*", tag)` → 不可（phase が None なので）
- `("*", area, tag)` → 有効（area が non-None なら）
- 単発タグ → 有効

### generate_reason_safe() → str

```python
def generate_reason_safe(
    meaning_tag_id: Optional[str],
    phase: Optional[str] = None,
    area: Optional[str] = None,
    lang: Optional[str] = None,
    fallback_label: Optional[str] = None,
) -> str:
    """例外を投げない安全版。

    Returns:
        理由文字列。マッチしない場合は fallback_label or ""
    """
```

## フォールバック動作の明確化

### 統合箇所での動作

Critical 3 / Recurring Patterns の統合では:
1. `generate_reason_safe()` を `fallback_label=None` で呼び出す
2. 戻り値が空文字の場合、**Reason 行を出力しない**
3. 既存の **Type** 行（meaning_tag_label）が表示されるため、ユーザーはミスの種類を把握可能

### 未知タグの場合
- `generate_reason()` → `None` を返す
- `generate_reason_safe()` → `""` を返す（fallback_label=None の場合）
- **Reason 行は出力されない**
- 既存の **Type** 行で `meaning_tag_label` が表示される

## 統合箇所

### 属性名確認（✅ 検証済み）

`CriticalMove` クラス（critical_moves.py:106-127）:
- `cm.gtp_coord: str` ✅
- `cm.meaning_tag_id: str` ✅
- `cm.game_phase: str` ✅

`MistakeSignature` クラス（pattern_miner.py:60-72）:
- `sig.phase: str` → `{"opening", "middle", "endgame"}` ✅
- `sig.area: str` → `{"corner", "edge", "center"}` ✅
- `sig.primary_tag: str` → MeaningTagId.value ✅

### インポート確認（✅ 検証済み）

`get_area_from_gtp` は `stats/__init__.py` からeagerエクスポート（軽量、循環なし）✅

### get_area_from_gtp() 戻り値（✅ 検証済み）

`BoardArea` enum（board_context.py:20-25）:
- `"corner"` ✅
- `"edge"` ✅
- `"center"` ✅
- `None`（pass/resign/invalid）✅

### 1. Critical 3セクション（important_moves.py:322-349）

**実装:**
```python
# ファイル先頭でインポート追加
from katrain.core.batch.stats import get_area_from_gtp
from katrain.core.analysis.reason_generator import generate_reason_safe

# critical_3_section_for() 内、line 325 の後に追加
try:
    area = get_area_from_gtp(cm.gtp_coord, ctx.game.board_size)
except Exception:
    area = None

reason = generate_reason_safe(
    cm.meaning_tag_id,
    phase=cm.game_phase,
    area=area,
    lang=ctx.lang,
)
if reason:
    lines.append(f"- **Reason**: {reason}")
```

### 2. Recurring Patternsセクション（summary_formatter.py:381-439）

**実装:**
```python
# ファイル先頭でインポート追加
from katrain.core.analysis.reason_generator import generate_reason_safe

# _append_recurring_patterns() 内、line 429 の後に追加
reason = generate_reason_safe(
    sig.primary_tag,
    phase=sig.phase,
    area=sig.area,
    lang=i18n.current_lang,
)
if reason:
    lines.append(f"   - {reason}")
```

## ゴールデンテスト仕様（確定版）

### 言語固定方針

ゴールデンテストでは**決定論的な出力**を保証するため、言語を固定する。

- **Critical 3 (test_golden_karte.py)**: `ctx.lang = "jp"` を fixture で強制
- **Recurring Patterns (test_golden_summary.py)**: `i18n.current_lang = "jp"` を fixture で強制
- **期待値**: 全て**日本語**で記述

### 実装方法

```python
@pytest.fixture
def force_jp_lang(monkeypatch):
    """ゴールデンテスト用に言語を jp に固定。"""
    from katrain.core.lang import i18n
    monkeypatch.setattr(i18n, "current_lang", "jp")
```

### ゴールデン期待値の例

**Critical 3（日本語）**:
```markdown
### 1. Move #45 (B) D10
- **Loss**: 3.2目
- **Type**: 死活ミス
- **Reason**: 石の生死に関わる読み間違いです。
- **Phase**: middle
...
```

**Recurring Patterns（日本語）**:
```markdown
1. **序盤 / 隅 / 悪手 (direction_error)**: 3回、総損失8.5目
   - game1.sgf #15(B), game2.sgf #20(W)
   - 隅での方向判断ミス。布石の基本を復習しましょう。
```

## テスト戦略

### ユニットテスト一覧（test_reason_generator.py）

| テスト名 | 対象 | 内容 |
|----------|------|------|
| `test_supported_tags_coverage` | SINGLE_TAG_REASONS | SUPPORTED_TAGS の全タグにテンプレートがある |
| `test_single_tag_reasons_keys_match_supported` | SINGLE_TAG_REASONS | キーが SUPPORTED_TAGS と完全一致 |
| `test_combination_reasons_have_both_languages` | COMBINATION_REASONS | 全エントリが jp/en 両方持つ |
| `test_area_vocabulary_matches_board_area` | AREA_VOCABULARY | BoardArea enum の .value と一致 |
| `test_phase_vocabulary_matches_signature` | PHASE_VOCABULARY | MistakeSignature.phase の有効値と一致 |
| `test_combination_priority` | generate_reason | 組み合わせマッチが単発より優先される |
| `test_unknown_tag_returns_none` | generate_reason | 未知タグで None を返す |
| `test_lang_none_defaults_to_jp` | generate_reason | lang=None → 日本語出力 |
| `test_lang_empty_defaults_to_en` | generate_reason | lang="" → 英語出力 |
| `test_lang_whitespace_defaults_to_en` | generate_reason | lang="  " → 英語出力 |
| `test_lang_jp_variants` | generate_reason | jp/ja/ja_JP/ja-JP → 日本語出力 |
| `test_lang_en_variants` | generate_reason | en/en_US → 英語出力 |
| `test_lang_unknown_defaults_to_en` | generate_reason | 未知言語コード（"fr"等）→ 英語出力 |
| `test_safe_never_raises` | generate_reason_safe | 全入力 None でも例外なし |
| `test_safe_returns_string` | generate_reason_safe | 常に str を返す |
| `test_safe_unknown_tag_returns_empty` | generate_reason_safe | 未知タグで "" を返す |
| `test_safe_fallback_label` | generate_reason_safe | 未知タグで fallback_label を返す |
| `test_wildcard_area_match` | generate_reason | (phase, "*", tag) がマッチする（area="center"） |
| `test_area_none_uses_wildcard` | generate_reason | area=None でも (phase, "*", tag) マッチ有効 |
| `test_phase_none_skips_phase_wildcard` | generate_reason | phase=None では (phase, "*", tag) 不可 |

**計20テスト**

### ゴールデンテスト更新

- `tests/test_golden_karte.py` - 言語固定（jp）、Reason 行あり
- `tests/test_golden_summary.py` - 言語固定（jp）、理由行あり

## 実装順序

### Step 1: コアモジュール作成
1. `reason_generator.py` を作成
   - `_normalize_lang()` ヘルパー
   - SUPPORTED_TAGS, PHASE_VOCABULARY, AREA_VOCABULARY 定義
   - ReasonTemplate dataclass
   - SINGLE_TAG_REASONS（12エントリ）
   - COMBINATION_REASONS（8エントリ、JP+EN）
   - generate_reason(), generate_reason_safe()
2. `analysis/__init__.py` にエクスポート追加
3. `test_reason_generator.py` 作成・実行

### Step 2: Critical 3 統合
1. `important_moves.py` に統合コード追加（try/except 付き）
2. ゴールデンテスト fixture + 期待値更新

### Step 3: Recurring Patterns 統合
1. `summary_formatter.py` に統合コード追加
2. ゴールデンテスト fixture + 期待値更新

### Step 4: 全体テスト
1. `uv run pytest tests` 全テスト実行
2. `python -m katrain` 起動確認

## 検証方法

1. **ユニットテスト**: `uv run pytest tests/test_reason_generator.py -v`
2. **ゴールデンテスト**: `uv run pytest tests/test_golden_karte.py tests/test_golden_summary.py -v`
3. **手動確認**: KaTrain で SGF を読み込み、Export Karte → Critical 3 に Reason 行があることを確認
4. **バッチ確認**: 複数 SGF で Batch Analysis → Summary Report の Recurring Patterns に理由文があることを確認

## リスク軽減

| リスク | 対策 |
|--------|------|
| データ欠損でクラッシュ | generate_reason_safe() で全入力を None 許容 |
| 未知のタグ値 | generate_reason() は None、safe() は "" 返却 |
| area 計算失敗 | get_area_from_gtp() を try/except でラップ |
| lang=None | "jp" にフォールバック |
| lang="" | "en" にフォールバック |
| 未知言語コード | normalize_lang_code() → "en" + 防御的クランプ |
| normalize_lang_code 例外 | try/except で "en" にフォールバック |
| 言語不整合 | ゴールデンテストは言語固定（jp） |

## Acceptance Criteria（最終版）

### 言語出力
- [ ] `lang=None` → 日本語出力
- [ ] `lang=""` → 英語出力
- [ ] `lang="  "` → 英語出力
- [ ] `lang` が `"jp"`, `"ja"`, `"ja_JP"`, `"ja-JP"` → 日本語出力
- [ ] `lang` が `"en"`, `"en_US"` → 英語出力
- [ ] `lang` が未知コード（`"fr"` 等）→ 英語出力

### クラッシュ耐性
- [ ] `meaning_tag_id=None` でクラッシュしない
- [ ] `phase=None` でクラッシュしない
- [ ] `area=None` でクラッシュしない
- [ ] `lang=None` でクラッシュしない
- [ ] 未知の `meaning_tag_id` 値でクラッシュしない
- [ ] `get_area_from_gtp()` 失敗時もクラッシュしない

### マッチング動作
- [ ] `area=None` でも `(phase, "*", tag)` ワイルドカードにマッチする
- [ ] `phase=None` では `(phase, "*", tag)` にマッチしない
- [ ] `generate_reason()` は未知タグで `None` を返す
- [ ] `generate_reason_safe()` は未知タグで `""` を返す（fallback_label=None）
- [ ] 未知タグの場合、Reason 行は出力されない
- [ ] COMBINATION_REASONS は jp/en 両言語で出力可能

### テスト
- [ ] `tests/test_reason_generator.py` 全20テストパス
- [ ] `tests/test_golden_karte.py` パス（言語固定 jp）
- [ ] `tests/test_golden_summary.py` パス（言語固定 jp）
- [ ] `uv run pytest tests` 全件パス
- [ ] `python -m katrain` 正常起動

## 見積もり

- 新規コード: ~320行
- 変更コード: ~35行
- テストコード: ~150行
- **合計**: ~505行
