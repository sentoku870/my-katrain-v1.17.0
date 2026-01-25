# Git ワークフロー（Git Workflow）

> このファイルは myKatrain での Git/GitHub 運用ルールを定義します。
> Claude Code はコミットまで実行可。push/PR作成はユーザー確認後に実行。

---

## 1. ブランチ方針

### 1.1 ブランチの役割

| ブランチ | 用途 | 直接コミット |
|----------|------|:------------:|
| `main` | 開発の基準ブランチ | docs-only のみ可 |
| `feature/YYYY-MM-DD-<short-desc>` | code-change 用作業ブランチ | ○ |
| `docs/YYYY-MM-DD-<short-desc>` | 大改稿ドキュメント用（任意） | ○ |

### 1.2 リポジトリ情報
- **リモート**: `sentoku870/my-katrain-v1.17.0`
- **ローカル**: `D:\github\katrain-1.17.0`

---

## 2. code-change フロー（Lv0-4）

code-change（コード変更を含む）は、レベルに関係なく以下のフローを使用。

### 2.1 手順

```powershell
# 1) リポジトリへ移動
cd D:\github\katrain-1.17.0

# 2) main を最新にする
git switch main
git pull origin main

# 3) 作業ブランチを作成
git switch -c feature/2025-12-30-<short-desc>

# 4) Claude Code で修正を実行
#    （Claude Code が直接ファイルを編集）

# 5) 差分確認
git status
git diff

# 6) 動作確認
python -m katrain              # 起動確認
uv run pytest tests            # テスト（必要に応じて）

# 7) コミット
git add -A
git commit -m "<type>: <short-desc>"

# 8) push
git push -u origin HEAD

# 9) PR 作成
gh pr create --base main --fill
```

### 2.2 コミットメッセージ例

| type | 用途 | 例 |
|------|------|-----|
| `feat` | 新機能 | `feat: add karte export button` |
| `fix` | バグ修正 | `fix: quiz crash on empty analysis` |
| `refactor` | リファクタリング | `refactor: extract eval logic to separate module` |
| `docs` | ドキュメント | `docs: update roadmap for Phase5` |
| `style` | フォーマット | `style: fix indentation in game.py` |
| `test` | テスト | `test: add quiz generation tests` |
| `chore` | その他 | `chore: update dependencies` |

---

## 3. docs-only フロー（簡易コミット）

docs-only（ドキュメントのみ）は main 直接コミット可。

```powershell
# 1) main で作業
cd D:\github\katrain-1.17.0
git switch main
git pull

# 2) ドキュメントを修正

# 3) コミット & push
git add -A
git commit -m "docs: <short-desc>"
git push
```

### 大改稿の場合（任意）
ファイル多数/再編/レビューしたい場合は、ブランチ + PR を使用：

```powershell
git switch -c docs/2025-12-30-<short-desc>
# 修正後
git push -u origin HEAD
gh pr create --base main --fill
```

---

## 4. PR 操作（gh コマンド）

### 4.1 初回設定（1回だけ）
```powershell
gh auth login
gh auth setup-git
gh repo set-default sentoku870/my-katrain-v1.17.0
```

### 4.2 PR 作成
```powershell
gh pr create --base main --fill
```

### 4.3 PR 確認
```powershell
gh pr view <number>
gh pr checks <number>
```

### 4.4 PR マージ（CI通過後）
```powershell
gh pr merge <number> --merge --delete-branch
```

---

## 5. トラブル時の対処

### 5.1 変更を元に戻したい（未コミット）
```powershell
git restore .
```

### 5.2 特定ファイルだけ戻したい
```powershell
git restore <path>
```

### 5.3 コミット済みを戻したい
```powershell
git log --oneline -5    # 履歴確認
# reset は慎重に（必要なら相談）
```

### 5.4 ブランチを間違えた
```powershell
git stash               # 変更を退避
git switch main
git switch -c feature/correct-name
git stash pop           # 変更を戻す
```

---

## 6. Claude Code の役割

### Claude Code がやること
- ファイルの編集
- `git add` / `git commit`（コミットまで実行可）
- 差分の説明
- 次のコマンドの提示

### ユーザー確認後に実行
- `git push`
- `gh pr create`

→ push/PR作成は「pushしていい？」等の確認後に実行。

### Claude Code がやらないこと（禁止）
- `git push --force`（明示的な指示がない限り）
- `git reset --hard`（明示的な指示がない限り）
- main ブランチへの直接 push（code-change の場合）

---

## 7. 変更履歴

- 2026-01-25: v1.1 Claude Codeのコミット実行を許可、push/PRは確認後に変更
- 2025-12-30: v1.0 作成（Claude Code移行対応、Codex CLI から移行）
