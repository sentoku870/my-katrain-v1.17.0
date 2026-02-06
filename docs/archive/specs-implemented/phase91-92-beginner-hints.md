# Phase 8: 初心者向けヒント（Safety Net / Anti-Self-Sabotage）仕様案（MVP）

## 0. 目的

初心者の「自滅（石が即死・取り逃し・分断放置）」を減らし、**何が悪かったかを1つだけ分かる**状態にする。  
「最善手提示」ではなく、**危険の可視化（最低限の安全柵）**に限定する。

---

## 1. スコープ

### 1.1 追加するもの（Phase 8 MVP）

- **Beginner Hint（1手につき最大1件）**の提示
- **構造解析ベースの自滅系検出**（2〜4カテゴリ）
- **MeaningTags（Phase 46）等の既存理由タグの初心者翻訳**でテンプレ10個を成立させる
- **設定でON/OFF可能**（有段者には邪魔になりうるため必須）

### 1.2 やらないこと（Phase 8では捨てる/後回し）

- 盤面全体の常時オーバーレイ（アイコン散布、点線多用、ヒートマップ常時表示）
- ホバー等の「着手前」警告（対局補助＝チート衝突＋UI工数増）
- ownership 断定系（「死に石」「確定地」「自陣埋め」を強く断定）
- ラダー（シチョウ）の自前判定（例外が多く割に合わない）
- 「ここに打て」の具体手提示（コーチング寄りになるため）

※ 上記は Future アイテムとして別フェーズ扱いにする。

---

## 2. 適用モード（チート衝突回避）

- **有効**: Review / Analysis（着手後にエンジン解析が付いたタイミング）
- **無効**: PLAY中（リアルタイム対局支援を避ける）

---

## 3. UI仕様（最小・安定・低工数）

### 3.1 表示場所

- 右パネル（既存のカルテ/コメント枠の近く）に **「Beginner Hint」枠**を追加
- 1手につき **最大1件**のみ表示（ノイズ抑制）
- 盤上表現は任意で **単一点ハイライト（丸枠）**のみ  
  （アイコン多用はしない。描画バグ・性能問題を避ける）

### 3.2 表示内容（固定フォーマット）

- タイトル（短い警告）
- 1行説明（初心者向け平易文）
- 「なぜ？」の一言（呼吸1、切れ、取り逃し等の理由）
- （任意）関連タグ（デバッグ用に小さく表示できるように）

---

## 4. 設定（myKatrain設定でON/OFF）

### 4.1 設定項目（案）

- 設定名: **Beginner Support**
- config key（例）:
  - `ui.beginner_hints.enabled: bool`（default: OFF 推奨）
  - `ui.beginner_hints.scope: "review_only"`（固定でOK。将来拡張用）
  - `ui.beginner_hints.board_highlight: bool`（default: ON）
  - `ui.beginner_hints.min_mistake_category: "MISTAKE"`（default）
  - `ui.beginner_hints.require_reliable: bool`（default: ON）

### 4.2 デフォルト値の推奨

- 既存ユーザーへの影響を避けるため、**default OFF**が無難  
  （初心者向けディストリや新規プロファイルだけONにする運用も可能）

---

## 5. 判定ロジック（MVP：確実に当たるものだけ）

### 5.1 入力

- 現局面の盤構造（グループ/呼吸点/連絡点/切断点）
- エンジン解析結果（MistakeCategory、信頼度、既存理由タグ）
- 直近の着手情報（座標、手番）

### 5.2 フィルタ（ノイズ抑制）

- 原則: `MistakeCategory >= MISTAKE` かつ `reliable == True` の時だけ提示
- 例外: ルール級（illegal / 自殺）だけは常に提示して良い

### 5.3 1手1ヒント選択（優先順位固定）

（上ほど強い）

1. `illegal_suicide`（ルール違反/自殺に近い）
2. `beginner:self_atari`（打った手で自分が即危険）
3. `beginner:ignore_atari`（呼吸1の自分グループを放置）
4. `beginner:missed_capture`（相手呼吸1を取り逃し）
5. `beginner:cut_risk`（切断点放置/連絡点不足）
6. 翻訳タグ（MeaningTags等からの初心者翻訳）

※ Phase 8は「危険を知らせる」まで。推奨手提示はしない。

### 5.4 盤上ハイライト座標（単一点）

- self_atari: **着手点**
- ignore_atari: **危険グループの代表石（任意の1石）**
- missed_capture: **取れる相手グループの代表石（任意の1石）**
- cut_risk: **切断点（連絡点）**

---

## 6. Reasonタグ設計（新規は最小）

### 6.1 新規（最大4つまで）

- `beginner:self_atari`
- `beginner:ignore_atari`
- `beginner:missed_capture`
- `beginner:cut_risk`

### 6.2 既存タグ（翻訳で使用）

- 既存の MeaningTags / mistake reasons をそのまま受け取り、初心者文へ変換
- **テンプレ10個の不足分は翻訳タグで埋める**（自作判定の増殖を避ける）

---

## 7. テンプレ（10個）定義（JP）

> 「テンプレID」＝ i18n msgid にする前提（例: `beginner_hint:self_atari:title`）

### 7.1 コア4（構造解析）

| Template ID                  | 対応タグ                | 表示タイトル（短） | 表示文（1行）                          | 理由（短）    |
| ---------------------------- | ----------------------- | ------------------ | -------------------------------------- | ------------- |
| beginner_hint:self_atari     | beginner:self_atari     | あぶない手         | そこに打つと、すぐ取られやすいです。   | 呼吸が少ない  |
| beginner_hint:ignore_atari   | beginner:ignore_atari   | アタリ放置         | 取られそうな石をそのままにしています。 | 呼吸が1       |
| beginner_hint:missed_capture | beginner:missed_capture | 取り逃し           | いま取れる石を逃しています。           | 相手の呼吸が1 |
| beginner_hint:cut_risk       | beginner:cut_risk       | 切られそう         | ここを切られると石が分断されます。     | 連絡点が弱い  |

### 7.2 翻訳6（既存タグ→初心者文）

※ 具体の元タグ名は実装時に repo 実態へ合わせる（MeaningTagsのID/キーに合わせて調整）

| Template ID                     | 元タグ例（候補）          | 表示タイトル（短） | 表示文（1行）                        |
| ------------------------------- | ------------------------- | ------------------ | ------------------------------------ |
| beginner_hint:low_liberties     | low_liberties / atari     | 呼吸が少ない       | 石が取られやすい状態です。           |
| beginner_hint:self_capture_like | self_capture / self_atari | 自分が苦しい       | 自分の石が逃げにくくなっています。   |
| beginner_hint:bad_shape         | empty_triangle 等         | 形が悪い           | 石が働きにくい形です。               |
| beginner_hint:heavy_group       | heavy / overconcentrated  | 石が重い           | 逃げにくく、攻められやすいです。     |
| beginner_hint:missed_defense    | defend / urgent           | 守りが必要         | 先に守らないと損しやすいです。       |
| beginner_hint:urgent_vs_big     | urgent / big_point        | 急場が先           | 大場より先に、危ない所を見ましょう。 |

> 注: 翻訳6は「候補」であり、実装時に既存タグの一覧に合わせて置換する。  
> 重要なのは **テンプレ10個が固定IDとして定義されること**（文言調整は後で差し替え可能）。

---

## 8. i18n（推奨）

- msgid 形式（例）:
  - `beginner_hint:self_atari:title`
  - `beginner_hint:self_atari:body`
  - `beginner_hint:self_atari:why`
- JPロケールはプロジェクトルールに従い **`jp`** を使用
- UI上でキーが出た場合は `.mo`未生成を疑い、i18n生成手順で解決する

---

## 9. 実装分割（Phase 8内部の最小ステップ）

### 8-A（必須）

- 設定ON/OFFの導入（UI + config）
- 1手1ヒント枠の導入（右パネル）
- コア4タグの判定・表示（構造解析）

### 8-B（必須）

- MeaningTags等の既存タグ→テンプレ翻訳（6個分）
- フィルタ（MistakeCategory / reliable）適用

### 8-C（任意）

- 盤上単一点ハイライト（描画が安定するなら）

---

## 10. テスト/受け入れ条件（最低限）

### 10.1 受け入れ条件（MVP）

- Beginner Support をOFFにすると一切表示されない
- Review/Analysisでのみ動作し、PLAY中は出ない
- 1手につきヒントが最大1件
- コア4カテゴリが最低1つずつ再現局面で発火する
- 信頼度が低い解析（reliable=False）では出ない（例外: illegal/suicide）

### 10.2 テスト対象（例）

- 自アタリ局面
- アタリ放置局面
- 取り逃し局面
- 切断点放置局面
- 翻訳タグ表示（元タグ→テンプレID→文言）

---

## 11. Future（Phase 8以降の候補）

- ownership を“参考表示”として導入（断定しない）
- 終局チューター（整地支援）
- ラダー等の探索系（エンジン出力が安定して取れる場合のみ）
- 盤上オーバーレイの拡張（アイコン、領域塗りなど）
- ホバー警告（PLAY補助にならない設計が確立した場合のみ）
