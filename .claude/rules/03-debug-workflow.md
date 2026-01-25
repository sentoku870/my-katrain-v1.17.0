# デバッグワークフロー（Debug Workflow）

> このファイルはバグ報告・デバッグ作業の進め方を定義します。
> 再現→原因特定→修正→確認のサイクルを標準化します。

---

## 1. 役割分担

### ユーザー
- 症状の報告（いつ/どこで/何が起きたか）
- 指定された手順での再現操作
- エラーメッセージ/ログのコピペ
- 動作確認

### Claude Code
- 症状の整理と仮説立て
- 再現手順の設計
- 必要な情報の指示
- 修正レベル（Lv0-5）の判定
- 修正の実行（Plan Mode 経由）
- 確認手順の提示

---

## 2. デバッグサイクル（7ステップ）

### Step 1: 現象の整理
- **いつ**: どの操作の後か
- **どの画面**: どのパネル/ダイアログか
- **何が起きた**: エラー？フリーズ？表示崩れ？
- **期待していた動作**: 本来どうなるはずか

### Step 2: 再現手順の確定
ユーザーが真似できる形で書く：
```
1. KaTrain を起動
2. ○○をクリック
3. SGF を読み込む
4. ○○を操作
5. → エラー発生
```

### Step 3: 情報収集
必要に応じてユーザーに依頼：
- **コンソール出力**: PowerShell のエラー全文
- **Traceback**: Python例外の全文
- **スクリーンショット**: 表示崩れの場合
- **SGFファイル**: 特定のSGFで発生する場合

### Step 4: 原因候補の整理
| 候補 | 可能性 | 確認方法 |
|------|--------|----------|
| UIのバグ | 高 | 別の操作で再現するか |
| 状態管理の不整合 | 中 | ログで状態を追跡 |
| KataGoエンジンの問題 | 低 | 別SGFで発生するか |

### Step 5: 修正方針とレベル決定
```
修正レベル: Lv2（中程度単一）
Git フロー: feature/YYYY-MM-DD-fix-xxx → PR
```

### Step 6: 修正と確認
1. Claude Code が修正を実行
2. ユーザーが再現手順で確認
3. 必要なら追加確認

### Step 7: 引継ぎメモ作成（任意）
長くなった場合は引継ぎメモを残す（後述）。

---

## 3. KaTrain 固有のデバッグポイント

### 3.1 よくある問題

| 症状 | 原因候補 | 確認方法 |
|------|----------|----------|
| 起動しない | 依存ライブラリ | `python -m katrain` のエラー |
| UI崩れ | Kivy レイアウト | `.kv` ファイルの構文 |
| 解析が動かない | KataGo 接続 | engine.py のログ |
| 日本語が化ける | i18n/エンコーディング | `.po` ファイル確認 |

### 3.2 ログ取得方法

**PowerShell でのUTF-8強制:**
```powershell
$env:PYTHONUTF8 = "1"
$OutputEncoding = [System.Text.Encoding]::UTF8
python -m katrain 2>&1 | Tee-Object -FilePath katrain_log.txt
```

**エラー全文の取得:**
```powershell
python -m katrain 2>&1
# Traceback があればそのまま全文コピー
```

### 3.3 関連ファイル

| 症状の領域 | 確認するファイル |
|------------|------------------|
| 起動/初期化 | `katrain/__main__.py` |
| 盤面表示 | `katrain/gui/badukpan.py` |
| 右パネル | `katrain/gui/controlspanel.py` |
| グラフ | `katrain/gui/widgets/graph.py` |
| 重要局面/ミス | `katrain/core/analysis/` (models.py, logic.py) |
| 解析 | `katrain/core/engine.py`, `game_node.py` |
| レイアウト | `katrain/gui.kv` |
| 翻訳 | `katrain/i18n/locales/*/katrain.po` |

---

## 4. 引継ぎメモ テンプレート

デバッグが長くなった場合に使用：

```markdown
## Debug 引継ぎメモ - YYYY-MM-DD

### 1. 対象
- myKatrain PC版

### 2. 現象
- 期待していた動作：
- 実際の動作：

### 3. 再現手順
1. 
2. 
3. 

### 4. 原因候補
- 第1候補：
- 第2候補：

### 5. 修正レベルとフロー
- 修正レベル：LvX
- Git フロー：feature/xxx → PR

### 6. 実施した修正
- 変更ファイル：
- 変更内容：

### 7. 確認結果
- 再現テスト：OK / NG
- 追加確認：
```

---

## 5. 一時デバッグログのルール

デバッグ中に一時的なログを追加する場合のルール。

### 5.1 追加時のルール

```python
# ✅ 良い例: [DEBUG] prefix を付ける
print(f"[DEBUG] radar data: {radar_data}")
Logger.log(f"[DEBUG] mesh vertices: {len(vertices)}", "DEBUG")

# ❌ 悪い例: prefix なし（本番コードと区別できない）
print(f"radar data: {radar_data}")
```

### 5.2 削除確認

修正完了後、コミット前に必ず残存確認:

```powershell
# PowerShell
Select-String -Path "katrain/**/*.py" -Pattern "\[DEBUG\]" -Recurse
```

または Claude Code が Grep で確認:
```
Grep(pattern="\[DEBUG\]", path="katrain", type="py")
```

### 5.3 本番コミットのチェックリスト

- [ ] `[DEBUG]` ログがすべて削除されている
- [ ] 一時的な `print()` 文がない
- [ ] テストが通る

---

## 6. 変更履歴

- 2026-01-25: v1.1 一時デバッグログのルールを追加
- 2025-12-30: v1.0 作成（Claude Code移行対応）
