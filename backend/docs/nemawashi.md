# 根回し（HITL）機能

## 概要
根回し機能は、AI が生成したアクション案（メール／会議／HR）の実行前に、人間の承認・差し戻し・指示（steer）を挟む Human-in-the-Loop（HITL）ワークフローです。承認依頼は Slack に通知され、承認／却下／修正依頼が実行状態に反映されます。

## 主要な登場オブジェクト
- action: `autonomous_actions` に保存される実行対象。`action_id` を持つ。
- thread: `thread_id = action-{action_id}` で管理される承認スレッド。
- approval request: `approval_request_id = apr-************` の承認依頼 ID。
- execution job: `job_id = job-************` の実行ジョブ ID。

## 状態管理（HITL ステータス）
HITL の主要ステータスは `app/domain/hitl.py` に定義されています。

```
drafted -> approval_pending -> approved -> executing -> executed
                          \-> rejected
                          \-> failed
```

補足:
- `autonomous_actions.status` には `pending`（承認前の初期状態）も登場します。
- `is_approved` は承認の最終判定を保持し、`approved` で `TRUE` になります。

## ワークフロー（主な流れ）
1) アクション作成  
   - 監視機構（watchdog）または API で `autonomous_actions` を作成（初期 `pending`）。
2) 承認依頼  
   - `POST /api/v1/nemawashi/{draft_id}/request-approval`  
   - `approval_request_id` を発行し、`langgraph_checkpoints.metadata` に承認情報を保存。
   - Slack が設定されていれば承認メッセージを送信。
3) 承認／却下／差し戻し  
  - 承認: `approve` で `approved` に更新し、実行ジョブを開始。  
  - 却下: `rejected` に更新。  
  - 差し戻し: `steer` でドラフト末尾に `[Steer] {feedback}`（任意で `[Plan]`）を追記し、再度 `request-approval` を実行。
4) 実行  
   - 実行中は `executing`、完了で `executed`、失敗で `failed`。
   - Slack が設定されていれば実行結果をスレッドに通知。

## API エンドポイント
### 根回し／承認
- `POST /api/v1/nemawashi/{draft_id}/request-approval`  
  - body なし  
  - response: `thread_id`, `approval_request_id`, `status`, `action_id`, `slack`
- `POST /api/v1/approvals/{approval_id}/approve`  
  - response: `job_id`, `status`, `thread_id`, `action_id`
- `POST /api/v1/approvals/{approval_id}/reject`  
  - response: `{ "status": "rejected" }`
- `POST /api/v1/approvals/{approval_id}/steer`  
  - body: `feedback`（必須）, `selectedPlan`, `idempotencyKey`  
  - response: `ApprovalRequestResponse`（再承認依頼）

### 実行
- `POST /api/v1/nemawashi/{draft_id}/execute`  
  - body: `simulateFailure`（任意）, `calendar`（任意）  
  - `calendar` で payload を上書き可能  
  - response: `job_id`, `status`, `thread_id`, `action_id`

### 監査／履歴
- `GET /api/v1/audit/{thread_id}`  
  - response: `thread_id`, `events`（監査イベントの配列）
- `GET /api/v1/history`  
  - query: `status`, `project_id`, `limit`  
  - response: thread 単位の履歴一覧

### Slack 連携（HITL UI）
- `POST /api/slack/interactions`  
  - 承認メッセージのボタン（approve/reject/request changes）を処理。
- `POST /api/slack/events`  
  - スレッド返信を解析し、差し戻し（steer）を自動適用。

## Slack 連携の詳細
- 承認メッセージには 3 ボタン（Approve / Reject / Request changes）。
- ボタン値に `thread_id` / `approval_request_id` / `action_id` を埋め込み。
- 返信文の解析で Plan A/B/C の指定やキーワード検出を行い、`apply_steer` を実行。
- 署名検証: `SLACK_SIGNING_SECRET` が未設定の場合、`SLACK_ALLOW_UNSIGNED=true` で未署名を許可可能。

## データ保存の構成
### 主テーブル
- `autonomous_actions`  
  - action の本体（type / draft / status / is_approved）
- `langgraph_checkpoints`  
  - thread ごとの `checkpoint` と `metadata` を保持  
  - `metadata` には以下を保存:
    - `approval_request_id`, `status`, `requested_by`, `requested_at`
    - `execution_job_id`, `execution_status`
    - `slack`（channel / message_ts / thread_ts）
    - `audit_events`（監査ログ）
    - `idempotency_keys`
- `external_action_runs`  
  - 外部実行の結果（provider / response / error / executed_at）

### 追加テーブル（現状のコード参照なし）
- `hitl_states`, `hitl_approval_requests`, `hitl_audit_logs`, `execution_jobs`  
  - マイグレーションに存在するが、現状コードでは参照されていない。

## 監査ログ（audit_events）
`metadata.audit_events` に以下のイベントが追加されます。
- `approval_requested`
- `approval_approved`
- `approval_rejected`
- `human_feedback_received`
- `execution_started`
- `execution_succeeded`
- `execution_failed`

## 実行ロジック（外部アクション）
`autonomous_actions.action_type` により実行方法が決まります。
- `mail_draft`（メール）
- `meeting_request`（会議予約）
- `hr_request`（HR 申請）

ドラフトの末尾に JSON を置くと payload として抽出されます（最終行が `{...}` の場合）。  
payload 内に `actions` 配列がある場合はバッチ実行になります。

### 主要な設定値（環境変数）
Slack:
- `SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN`, `SLACK_DEFAULT_CHANNEL`
- `SLACK_WEBHOOK_URL`, `SLACK_REQUEST_TTL_SECONDS`, `SLACK_ALLOW_UNSIGNED`

外部実行:
- `EMAIL_PROVIDER`, `EMAIL_DEFAULT_TO`, `EMAIL_DEFAULT_FROM`
- `CALENDAR_PROVIDER`, `CALENDAR_DEFAULT_ATTENDEE`, `CALENDAR_DEFAULT_TIMEZONE`, `CALENDAR_DEFAULT_OWNER_EMAIL`
- `HR_PROVIDER`, `HR_API_URL`

## Watchdog との連携
watchdog はリスク判定後に `autonomous_actions` を生成し、即座に `request_approval` を呼び出します。  
その際 `langgraph_checkpoints.metadata` に `mode=watchdog`, `project_id`, `severity` を追加しています。

## 注意点／制約
- `POST /api/v1/nemawashi/{draft_id}/execute` は承認状態の検証を行わないため、承認前でも実行可能です。
- 承認 ID の検索は `langgraph_checkpoints` 全件スキャン（承認数が増えると負荷増）。
- ドラフト末尾の JSON を壊すと外部実行の payload 解析に失敗します。

## 参照ファイル
- `app/api/hitl.py`
- `app/domain/hitl.py`
- `app/api/slack.py`
- `app/integrations/slack.py`
- `app/domain/external_actions.py`
- `app/domain/watchdog.py`
- `migrations/0001_init.up.sql`
- `migrations/0002_m2_hitl_watchdog.up.sql`
