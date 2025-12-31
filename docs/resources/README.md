# Implementation Resources

実装で使用する外部データ・リソース格納場所。

## ファイル一覧

### 囲碁用語辞書
- **go_lexicon_master_last.yaml** (361KB)
  - 囲碁用語の多言語辞書（日本語・英語）
  - 出典: 「囲碁はむずかしくない」プロジェクト
  - スキーマ: `go_lexicon_master_v1`
  - 最終更新: 2025-12-28

#### 構造
- `meta`: スキーマ情報・作成日・ソース
- `entries`: 用語エントリ（配列）
  - `id`: 用語ID（例: liberty, atari, joseki）
  - `level`: レベル（1=基本, 2=中級, 3=上級）
  - `category`: カテゴリ（rules, tactics, strategy等）
  - `ja_term` / `en_terms`: 日英用語
  - `ja_short` / `en_short`: 短い説明
  - `diagram`: SGF座標による図解（一部の手筋・形）
  - `related_ids`: 関連用語へのリンク
  - `sources`: 参考URL（2-4個）

#### 用途（Phase 7以降）
- 構造解析時の用語説明生成
- 初心者向けヒントの言語化
- 理由タグから用語解説への自動リンク
- 多言語対応（日英同時出力）

#### 管理方針
- Git管理下に置く（361KBは許容範囲、LFS不要）
- 元データは `D:\github\myKatrain_参考資料\` に保管
- 更新時は元データから再コピー
