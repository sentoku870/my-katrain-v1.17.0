# Leela Zero lz-analyze 出力フォーマット仕様

> 作成日: 2026-01-15
> 対象バージョン: Leela 0.110 (LizziYzy改良版)
> ステータス: 確定（Phase 14.0 サンプル収集完了）

---

## 1. 概要

`lz-analyze` コマンドは、Leela Zero の解析結果を GTP 拡張形式で出力する。
本ドキュメントは、Leela 0.110 での実際の出力を基に、パーサ実装に必要な仕様を定義する。

---

## 2. コマンド形式

```
lz-analyze <interval>
```

- `interval`: 出力間隔（centiseconds）。例: `100` = 1秒ごと
- 探索を停止するまで、定期的に `info` 行を出力し続ける

**停止方法**: 任意の GTP コマンド（例: `name`）を送信

---

## 3. 出力フォーマット

### 3.1 基本構造

```
info move <coord> visits <n> winrate <wr> order <ord> pv <moves...> [info move ...]
```

1行に複数の候補手が `info` で区切られて連結される。

### 3.2 フィールド定義

| フィールド | 型 | 説明 | 例 |
|-----------|-----|------|-----|
| `move` | string | GTP座標 (A-T, 1-19, I除く) | `C4`, `Q16`, `pass` |
| `visits` | int | 探索訪問数 | `7975` |
| `winrate` | int | 勝率 × 10000（0-10000） | `4912` = 49.12% |
| `order` | int | 候補順位（0から開始） | `0` = ベスト手 |
| `pv` | string[] | 読み筋（スペース区切り） | `C4 Q4 D17` |

### 3.3 winrate の単位（重要）

**Leela 0.110 では winrate は 0-10000 の整数で出力される**

- `winrate 4912` → 49.12%
- `winrate 10000` → 100%
- `winrate 0` → 0%

**パーサでの正規化**:
```python
# raw winrate (0-10000) → normalized (0.0-1.0)
winrate_normalized = raw_winrate / 10000.0
```

注意: 将来のビルドで 0-100 や 0.0-1.0 で出力される可能性があるため、
パーサは `normalize_winrate_from_raw()` で自動判定する。

---

## 4. サンプル出力

### 4.1 序盤（空盤）

```
info move C4 visits 7975 winrate 4912 order 0 pv C4 Q4 D17 Q16 O3 R6 J3 D15 C15 info move C16 visits 9086 winrate 4902 order 1 pv C16 Q16 D3 Q4 O17 R14 H17 D5 C7 C6 ...
```

### 4.2 中盤

```
info move R14 visits 59871 winrate 4997 order 0 pv R14 R5 Q6 O4 P9 R12 R9 S9 R8 S8 info move R13 visits 18346 winrate 4948 order 1 pv R13 R5 Q6 O4 P10 Q8 P8 P7 Q7 O7 ...
```

### 4.3 置碁（3子局、白番）

```
info move D16 visits 36661 winrate 3908 order 0 pv D16 C14 F17 B16 O17 C17 D17 info move D17 visits 29801 winrate 3793 order 1 pv D17 D15 D12 G16 E15 E14 ...
```

注: 置碁では白番の winrate が低い（<50%）のが正常。

---

## 5. パーサ実装の注意点

### 5.1 正規表現パターン

```python
CANDIDATE_PATTERN = re.compile(
    r'info\s+move\s+(\w+)\s+'
    r'visits\s+(\d+)\s+'
    r'winrate\s+(\d+)\s+'
    r'order\s+(\d+)\s+'
    r'pv\s+([\w\s]+?)(?=\s*info\s+move|\s*$)'
)
```

### 5.2 winrate 正規化ロジック

```python
def normalize_winrate_from_raw(raw: float) -> float:
    """
    rawの単位を判定して0-1に正規化。
    - raw > 100: 0-10000と判断して /10000
    - raw > 1.0: 0-100と判断して /100
    - raw <= 1.0: 0-1と判断してそのまま
    """
    if raw > 100:
        raw = raw / 10000.0
    elif raw > 1.0:
        raw = raw / 100.0
    return max(0.0, min(1.0, raw))
```

### 5.3 エラー処理

| 状況 | 対応 |
|------|------|
| `info` 行がない | 空の candidates を返す |
| winrate が欠損 | 該当候補をスキップ |
| visits が 0 または負 | 該当候補をスキップ |
| パース失敗 | parse_error をセット |

---

## 6. テストサンプル配置

```
tests/fixtures/leela_samples/
├── even_game_opening.txt   # 互先・序盤
├── even_game_midgame.txt   # 互先・中盤
├── handicap_3.txt          # 3子局
├── endgame.txt             # 終盤
└── error_cases.txt         # エラーケース
```

---

## 7. 確認済み情報

- **winrate 存在確認**: ✅ 全候補手に winrate フィールドあり
- **winrate 単位**: 0-10000（パーセント × 100）
- **prior フィールド**: なし（Leela 0.110 では出力されない）
- **score フィールド**: なし（Leela Zero は勝率のみ）

---

## 変更履歴

- 2026-01-15: v1.0 作成（Phase 14.0 完了）
