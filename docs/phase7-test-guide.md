# Phase 7 動作確認ガイド

> このガイドは Phase 7 で実装した機能が正しく動作するかを確認するための手順書です。

---

## 確認する機能

1. **Phase × Mistake クロス集計テーブル**（複数局サマリー）
2. **弱点仮説セクション**（複数局サマリー + 単局カルテ）
3. **Practice Priorities の精度向上**（クロス集計活用）

---

## テスト1: 複数局サマリーの生成

### 手順

1. KaTrain を起動
   ```powershell
   cd D:\github\katrain-1.17.0
   python -m katrain
   ```

2. メニューから「Analysis」→「Multi-game summary」を選択

3. KataGo解析済みの SGF ファイルを2局以上選択
   - テスト用に `tests/data/` のファイルを使用可能
   - または自分の対局ファイル（KTプロパティ付き）を使用

4. プレイヤー名を選択（自分の名前）

5. 「Generate Summary」をクリック

### 期待される出力

`reports/summary_互先_YYYYMMDD-HHMM.md` が生成され、以下のセクションが含まれる：

#### 1. Phase × Mistake Breakdown テーブル

```markdown
## Phase × Mistake Breakdown

| Phase | Good | Inaccuracy | Mistake | Blunder | Total Loss |
|-------|------|------------|---------|---------|------------|
| Opening | 45 | 5 (5.2) | 2 (4.8) | 1 (6.3) | 16.3 |
| Middle game | 120 | 25 (18.5) | 18 (38.2) | 8 (52.1) | 108.8 |
| Endgame | 30 | 3 (2.1) | 1 (3.8) | 0 | 5.9 |
```

**確認ポイント**:
- ✅ 3つの Phase（Opening / Middle game / Endgame）が表示される
- ✅ 各セルに「回数 (損失)」の形式で表示される（GOOD以外）
- ✅ Total Loss 列が正しく計算されている

#### 2. Weakness Hypothesis セクション

```markdown
## Weakness Hypothesis

Based on cross-tabulation analysis:

1. **Middle gameの大悪手** (8回、損失52.1目)
2. **Middle gameの悪手** (18回、損失38.2目)
3. **Openingの軽微なミス** (5回、損失5.2目)

**分析**:
- Middle gameの損失の47.9%が大悪手によるもの
- Middle gameの4.7%の手が大悪手と判定されている
```

**確認ポイント**:
- ✅ 上位3つの弱点が損失順に表示される
- ✅ 回数と損失が正しく表示される
- ✅ 分析セクションで割合（%）が計算されている

#### 3. Practice Priorities セクション

```markdown
## Practice Priorities

Based on the data above, consider focusing on:

- 1. **Middle gameの大悪手** (8回、損失52.1目)
- 2. **Middle gameの悪手** (18回、損失38.2目)
```

**確認ポイント**:
- ✅ 上位2つの弱点が簡潔に表示される
- ✅ Weakness Hypothesis の上位2つと一致する

---

## テスト2: 単局カルテの生成

### 手順

1. KaTrain で KataGo解析済みの対局を開く
   - または新規対局を開始して数手進める

2. 「Export Karte」ボタンをクリック
   - 右パネルの下部にあるボタン

3. 保存先を確認

### 期待される出力

`reports/karte_YYYYMMDD-HHMM.md` が生成され、以下のセクションが含まれる：

#### Weakness Hypothesis (Focus Player)

```markdown
## Weakness Hypothesis (Black)

1. **Middle gameの大悪手** (3回、損失18.5目)
2. **Openingの悪手** (2回、損失4.8目)
```

**確認ポイント**:
- ✅ Focus Player（自分の名前で設定したプレイヤー）の弱点が表示される
- ✅ 上位2つの弱点が表示される
- ✅ 手数が50手以上ある対局で Middle game / Endgame が表示される

---

## テスト3: UTF-8エンコーディングの確認

### 手順

1. 生成された `summary.md` または `karte.md` をテキストエディタで開く
   - VSCode, Notepad++, またはメモ帳で開く

2. 日本語が正しく表示されるか確認

### 期待される結果

- ✅ 「大悪手」「悪手」「軽微なミス」が正しく表示される
- ✅ 文字化けしていない
- ✅ ファイルのエンコーディングが UTF-8 である

---

## トラブルシューティング

### 問題1: Phase × Mistake Breakdown が表示されない

**原因**: SGF に KataGo 解析データ（KTプロパティ）が含まれていない

**対処法**:
1. KaTrain で対局を開く
2. 「Analyze Game」で全手を解析する
3. SGF を保存して再度試す

### 問題2: Weakness Hypothesis が「明確な弱点パターンは検出されませんでした」と表示される

**原因**: 損失が 0.5 目以下の手しかない（ほぼ完璧な対局）

**対処法**:
- これは正常な動作です
- 損失がある対局で再度試す

### 問題3: Freedom Distribution が全て UNKNOWN

**原因**: これは既知の制限です（usage-guide.md に記載済み）

**対処法**:
- 複数局サマリーでは Freedom は計算されません
- 代わりに Phase × Mistake クロス集計を使用します
- Freedom が必要な場合は単局カルテ（Export Karte）を使用します

---

## 成功基準

Phase 7 の動作確認が成功したと判断できる条件：

- [x] 複数局サマリーに Phase × Mistake Breakdown テーブルが表示される
- [x] Weakness Hypothesis セクションが上位3つの弱点を表示する
- [x] Practice Priorities が上位2つに絞られている
- [x] 単局カルテに Weakness Hypothesis (Focus Player) が表示される
- [x] 日本語が正しく表示される（UTF-8エンコーディング）

---

## 次のステップ

Phase 7 の動作確認が完了したら：

1. `docs/99-worklog.md` に動作確認の結果を記録
2. Phase 8（初心者向けヒント、任意）または Phase 9（検証テンプレ）に進む
