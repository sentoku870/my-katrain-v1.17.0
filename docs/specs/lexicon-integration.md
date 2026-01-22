`go_lexicon_master_last.yaml`（以下、Lexicon）は、単なる用語集ではなく、**「AIの数値データ」と「人間の概念」を橋渡しする知識グラフ**です。提供された資料（「IGQE調査」「KataGo学習・応用調査」など）に基づき、このファイルをKaTrainフォークで最大限活用するための機能トップ5を詳細設計ドラフトとして提案します。

---

# 機能設計書: Lexicon Integration for KaTrain-Fork

## 1. 自動意味タグ付けエンジン (Semantic Mistake Tagger)

**目的:**「ミスのタイプ分類タグ付け」の具体化。KataGoの解析結果（数値）と盤面パターンを、Lexiconの定義済みID（例: `aji_keshi`, `empty_triangle`）にマッピングし、AIの「-5目」という出力を「味消し（-5目）」という言語的指摘に変換する。

### 1.1 ロジック設計

Lexiconの `recognize_by` フィールドを、Pythonの判定ロジックにハードコード、またはルールエンジンとして実装する。

**マッピングテーブル例:**
| Lexicon ID | 判定ロジック (Heuristics) | 参照データ |
| :--- | :--- | :--- |
| **`empty_triangle`** (空き三角) | 自分の石3つが「L字」かつ中央が空点 AND `ScoreLoss` > 1.0 | 盤面形状, ScoreLoss |
| **`damezumari`** (ダメ詰まり) | グループの呼吸点 $\le$ 2 AND 敵に囲まれている AND `ScoreLoss` > 2.0 | Liberty Count, Enemy Adjacency |
| **`aji_keshi`** (味消し) | 相手の切断点/弱点を補強させる手 AND `ScoreLoss` > 1.0 AND 自分の `WinRate` 低下 | Shape Analysis, Previous/Next Move |
| **`overplay`** (打ち過ぎ) | 相手の厚み(`thickness`)に近い AND `ScoreStdev` > 20 (高リスク) AND `ScoreLoss` > 3.0 | Influence Map, ScoreStdev |

### 1.2 実装ドラフト (`core/analysis/semantic_tagger.py`)

```python
import yaml

class SemanticTagger:
    def __init__(self, lexicon_path):
        with open(lexicon_path) as f:
            self.lexicon = yaml.safe_load(f)['entries']
        # ID検索用のインデックス作成
        self.lex_map = {entry['id']: entry for entry in self.lexicon}

    def tag_move(self, node, analysis_result):
        tags = []

        # 1. 形状ベースの判定 (Shape Analysis)
        if self._is_empty_triangle(node):
            tags.append(self._create_tag('empty_triangle'))

        # 2. 数値ベースの判定 (Metric Analysis)
        if analysis_result['scoreLoss'] > 5.0 and analysis_result['scoreStdev'] > 20.0:
            tags.append(self._create_tag('overplay')) #

        # 3. 文脈ベースの判定 (Context)
        if self._is_aji_keshi(node): # 相手を固めた判定
            tags.append(self._create_tag('aji_keshi'))

        return tags

    def _create_tag(self, lex_id):
        entry = self.lex_map.get(lex_id)
        return {
            "id": lex_id,
            "term": entry['ja_term'],
            "warning": entry['pitfalls'] if entry.get('pitfalls') else ""
        }
```

---

## 2. RAG駆動型「なぜ悪手か」解説生成 (Lexicon-RAG Explainer)

**目的:**「LLMによる解説生成」および「AI推奨手の簡易解説」の強化。LLMが幻覚（Hallucination）を起こさないよう、Lexiconの記述を「正解データ（Ground Truth）」としてプロンプトに注入する。

### 2.1 プロンプトエンジニアリング設計

Lexiconの `ja_expanded`（詳細解説）、`pitfalls`（陥りやすい罠）、`contrast_with`（対比概念）を動的に挿入する。

**プロンプトテンプレート:**

```text
あなたは囲碁のコーチです。以下の局面でユーザーの手が悪手と判定されました。
KataGo解析データ: 損失 {score_loss} 目, 判定タグ: {detected_tags}

以下の「囲碁用語定義」を使用して、なぜこの手が悪いのかを{level}レベルの学習者に説明してください。

【参照定義: {lexicon_entry['ja_term']}】
定義: {lexicon_entry['ja_short']}
詳細: {lexicon_entry['ja_expanded']}
注意点: {lexicon_entry['pitfalls']}
比較概念: {lexicon_entry['contrast_with']}

出力要件:
1. 専門用語を正しく使うこと。
2. 「{lexicon_entry['ja_one_liner']}」という要点を引用すること。
```

### 2.2 データフロー

1.  **解析:** KataGoが `scoreLoss` を算出。
2.  **タグ付け:** 上記 `SemanticTagger` が `aji_keshi` を検出。
3.  **検索:** Lexiconから `id: aji_keshi` のエントリを取得。
4.  **生成:** LLMが「この手は味消しです。将来の可能性を消してしまいました（Lexicon定義に基づく解説）」を出力。

---

## 3. ユーザー棋力適応型フィルタリング (Level-Adaptive UI)

**目的:**「棋力別フィードバック調整」の具現化。Lexiconの `level` フィールド（1:初級, 2:中級, 3:上級）を利用し、ユーザーのランクに応じて表示する情報を制御する。

### 3.1 フィルタリングロジック

DDK（級位者）に「味消し（Level 2）」や「本手（Level 3）」を説いても混乱するだけである。Lexiconのレベル定義に基づき、表示制限を行う。

**表示ルール:**

- **Novice (15級以下):** `level: 1` のタグのみ表示（例: `atari`, `ladder`, `connection`）。
- **Intermediate (14級-5級):** `level: 1` + `level: 2` を表示（例: `shape`, `thicknes`）。
- **Advanced (4級以上):** 全レベルを表示（例: `aji`, `kikashi`, `probe`）。

### 3.2 実装イメージ (`core/gui/feedback_panel.py`)

```python
def get_displayable_mistakes(user_rank, detected_tags):
    allowed_level = 1
    if user_rank >= "5k": allowed_level = 2
    if user_rank >= "1d": allowed_level = 3

    display_list = []
    for tag in detected_tags:
        # Lexiconからレベルを取得
        lex_entry = lexicon_db.get(tag['id'])
        if lex_entry['level'] <= allowed_level:
            display_list.append(tag)

    return display_list
```

**効果:** 初心者には「アタリ！（Level 1）」だけを伝え、有段者には「それは味消し（Level 2）です」と伝えることで、認知負荷を最適化する。

---

## 4. 概念可視化オーバーレイ (Concept Visualization Overlay)

**目的:**「グループの生死・未確定石表示」の拡張。Lexiconにある抽象概念（厚み、味、模様）を、KataGoの `Ownership` や `Influence` ヒートマップを使って視覚化する。

### 4.1 概念と視覚化のマッピング

Lexiconの定義を「視覚的シグナル」に変換する。

| Lexicon ID          | 定義要約             | KataGoデータによる視覚化ロジック                                              | UI表示                                                 |
| :------------------ | :------------------- | :---------------------------------------------------------------------------- | :----------------------------------------------------- |
| **`moyo`** (模様)   | 地になりそうな勢力圏 | `Ownership` が 0.4〜0.7 (未確定だが偏りがある) の広範なエリア                 | 薄い色の雲のようなオーバーレイ                         |
| **`atsumi`** (厚み) | 堅固で外向きの勢力   | `Strength` (石の強度) が高く、`Influence` (放射影響) が広いエリア             | 石の周囲に「壁」のようなライン描画                     |
| **`aji`** (味)      | 潜在的な手残り       | 確定地(`Ownership` > 0.9)の中に、局所的に `Policy` 値が高い相手の着手点がある | その地点に「スパイス（味）」アイコンまたは「！」マーク |
| **`urgent`** (急場) | 放置すると致命的     | `ScoreLoss` が極大かつ `Ownership` が反転する地点                             | 盤上で赤く点滅                                         |

---

## 5. 「次の一手」スタイル一致クイズ (Style & Concept Quiz)

**目的:**「ミスのクイズ出題モード」とHuman-SLの統合。Lexiconの `category`（定石、手筋、ヨセ）に基づいて、特定のテーマに絞ったトレーニングを提供する。

### 5.1 クイズ生成ロジック

過去の棋譜やHuman-SLの自己対戦から、Lexiconのカテゴリに合致する局面を抽出して出題する。

**モード設定:**

1.  **「本手」クイズ:** `id: honte` にタグ付けされた手（AI評価が高く、かつHuman-SLのプロファイル `rank_9d` の一致率が高い手）を正解とする。「形を整える手を選べ」という問題。
2.  **「サバキ」クイズ:** `id: sabaki` の状況（敵の勢力圏内で `Ownership` が低い石）において、Human-SLが高く評価する「軽い手」を当てる。
3.  **「ヨセ」ドリル:** `category: endgame` に属する局面のみを抽出し、`scoreLoss` 0.5目以内の手を正解とする。

### 5.2 実装ドラフト (`core/quiz/quiz_generator.py`)

```python
def generate_quiz(game_record, focus_category="endgame"):
    candidates = []
    for node in game_record:
        # Lexiconカテゴリとの一致を確認
        if semantic_tagger.check_category(node) == focus_category:
            # 問題として適切な難易度か判定（Human-SLの一致率などを利用）
            if is_good_problem(node):
                candidates.append({
                    "board": node.board_state,
                    "answer": node.best_move,
                    "concept": lexicon_db.get_term_by_category(focus_category),
                    "hint": lexicon_db.get_one_liner(focus_category)
                })
    return candidates
```

---

## 6. 総合的な実装ロードマップ

これらの機能をKaTrainフォークに統合するためのステップです。

1.  **Phase 1 (基盤構築):** `go_lexicon_master_last.yaml` を読み込むクラスと、盤面状態からIDを判定する `SemanticTagger` のプロトタイプ（アタリ、空き三角など単純なもの）を実装。
2.  **Phase 2 (UI統合):** 解析パネルに「タグ」を表示する欄を追加。ユーザーランク設定に基づき表示をフィルタリングする機能（Feature 3）を実装。
3.  **Phase 3 (LLM連携):** 解析結果とLexicon定義をプロンプトに埋め込み、解説を生成するAPI連携（Feature 2）を実装。
4.  **Phase 4 (高度化):** Human-SLモデルを活用し、「本手」「味」などの抽象概念を判定ロジックに組み込む（Feature 1, 5の強化）。

この設計により、`go_lexicon_master_last.yaml` は単なる辞書ファイルから、KaTrainの**「教育的知能（Pedagogical Intelligence）」の中核**へと昇華されます。
