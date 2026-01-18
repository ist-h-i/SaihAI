# SaihAI v2 ギャップ修正タスク（コード実装で解決）

本書は、以下 3 ドキュメントを基準に「現状リポジトリの実装」とのギャップを埋めるための **コード実装タスク** を列挙します。

- `docs/saihai-v2-acceptance-checklist.md`
- `docs/saihai-v2-backend-functional-design.md`
- `docs/saihai-v2-system-requirements.md`

> 注: 現状の実装は「Tactical Simulator / PoC」を主眼にした構成になっており、v2 要件（LangGraph/Redis/実運用の外部連携）を満たすには追加実装が必要です。

## PoC 方針（開発者のみ運用）

- Slack: 介入/再提示は「同一スレッドへの追加投稿」で実装（`chat.update` は使わない）
- Slack ACK: FastAPI `BackgroundTasks` で即時 200（キュー/ワーカーは導入しない）
- State: Redis/LangGraph を導入、DB（Postgres）の保存方式でデモを成立させる
- LLM/Embeddings: Bedrock 実呼び出しは必須
- External actions: Email/Calendar/HR は 実API連携

## 優先度

- **P0:** 二重実行・セキュリティ・Slack 側のタイムアウト/再送で破綻するもの
- **P1:** 主要 FR の成立（検知→提案→承認/介入→実行→履歴）
- **P2:** NFR（可用性/整合性/可観測性）・運用
- **P3:** 改善/負債返済

---

## P0: Slack/HITL の冪等性とスレッド整合

- [ ] **AC-ROB-002 承認ボタン二重押しで二重実行しない**
  - 現状: `backend/app/domain/hitl.py` の `approve_request()` は重複呼び出しで毎回 `process_execution_job()` を実行しうる（Slack 再送/二重押しで二重実行のリスク）
  - 修正案:
    - `langgraph_checkpoints.metadata` に `execution_job_id` / `execution_status` を保存し、`approved/executing/executed` のときは **再実行せず既存結果を返す**
    - `autonomous_actions.status` も参照し、`executing/executed` のときは実行開始しない
  - 変更候補:
    - `backend/app/domain/hitl.py`（`approve_request`, `process_execution_job`, `reject_request`）

- [ ] **AC-ROB-001 Slack Event 再送で二重処理しない（Interactions も含む）**
  - 現状: `backend/app/api/slack.py` の `/slack/interactions` は `hitl_approve/hitl_reject` を冪等キーなしで処理
  - 修正案:
    - Interactions payload から冪等キー（例: `payload.action_ts` + `approval_request_id` + `action_id`）を生成し、チェックポイント `metadata.idempotency_keys` に保存して重複を無視
  - 変更候補:
    - `backend/app/api/slack.py`
    - `backend/app/domain/hitl.py`（idempotency 管理の共通化）

- [ ] **AC-FR4-003 / AC-FR5-003 スレッドが維持され、介入→再提示が同一スレッドで成立**
  - 現状: `apply_steer()` は再度 `send_approval_message()` を呼ぶが、スレッド内返信/メッセージ更新ではなく「新規投稿」になりやすい
  - PoC採用:
    - `chat.postMessage` の `thread_ts` を使って **同一スレッドに再提示**（実装最小・デモ向き）
  - 将来（必要なら）:
    - `chat.update` を実装して **元のメッセージを更新**（スレッドを汚したくない場合）
  - 変更候補:
    - `backend/app/integrations/slack.py`（update/post in thread 対応）
    - `backend/app/domain/hitl.py`（slack meta の扱い、再提示ルール）

- [ ] **AC-CONN-002 Slack ACK を 3 秒以内に返す**
  - 現状: `/slack/events`・`/slack/interactions` が DB 参照/更新を同期で行う（DB が遠いと遅延しやすい）
  - PoC採用:
    - FastAPI `BackgroundTasks` に処理を移し **即 200 を返す**
  - 将来（必要なら）:
    - ジョブキュー（Redis 等）に enqueue してワーカーで処理
  - 変更候補:
    - `backend/app/api/slack.py`
    - （ワーカー導入時）`backend/app/services/*` を新設

---

## P1: 監視データ収集（FR-001）

- [ ] **（Post-PoC）AC-PER-001 / AC-PER-002 / AC-RED-001 Redis+thread_id を前提にしたチェックポイント復元（LangGraph）**
  - PoC採用: Redis/LangGraph を導入
  - Post-PoC 実装案（設計書準拠）:
    - `langgraph` を導入し、`thread_id` をキーにした `StateGraph` を構築
    - checkpointer を Redis に変更し、Slack 介入時に **同一 thread_id の state を復元**して再計算
  - 変更候補:
    - `backend/pyproject.toml`（依存追加）
    - `backend/app/services/workflow_engine.py`（新設）
    - `backend/app/services/state_manager.py`（新設）
    - `backend/app/api/slack.py`（workflow 起動/再開）

- [ ] **AC-FR1-002 Slack ログの取得・保存**
  - 現状: Slack のメッセージ履歴を収集して DB に保存する仕組みが未実装（データ投入のSQLファイル作成を優先し、UIからの登録は後回しでよい）
  - 実装案:
    - `slack.conversations.history` 等で期間指定取得 → `slack_messages`（新テーブル）に保存
    - 冪等キーは `channel_id + ts`（または Slack の `client_msg_id`）でユニーク制約
  - 変更候補:
    - `backend/app/domain/input_sources.py` に `ingest_slack_logs()`
    - `backend/app/api/v1.py` に ingest/list エンドポイント追加（既存 `weekly-reports` と同様のパターン）
    - `backend/migrations/*.sql`（テーブル追加）

- [ ] **AC-FR1-003 勤怠ログの取得・保存**
  - 現状: 勤怠データの取り込み経路が未実装（データ投入のSQLファイル作成を優先し、UIからの登録は後回しでよい）
  - 実装案（PoC なら CSV から開始）:
    - `attendance_logs`（新テーブル）を追加し、CSV/API 取り込みを実装
    - 冪等キーは `employee_id + date`（ユニーク制約）
  - 変更候補:
    - `backend/app/domain/input_sources.py`（`ingest_attendance()`）
    - `backend/migrations/*.sql`

- [ ] **AC-FR1-004 収集処理の冪等性（Slack/勤怠を含める）**
  - 現状: 週報は `weekly_reports` の存在チェックで概ね冪等だが、他ソースが未整備（データ投入のSQLファイル作成を優先し、UIからの登録は後回しでよい）
  - 実装案:
    - 各テーブルにユニーク制約 + upsert（PostgreSQL `ON CONFLICT DO NOTHING`）

---

## P1: ベクトル埋め込み/類似検索（AC-VEC）

- [ ] **AC-VEC-001 埋め込みの保存（PoC: 疑似ベクトルでOK）**
  - 現状: `backend/app/domain/embeddings.py` は疑似ベクトル（hash + RNG）を生成している
  - PoC採用:
    - 現状の疑似ベクトル生成を維持し、`weekly_reports.content_vector` を埋める（Bedrock embeddings は不要）
  - Post-PoC:
    - Bedrock の embedding モデル（例: Titan Embeddings 等）で `float[]` を生成し `weekly_reports.content_vector` に保存
    - 失敗時はリトライ/エラー保存（AC-ROB-003 に連動）
  - 変更候補:
    - `backend/app/domain/embeddings.py`（PoC: 現状維持 / Post-PoC: 実装差し替え）
    - `backend/app/integrations/bedrock.py`（Post-PoC: embedding 呼び出し追加）

- [ ] **AC-VEC-002 類似検索が動作し、分析に利用される**
  - 現状: 類似検索 API/ドメインロジックが未実装
  - PoC採用:
    - DB からベクトルを読み出し、Python 側で類似度（例: cosine）計算して Top-K を返す
  - Post-PoC:
    - PostgreSQL+pgvector の場合は `SELECT ... ORDER BY content_vector <-> :query_vec LIMIT :k` を用意し、Monitor/Gunshi の根拠として参照
  - 変更候補:
    - `backend/app/domain/embeddings.py` に `search_weekly_reports()`
    - `backend/app/domain/watchdog.py` or 新設 `backend/app/agents/monitor.py` で利用

---

## P1: Watchdog / Monitor / Gunshi / Drafting（FR-002/003）

- [ ] **AC-FR2-001 Watchdog の定期実行（24/7）に耐える形のジョブ実装**
  - 現状: `enqueue_watchdog_job()` が DB に永続化せず job_id を返すのみ
  - 実装案:
    - `watchdog_jobs` / `watchdog_alerts`（既存 migration で作成済み）を実際に利用し、enqueue/run の状態遷移を保存
  - 変更候補:
    - `backend/app/domain/watchdog.py`
    - `backend/app/api/watchdog.py`

- [ ] **AC-FR2-002 Watchdog が異常候補リストを出力**
  - 現状: health snapshot と pending action 作成はあるが「候補リスト」や `watchdog_alerts` 永続化が未整備
  - 実装案:
    - 異常候補（project_id/employee_id/score/理由）を `watchdog_alerts` に保存し、Dashboard で参照可能にする

- [ ] **AC-FR2-003 Monitor Agent が JSON でリスク判定を返す / AC-FR2-004 JSON 壊れの復旧**
  - 現状: LLM を使った Monitor が未実装（ルールベースのみ）
  - PoC採用:
    - ルールベース（既存キーワード/スコア）で `risk_level` / `reason` 等の JSON を生成し、JSON 壊れ復旧は不要にする
  - Post-PoC:
    - Bedrock を使い、`docs/saihai-v2-system-requirements.md` の JSON 仕様で出力
    - JSON パース失敗時は「再要求（強制 JSON）」→それでも失敗ならフォールバック（低信頼ラベル）で復旧
  - 変更候補:
    - `backend/app/agents/monitor.py`（新設）
    - `backend/app/integrations/bedrock.py`（リトライ/usage ログ）

- [ ] **AC-FR3-001 Gunshi がプラン A/B（推奨付き）を提示**
  - 現状: `ai_strategy_proposals` はあるが、v2 の「根回し」用途としての生成が未実装
  - 実装案:
    - Monitor 出力 + 社員/案件データ + 類似検索を根拠に Plan A/B を生成して DB に保存（推奨フラグ含む）
  - 変更候補:
    - `backend/app/agents/gunshi.py`（新設）
    - `backend/app/domain/watchdog.py`（呼び出し/連携）

- [ ] **AC-FR3-002 Drafting Agent がメール/申請書下書きを生成**
  - 現状: 下書き生成が未実装（`autonomous_actions.draft_content` は簡易文）
  - 実装案:
    - 生成結果は構造化（email_draft / hr_request）し、Slack でプレビューできる形式へ
  - 変更候補:
    - `backend/app/agents/drafting.py`（新設）
    - `backend/app/domain/external_actions.py`（payload 仕様の整理）

---

## P1: 実行（FR-006）

- [ ] **AC-FR6-002 HR システム API POST（スタブ可）**
  - 現状: `backend/app/domain/external_actions.py` に HR/API 型がない
  - 実装案:
    - `ACTION_TYPE_HR` を追加し、`HTTP POST`（まずはスタブ URL）を実装
    - 結果を永続化（`external_action_runs` 等）して監査可能にする
  - 変更候補:
    - `backend/app/domain/external_actions.py`
    - `backend/migrations/*.sql`（必要なら action_type/履歴テーブル整備）

- [ ] **AC-FR6-003 Gmail API 送信予約 / AC-FR6-004 カレンダー作成**
  - 現状: `EMAIL_PROVIDER` / `CALENDAR_PROVIDER` は `mock` のみ
  - PoC採用:
    - `mock` のままデモする（「予約日時が反映された」ことを payload/監査ログ/Slack 通知で示す）
  - Post-PoC:
    - `gmail` / `google_calendar` などプロバイダ実装を追加
    - 予約の冪等性キー（`approval_request_id + action_type` 等）で二重作成を防ぐ
  - 変更候補:
    - `backend/app/domain/external_actions.py`

- [ ] **AC-FR6-005 実行完了が Slack に通知される**
  - 現状: 実行結果を Slack へ返す処理が未実装
  - 実装案:
    - `process_execution_job()` の成功/失敗で Slack thread に結果投稿（成功/失敗内訳、再実行案内）
  - 変更候補:
    - `backend/app/domain/hitl.py`
    - `backend/app/integrations/slack.py`

- [ ] **AC-ROB-004 部分失敗でも状態が矛盾しない**
  - 現状: 1 action 前提で部分失敗の表現がない
  - 実装案:
    - 1 承認で複数アクションを実行し、各アクションの成功/失敗を分離して保存・通知
    - `execution_jobs` / `external_action_runs`（既存 migration）を実際に利用する方向が自然

---

## P1: ダッシュボード（FR-007）

- [ ] **AC-FR7-001 履歴一覧 / AC-FR7-002 詳細ログ / AC-FR7-003 検索・フィルタ**
  - 現状:
    - `/api/v1/dashboard/initial` は存在するが「介入/実行/承認」の履歴 UI と検索が未整備
    - `/api/v1/audit/{thread_id}` はあるが UI 連携が薄い
  - 実装案:
    - Backend: `GET /api/v1/history?employee_id=&from=&to=&status=` 等を追加
    - Frontend: 履歴ページ/詳細モーダル/検索 UI を追加し、監査イベントを表示
  - 変更候補:
    - `backend/app/api/v1.py` / `backend/app/api/hitl.py`
    - `frontend/src/app/pages/dashboard.page.ts`（履歴表示の導線追加）
    - `frontend/src/app/core/api-client.ts` / `types.ts`

---

## P2: セキュリティ/可観測性/ヘルスチェック

- [ ] **AC-CONN-001 /health が依存サービス込みの健全性を返す**
  - 現状: `GET /api/health` は固定 `ok`
  - PoC採用:
    - DB ping を短いタイムアウトで確認し、OK/NG を返す（Redis/Slack auth.test は省略）
  - Post-PoC:
    - DB ping / Redis ping / Slack auth.test（任意）を実施してステータスを返す（タイムアウト必須）
  - 変更候補:
    - `backend/app/api/health.py`

- [ ] **AC-OBS-001 相関IDで追跡できる**
  - 現状: `X-Request-ID` はあるが、`thread_id` / `approval_request_id` をログへ一貫して出していない
  - 実装案:
    - HITL/Slack ハンドラで `thread_id` / `approval_request_id` を logger の構造化フィールド（またはメッセージ）として出力

- [ ] **（Post-PoC）AC-OBS-002 LLM コスト計測（入力/出力トークン、レイテンシ）**
  - PoC採用: mock 利用が前提のため、計測は省略
  - Post-PoC:
    - Bedrock `converse` の `usage` を取得してログ/メトリクスに送る（失敗時もレイテンシ記録）
    - リトライ（指数バックオフ）を実装（AC-ROB-003）

---

## P3: 文字化け/表示品質（必要なら）

- [ ] **ダッシュボード/プラン生成で日本語が文字化けしている文字列を修正**
  - 例: `backend/app/api/v1.py` の一部文言が mojibake になっている
  - 影響: UI の品質低下（FR-007 の受け入れ証跡が取りづらい）
