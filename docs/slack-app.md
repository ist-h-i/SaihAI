# Slack App 設計（通知/承認/HITL 連携）

本書は SaihAI の Slack 連携（通知/承認/介入）に必要な設定と運用方針を整理する。

## ゴール

- Slack 通知 → 承認/却下 → 介入（Steer）までを 1 スレッドで完結させる。
- 署名検証と冪等性を前提に、安全に状態遷移できること。

## 1. アプリ作成

1) https://api.slack.com/apps から新規アプリ作成（From scratch）
2) OAuth & Permissions を設定し、ワークスペースにインストール
3) Events / Interactivity の Request URL を設定

## 2. 必要スコープ（Bot Token Scopes）

- `chat:write`（通知送信）
- `views:write`（モーダルで介入指示を受け取る場合）
- `channels:read` / `groups:read` / `im:read` / `mpim:read`（投稿先の解決）
- `chat:write.public`（必要なら公開チャンネル投稿）

## 3. Request URL

- Interactivity: `POST /slack/interactions`
- Events: `POST /slack/events`

## 4. Events 設定（必要な場合のみ）

- HITL の Steer をスレッド返信で受け取る場合は、以下を購読:
  - `message.channels`
  - `message.groups`
  - `message.im`
  - `message.mpim`

※ デモ機能は「介入ボタン → モーダル入力」で完結するため、Events の購読は必須ではない。

## 5. 署名検証

- `SLACK_SIGNING_SECRET` を使用して署名検証を行う。
- Slack の署名は `v0:{timestamp}:{body}` を HMAC-SHA256 で署名。
- 受信時刻のズレは 5 分以内に制限（リプレイ対策）。

## 6. 環境変数

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_DEFAULT_CHANNEL=C0123456789
# ローカル検証用（署名検証を無効化する場合のみ）
SLACK_ALLOW_UNSIGNED=false
```

## 7. メッセージ設計（Block Kit）

- ヘッダー: HITL 承認の種別を明示
- セクション: 要約 / ドラフト本文（根回し文）
- アクション: Approve / Reject / Request changes
- コンテキスト: `thread_id` と `approval_request_id` を表示

## 7.1 デモフロー（追加）

- 初回投稿: Plan A/B/C と `✋ 介入` ボタンを提示
- `✋ 介入` → モーダル入力（callback: `demo_intervention_modal`）
- Plan/介入後: Approve / Reject / Cancel ボタンをスレッド内に投稿

## 8. 運用メモ

- 承認ボタンは `approval_request_id` を value に埋め込む。
- 介入テキストはスレッド返信として受信し、`approval_request_id` と関連付ける。
- Slack の Retry は同一 `event_id` を冪等キーとして扱う。
