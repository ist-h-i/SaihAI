# セットアップガイド（外部サービス・環境変数・ローカル確認）

本ドキュメントは、SaihAI プロジェクトが利用（または想定）する外部サービスの一覧、セットアップ手順、必要な環境変数、ローカルでの動作確認方法をまとめたものです。

- 対象範囲: localhost 起動（Backend/Frontend）しつつ、**必須の AWS サービス（Bedrock / PostgreSQL+pgvector）** を接続する（ALB/CloudFront は PoC では扱わない）
- 目的: 新規参加者が迷わず **ローカル + AWS最小（Bedrock + pgvector DB）** で動かせること
- 参照: `STRANDS_BEDROCK.md`、`docs/db-idea.md`

## まずは localhost で動かす（PoC / AWS最小）

PoC ではアプリ（Backend/Frontend）は localhost で起動し、**AI とベクトルDBは AWS を利用します**。

- 必須: AWS Bedrock（推論） / AWS PostgreSQL + pgvector（ベクトルDB）
- 不要: ALB / CloudFront（配信・負荷分散は後回し）

0) AWS 側の最小セットアップ（必須）

- Bedrock: モデル有効化（Model access）と必要な値の取得
- DB: Aurora PostgreSQL（または RDS for PostgreSQL）+ pgvector の用意と、ローカルから接続できる経路/SG 設定
- 手順は `docs/aws-setup.md` の「PoC / localhost」セクションを参照

1) 依存関係のセットアップ（初回のみ）

```bash
bash dev-setup.sh
```

2) `backend/.env` の設定（必須）

最低限、以下を設定します（例）。

```bash
DATABASE_URL=postgresql+psycopg://<DbUser>:<DbPassword>@<DbEndpoint>:5432/<DbName>?sslmode=require
AWS_REGION=ap-northeast-1
AWS_BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
AWS_BEARER_TOKEN_BEDROCK=your-api-key-here
```

3) DB の初期化（必須）

```bash
cd backend
uv run python scripts/db_tool.py up
uv run python scripts/db_tool.py seed --force
```

DB 疎通で `Operation timed out` になる場合は、まず `docs/aws-setup.md` の「接続テスト（ローカル）」で `nc -vz <DbEndpoint> 5432` を確認し、Security Group の許可元IPなどを見直してください。

3.5) 週報データ投入（任意）

```bash
cd backend
uv run python scripts/ingest_weekly_reports.py
```

4) 起動

```bash
bash dev-start.sh
```

5) 動作確認

- Backend: `http://localhost:8000/api/health`
- Frontend: `http://localhost:4200/`

ポートが使用中の場合、`dev-start` が `8001` / `4201` に自動で切り替えます（表示される URL を参照してください）。

## 外部サービス一覧（カテゴリ別）

- ローカル PoC: アプリは localhost、外部依存は **AWS Bedrock / AWS PostgreSQL+pgvector**（ALB/CloudFront は不要）
- AI（LLM / 埋め込み）
  - AWS Bedrock Runtime（Anthropic Claude 等）
    - 用途: 推論実行（Strands Agent 経由で Bedrock を呼び出し）
- データベース
  - PostgreSQL + pgvector
    - 用途: コアデータ管理（users/projects 等）、ベクトル検索（週報ベクトル）、LangGraph のチェックポイント保存
- チャット/通知
  - Slack（Web API / 将来: Events/Interactive）
    - 用途: 通知・介入・承認（Block Kit）

## AI: AWS Bedrock のセットアップ（必須）

PoC の機能要件として Bedrock を利用します。セットアップ手順（Model access の有効化など）は `docs/aws-setup.md` を参照してください。

前提条件
- AWS アカウント（Bedrock 利用権限付与済み）
- モデル（例: Claude 4.x / Haiku / Sonnet）がアカウントで有効

環境変数（.env 例）
```
AWS_BEARER_TOKEN_BEDROCK=your-api-key-here
AWS_REGION=ap-northeast-1
AWS_BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
```

手順
- Backend は `backend/app/env.py` の `load_env()` で `.env` を読み込み（python-dotenv は不要）
  - 読み込み順: 実行時のカレントディレクトリ → リポジトリルートの `.env` → `backend/.env`（先に見つかった 1 つのみを読む）
- Strands Agent を用いた最小サンプルは `STRANDS_BEDROCK.md` を参照
  - 事前に `pip install strands-agents python-dotenv` を実行（サンプル側は python-dotenv を利用）
  - `.env` に上記 3 つの環境変数を定義

ローカル動作確認
- `STRANDS_BEDROCK.md` のサンプルコードを実行し、日本語プロンプトに対する応答が返ることを確認

参考
- `STRANDS_BEDROCK.md` 内「トラブルシュート」を参照（リージョン誤り・トークン無効など）

## DB: PostgreSQL + pgvector のセットアップ（AWS / 必須）

PoC の機能要件として、AWS 上の PostgreSQL + pgvector を利用します（ALB/CloudFront は不要）。

前提条件
- Aurora PostgreSQL（または RDS for PostgreSQL）を作成済み
- ローカルから DB に接続できる経路（SG 許可 / SSM 踏み台 / VPN など）

環境変数（`backend/.env` 例）

```bash
DATABASE_URL=postgresql+psycopg://<DbUser>:<DbPassword>@<DbEndpoint>:5432/<DbName>?sslmode=require
```

初期化（必須）

```bash
cd backend
uv run python scripts/db_tool.py up
uv run python scripts/db_tool.py seed --force
```

補足
- `db_tool.py up` は `CREATE EXTENSION vector;` を含みます。権限エラーの場合は、DB 側で拡張を有効化してから再実行してください。

## Slack: Web API / アプリ作成

前提条件
- Slack ワークスペースの管理者権限（またはアプリ作成権限）

環境変数（.env 例）
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
# Socket Mode を使用する場合（任意）
SLACK_APP_TOKEN=xapp-...
# 既定投稿先（Slack 通知を使う場合は必須）
SLACK_DEFAULT_CHANNEL=C0123456789
```

手順
1) https://api.slack.com/apps から新規アプリ作成（From scratch）
2) OAuth & Permissions
   - Bot Token Scopes の例: `chat:write`, `channels:read`, `groups:read`, `im:read`, `mpim:read`
   - 連携ワークスペースにインストール
3) Events / Interactivity を有効化
   - Interactivity: `POST /slack/interactions`
   - Event Subscriptions: `POST /slack/events`
   - 詳細は `docs/slack-app.md` を参照

ローカル動作確認（現段階の最小確認）
- トークン有効性の確認（Web API `auth.test`）
```
curl -sS -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test | jq
```
- `ok: true` が返れば認証成功。
- 署名検証の一時無効化は `SLACK_ALLOW_UNSIGNED=true`（ローカル専用）を使用。

## 環境変数/シークレット一覧と取得元

- AWS_BEARER_TOKEN_BEDROCK: AWS 管理画面（Bedrock 対応の資格情報）。Bearer/STS 等の運用方針はセキュリティポリシーに従う。
- AWS_REGION: 利用リージョン（例: ap-northeast-1）
- AWS_BEDROCK_MODEL_ID: 利用モデル ID（例は `STRANDS_BEDROCK.md` を参照）
- SAIHAI_API_BASE_URL: Frontend が参照する API base URL（`npm start`/`npm run build` で `src/assets/runtime-config.json` に反映）
- SAIHAI_AUTH_TOKEN: Frontend が付与する開発用 Bearer トークン（任意）
- SAIHAI_LOGIN_TIMEOUT_MS: ログインのタイムアウト時間（ミリ秒、任意）
- SAIHAI_LOG_LEVEL / SAIHAI_LOG_TO_SERVER / SAIHAI_SERVER_LOG_LEVEL: フロントのログ設定（任意）
- DATABASE_URL: AWS PostgreSQL + pgvector の接続文字列
- LOG_LEVEL / LOG_FILE / LOG_HTTP_REQUESTS: Backend のログ設定（任意）
- DEV_LOGIN_PASSWORD: 開発用ログインの共通パスワード（デフォルト `saihai`）
- JWT_SECRET / JWT_TTL_MINUTES: JWT 署名キーと有効期限（分）
- SLACK_BOT_TOKEN / SLACK_SIGNING_SECRET / SLACK_APP_TOKEN（任意）: Slack アプリ管理画面（Basic Information / OAuth & Permissions / Socket Mode）
- SLACK_DEFAULT_CHANNEL: 既定投稿先のチャンネル ID
- SLACK_REQUEST_TTL_SECONDS: 署名検証の許容時間（秒、デフォルト 300）
- SLACK_ALLOW_UNSIGNED: ローカル検証用の署名検証無効化フラグ（`true` のときのみ許可）
- INTERNAL_API_TOKEN: Watchdog の内部実行 API に付与するトークン（未設定の場合は無効）
- EMAIL_PROVIDER / CALENDAR_PROVIDER: 外部アクションのプロバイダ（既定 `mock`）
- EMAIL_DEFAULT_TO / EMAIL_DEFAULT_FROM / CALENDAR_DEFAULT_ATTENDEE / CALENDAR_DEFAULT_TIMEZONE: 外部アクションの既定値（任意）

保存先
- ローカル開発（Backend）: `backend/.env`（または作業ディレクトリの `.env` / リポジトリルートの `.env` のいずれか 1 つ）
- ローカル開発（Frontend）: `SAIHAI_*` は環境変数、または `frontend/.env` / リポジトリルートの `.env`（`frontend/scripts/write-runtime-config.cjs` が読む）
- CI/CD / 本番: GitHub Secrets / AWS Systems Manager Parameter Store など。運用規約に従って安全に保管。

## ローカル動作確認（サマリ）

- AI: `STRANDS_BEDROCK.md` のサンプル実行で応答が得られる
- DB: `db_tool.py up/seed` が通り、pgvector が有効な DB に接続できる
- Slack（任意）: `auth.test` で `ok: true`
- Watchdog: `cd backend && uv run python scripts/watchdog_enqueue.py` → `uv run python scripts/watchdog_worker.py`
- Weekly reports: `cd backend && uv run python scripts/ingest_weekly_reports.py`
- アプリ
  - Backend: `cd backend && uvicorn app.main:app --reload` で `GET /api/health` が `{"status":"ok"}` を返す
  - Frontend: `cd frontend && npm i && npm start` でローカル起動

## ドキュメントの配置/参照

- 配置: `docs/setup.md`（本ファイル）
- 参照: リポジトリの `README.md` からリンク（下部の「Setup / 外部サービス」セクション）
- 関連: `docs/slack-app.md`（Slack App 設計）
- 関連: `docs/aws-setup.md`（PoC / localhost の AWS セットアップ手順）
