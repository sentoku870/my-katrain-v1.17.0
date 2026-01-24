# Phase 22: 安定性向上計画

> **作成日**: 2026-01-16
> **ステータス**: 計画中
> **目的**: アプリケーションの安定性向上（クラッシュ、フリーズ、リソースリークの防止）

---

## Executive Summary

3つの調査（エラーハンドリング、スレッド/並行処理、メモリ/リソース）の結果から、重要度と優先度でトップ5の問題を選定。

**選定基準**:
1. ユーザーへの影響（クラッシュ、フリーズ、データ損失）
2. 再現性（通常使用で発生する確率）
3. 修正コスト vs 効果
4. 累積効果（時間経過で悪化する問題）

---

## Top 5 安定性問題

### Issue #1: エンジンスレッドのブロッキングI/O（タイムアウトなし）

| 項目 | 内容 |
|------|------|
| **重要度** | CRITICAL |
| **影響** | アプリ全体がフリーズ |
| **再現性** | KataGoがハング時に100%発生 |

**問題箇所**:
- `engine.py:310`: `stderr.readline()` - ブロッキング
- `engine.py:330`: `stdout.readline()` - ブロッキング
- `engine.py:450-451`: `stdin.write()` + `flush()` - ブロッキング

**根本原因**:
KataGoプロセスが応答しなくなった場合（メモリ不足、GPUクラッシュ等）、これらのブロッキング呼び出しが永久に戻らず、スレッドがハングする。

**修正方針**:
```python
# Windows: スレッドベースのタイムアウト
def _readline_with_timeout(pipe, timeout=5.0):
    result = [None]
    def read_line():
        result[0] = pipe.readline()
    t = threading.Thread(target=read_line, daemon=True)
    t.start()
    t.join(timeout)
    return result[0] if result[0] is not None else b""
```

**PR規模**: engine.py 1ファイル、+60-80行

---

### Issue #2: queriesディクショナリのレースコンディション

| 項目 | 内容 |
|------|------|
| **重要度** | CRITICAL |
| **影響** | KeyErrorクラッシュ、データ破損 |
| **再現性** | 解析中の新規ゲーム作成時に発生可能 |

**問題箇所**:
- `engine.py:217-223`: `terminate_query` で `queries.pop()` がロックなし
- `engine.py:261-269`: `wait_to_finish()` で `self.queries` をロックなしで読み取り

**根本原因**:
`thread_lock` の使用が一貫していない。一部の操作はロックを取得するが、他はしない。

**修正方針**:
```python
def terminate_query(self, query_id, ignore_further_results=True):
    if query_id is not None:
        self.send_query({"action": "terminate", "terminateId": query_id}, None, None)
        if ignore_further_results:
            with self.thread_lock:  # FIX: ロック追加
                self.queries.pop(query_id, None)

def wait_to_finish(self, timeout=30.0):
    start = time.time()
    while True:
        with self.thread_lock:  # FIX: ロック追加
            remaining = len(self.queries)
        if not remaining:
            return True
        # ...
```

**PR規模**: engine.py 1ファイル、~30-40行修正

---

### Issue #3: Clock.schedule_intervalがキャンセルされない

| 項目 | 内容 |
|------|------|
| **重要度** | HIGH |
| **影響** | メモリリーク、リソース浪費 |
| **再現性** | 長時間セッションで蓄積 |

**問題箇所**:
- `__main__.py:414`: `Clock.schedule_interval(self.handle_animations, 0.1)` - キャンセルなし
- `controlspanel.py:120`: `Clock.schedule_interval(self.update_timer, ...)` - キャンセルなし

**根本原因**:
`ClockEvent` を保存せずに `schedule_interval` を呼び出しているため、後でキャンセルできない。

**修正方針**:
```python
# __main__.py
self._animation_clock_event = Clock.schedule_interval(self.handle_animations, 0.1)

def cleanup(self):
    if self._animation_clock_event:
        self._animation_clock_event.cancel()
        self._animation_clock_event = None
```

**PR規模**: 2ファイル、~20-30行追加

---

### Issue #4: katago_processのTOCTOUレースコンディション

| 項目 | 内容 |
|------|------|
| **重要度** | HIGH |
| **影響** | AttributeErrorクラッシュ |
| **再現性** | シャットダウン中の解析時に発生 |

**問題箇所**:
- `engine.py:230-244`: `check_alive()` が `katago_process` をチェック後に使用
- `engine.py:281`: `shutdown()` が `self.katago_process = None` を設定
- `engine.py:308,328,415`: スレッドループ条件が `katago_process is not None` をチェック

**根本原因**:
複数スレッドが `self.katago_process is not None` をチェックした後に使用するが、別スレッド（特に `shutdown()`）がその間に `None` に設定する可能性がある。

**修正方針**:
```python
def _read_stderr_thread(self):
    while True:
        process = self.katago_process  # 参照をキャプチャ
        if process is None:
            return
        try:
            raw_line = process.stderr.readline()
            # 'self.katago_process' ではなく 'process' を使用
        except (OSError, AttributeError):
            return
```

**PR規模**: engine.py 1ファイル、~40-50行修正

---

### Issue #5: ポップアップdismiss遅延によるメモリ蓄積

| 項目 | 内容 |
|------|------|
| **重要度** | MEDIUM |
| **影響** | ポップアップ多用時のメモリ肥大 |
| **再現性** | クイズセッション等で顕著 |

**問題箇所**:
- `popups.py:109`: `Clock.schedule_once(self._do_update_state, 1)` - 1秒遅延

**根本原因**:
ポップアップ閉じた後、1秒間コンテンツがメモリに残る。連続でポップアップを開閉すると蓄積する。

**修正方針**:
```python
def _schedule_update_state(self, popup_instance):
    Clock.schedule_once(self._do_update_state, 0)  # 次フレームで実行
```

**PR規模**: popups.py 1ファイル、~5行修正

---

## 実装順序（依存関係考慮）

```
Issue #5 (Popup delay) ─────> 簡単、低リスク、即効果
    ↓
Issue #3 (Clock intervals) ─> 独立、良い実践
    ↓
Issue #2 (queries Race) ────> I/O変更前の基盤修正
    ↓
Issue #4 (TOCTOU) ──────────> #2と類似パターン
    ↓
Issue #1 (Blocking I/O) ────> 最も複雑、#2/#4完了後
```

**推奨PR構成**:
| PR | 内容 | 対象Issue |
|----|------|-----------|
| PR #1 | Quick wins: popup delay + clock cleanup | #5, #3 |
| PR #2 | Thread safety: queries + TOCTOU | #2, #4 |
| PR #3 | Blocking I/O timeout | #1 |

---

## リスク評価

| Issue | 修正リスク | 軽減策 |
|-------|-----------|--------|
| #1 | 中 - Windows/Unix差異 | クロスプラットフォームテスト |
| #2 | 低 - ロック追加は追加的 | デッドロック可能性確認 |
| #3 | 極低 - クリーンアップ追加 | イベントキャンセル確認 |
| #4 | 低 - 既知パターン | 全スレッド終了パス確認 |
| #5 | 極低 - タイミング変更のみ | UI応答性テスト |

---

## テスト戦略

### 自動テスト
```powershell
uv run pytest tests -v
```

### 手動テスト
1. **Issue #1**: KataGoプロセスを強制終了し、アプリがフリーズしないことを確認
2. **Issue #2**: 解析中に新規ゲームを連打し、クラッシュしないことを確認
3. **Issue #3**: 長時間（30分+）使用後のメモリ使用量確認
4. **Issue #4**: 解析中にエンジン再起動を繰り返し、クラッシュしないことを確認
5. **Issue #5**: クイズを100回連続実行し、メモリ増加が抑制されていることを確認

---

## 変更対象ファイル

| ファイル | 変更Issue | 変更内容 |
|----------|-----------|----------|
| `katrain/core/engine.py` | #1, #2, #4 | I/Oタイムアウト、ロック追加、TOCTOU修正 |
| `katrain/__main__.py` | #3 | Clockイベントキャンセル |
| `katrain/gui/controlspanel.py` | #3 | Clockイベントキャンセル |
| `katrain/gui/popups.py` | #5 | dismiss遅延短縮 |

---

## 変更履歴

- 2026-01-16: v1.0 作成（調査結果統合、Top 5選定）
