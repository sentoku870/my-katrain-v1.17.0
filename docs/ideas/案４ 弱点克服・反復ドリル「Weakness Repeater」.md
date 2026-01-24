提供されたソース（`00-purpose-and-scope.txt`、`01-roadmap.txt`）およびこれまでの開発文脈（Phase 46 MeaningTags、Phase 48 Radar）に基づき、**「Phase 59: Weakness Repeater（弱点特化型・反復ドリル）」**の仕様草案を作成しました。

この機能は、`00-purpose-and-scope.txt` にある**「目的は『最善手当てクイズ』ではなく、弱点の同定と矯正」**というコア・フィロソフィーを最も体現する機能です。

---

# 仕様草案: Phase 59 - "Weakness Repeater" (弱点克服・反復ドリル)

## 1. 概要 (Concept)

過去のユーザー自身の対局データ（解析済みSGF）から、特定の**「負けパターン（MeaningTags）」**に該当する悪手のみを抽出し、**「自分のミスを自分で修正する」**ためのドリルを自動生成する。
汎用的な詰碁ではなく、「自分が実際に間違えた局面」を使うことで、当事者意識と学習効果を最大化する。

## 2. データ構造設計 (Data Model)

### 2.1 `DrillProblem` (ドリル問題オブジェクト)

`katrain/core/drill/models.py` に定義。単なるクイズではなく、元となったミスのコンテキストを保持する。

```python
@dataclass(frozen=True)
class DrillProblem:
    id: str                  # 一意のID (game_id + move_number hash)
    sgf_path: str            # 元ファイルのパス
    move_number: int         # 問題となる局面の手数
    player_color: str        # 'B' or 'W'

    # ミス情報
    played_move_gtp: str     # 実際に打ってしまった悪手
    played_loss: float       # その手の損失 (例: 5.4目)
    meaning_tag: str         # Phase 46で付与されたタグ (例: 'aji_keshi', 'overplay')

    # 解決条件
    best_move_gtp: str       # AI推奨手
    acceptable_loss: float   # 正解とみなす許容損失範囲 (例: 0.5目以内)

    # SRS (Spaced Repetition System) 管理用
    mastery_level: int = 0   # 0:未習得 -> 5:完全に理解
    next_review_due: float   # 次回出題予定時刻 (timestamp)
```

## 3. ロジック設計 (Core Logic)

### 3.1 問題抽出エンジン (`DrillExtractor`)

**目的:** 大量のSGFから「矯正すべき悪手」だけをフィルタリングする。

- **入力:** 解析済みSGFフォルダ, ターゲットタグ（例: `['endgame_loss', 'life_death_error']`）
- **抽出フィルタ基準 (野狐初段〜五段向け調整):**
  1.  **損失閾値:** `score_loss` > 3.0 (小さすぎるミスは無視)
  2.  **タグ一致:** 指定された `MeaningTag` が付与されていること。
  3.  **確信度:** `is_reliable` が True であること (AIの読み抜けを除外)。
  4.  **除外:** 序盤の定石（Opening）は除外オプションあり（中盤・終盤のミスに特化するため）。

```python
def extract_problems(games: List[Game], target_tags: List[str]) -> List[DrillProblem]:
    problems = []
    for game in games:
        for node in game.traverse():
            # Phase 46/47のMeaningTagsを利用
            if node.analysis.meaning_tag in target_tags and node.analysis.score_loss > 3.0:
                problems.append(DrillProblem(...))
    return problems
```

### 3.2 判定ロジック (`AnswerEvaluator`)

既存の「最善手当て」とは異なり、**「元の悪手よりマシならOK」ではなく、「悪手の原因（タグ）を解消していればOK」**とする。

- **OK判定:**
  - 損失が `acceptable_loss` (0.5〜1.0目) 以内の手を打った。
  - **Lexicon連携:** 打った手に対し、AIが再度タグ付けを行い、禁止タグ（例: `aji_keshi`）が付かなくなったか確認。
- **NG判定:**
  - 元の悪手と同じ手を打った（「再現」してしまった）。
  - 別の種類の悪手（例: 味消しは避けたが、死活で見損じた）を打った。

---

## 4. UI/UX設計 (Drill Mode Interface)

### 4.1 ドリル設定メニュー

「何を克服しますか？」という問いかけでフィルタリングを行う。

- **モード選択:**
  - 🚑 **Emergency Care (救急外来):** 直近10局のワースト悪手トップ5を即座に出題。
  - 🛡️ **Solidify Defense (ポカ避け):** `overplay` (打ちすぎ) / `cut` (切断見落とし) タグに限定。
  - 👁️ **Tactical Eye (死活・手筋):** `life_death_error` / `missed_tesuji` タグに限定。
  - 🍂 **Endgame Precision (ヨセ):** `endgame_loss` / `aji_keshi` タグに限定。

### 4.2 出題画面の挙動

1.  **Scene Setting (状況説明):**
    - 盤面を表示。「この局面で、あなたは **5目損** をしました。原因は **『味消し (Aji-Keshi)』** でした。」と表示。
    - **ヒント:** Phase 45 `Lexicon` から「味消し」の定義をツールチップで表示。
2.  **Action (回答):**
    - ユーザーが着手。
3.  **Feedback (即時評価):**
    - **正解:** 「Excellent! AI推奨手と一致しました。味を残して正解です。」
    - **再犯 (Bad):** 「あっと！ **実戦と同じミス** です。これでは相手に地を固めさせてしまいます。」（実戦の進行を数手再生して痛みを思い出させる）
    - **惜しい:** 「悪くはないですが、もっと良い手があります（損失 -1.5目）。」

---

## 5. ロードマップへの統合

`01-roadmap.txt` の Phase 52 以降に配置します。

### Phase 59: Weakness Repeater Core (Extraction & Storage)

- **目的:** 解析済みデータから問題を抽出し、軽量JSON DB (`drills.json`) に保存する仕組み。
- **実装:** `core/drill/extractor.py`, `core/drill/store.py`
- **依存:** Phase 46 (MeaningTags), Phase 13 (Smart Kifu DB)

### Phase 60: Drill UI & Feedback Loop

- **目的:** 実際にドリルをプレイする画面と、SRS（忘却曲線）に基づく再出題スケジューリング。
- **実装:** `gui/features/drill_mode.py`
- **UX:** 「自分のミス」と向き合うのは苦痛であるため、正解時に **「以前の自分を超えた」** ことを強調する演出（完了音、成長グラフ）を入れる。

## 6. この機能の「野狐初段〜五段」への効果

資料 `Abstract (Overview of Findings).docx` にある通り、この層の最大の課題は**「知識はあるが、実戦で同じパターンのミス（Habitual Bad Moves）を繰り返す」**ことです。

- **一般的な詰碁:** 「きれいな正解」があるが、実戦に出にくい。
- **Weakness Repeater:** 「汚い実戦形」であり、**「自分がついやってしまう手」**が不正解の選択肢として強烈に刷り込まれている。

これを反復することで、実戦で似た局面になった際、**「あ、これドリルで見た『いつもの自滅パターン』だ」**と気づき、手が止まるようになります（メタ認知の獲得）。
