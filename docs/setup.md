# セットアップガイド（外部サービス・環境変数・ローカル確認）

本ドキュメントは、SaihAI プロジェクトが利用（または想定）する外部サービスの一覧、セットアップ手順、必要な環境変数、ローカルでの動作確認方法をまとめたものです。

- 対象範囲: AI 推論（AWS Bedrock）、データベース（PostgreSQL + pgvector）、Slack 連携、付随サービス（EventBridge/S3+CloudFront などの運用想定）
- 目的: 新規参加者が迷わずローカル環境構築できること
- 参照: `STRANDS_BEDROCK.md`、`requirement-docs/database-schema.md`

## 外部サービス一覧（カテゴリ別）

- AI（LLM / 埋め込み）
  - AWS Bedrock Runtime（Anthropic Claude 等）
    - 用途: 推論実行（Strands Agent 経由で Bedrock を呼び出し）
- データベース
  - PostgreSQL + pgvector
    - 用途: コアデータ管理（users/projects 等）、ベクトル検索（週報ベクトル）、LangGraph のチェックポイント保存
- チャット/通知
  - Slack（Web API / 将来: Events/Interactive）
    - 用途: 通知・介入・承認（Block Kit）
- 運用想定（将来）
  - Amazon EventBridge（Watchdog トリガー）
  - S3 + CloudFront（フロントエンド配信）

## AI: AWS Bedrock のセットアップ

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
- `backend` 側で Python を利用する場合: `python-dotenv` を利用し `.env` を読み込み
- Strands Agent を用いた最小サンプルは `STRANDS_BEDROCK.md` を参照
  - 事前に `pip install strands-agents python-dotenv` を実行
  - `.env` に上記 3 つの環境変数を定義

ローカル動作確認
- `STRANDS_BEDROCK.md` のサンプルコードを実行し、日本語プロンプトに対する応答が返ることを確認

参考
- `STRANDS_BEDROCK.md` 内「トラブルシュート」を参照（リージョン誤り・トークン無効など）

## DB: PostgreSQL + pgvector のセットアップ

前提条件
- Docker が利用可能（推奨）

環境変数（.env 例）
```
# いずれか（アプリ側が DATABASE_URL を読む実装になった場合を想定）
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/saih_ai
# または分割指定
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=postgres
PGDATABASE=saih_ai
```

手順（ローカル PostgreSQL コンテナ）
1) コンテナ起動（pgvector 拡張入りイメージを利用）
```
docker run --name saihai-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=saih_ai -p 5432:5432 -d ankane/pgvector:latest
```
2) マイグレーション実行（backend の DB ツール）
```
cd backend
python scripts/db_tool.py up
python scripts/db_tool.py seed --force
```
3) psql で接続し拡張とスキーマ適用（手動確認）
```
# 拡張有効化
psql postgresql://postgres:postgres@localhost:5432/saih_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"
# スキーマは backend/migrations/0001_init.up.sql と一致することを確認
```

ローカル動作確認
- `SELECT 1;` が通ること
- `CREATE EXTENSION vector;` が成功済みであること
- `requirement-docs/database-schema.md` のサンプル INSERT が成功すること

補足
- `DATABASE_URL` を設定しない場合、SQLite (`sqlite:///./saihai.db`) で起動します。
- `backend/scripts/db_tool.py seed` は `backend/app/data/seed.json` を DB に投入し、`/api/v1/projects` と `/api/v1/members` が DB 由来になります。

## Slack: Web API / アプリ作成

前提条件
- Slack ワークスペースの管理者権限（またはアプリ作成権限）

環境変数（.env 例）
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
# Socket Mode を使用する場合（任意）
SLACK_APP_TOKEN=xapp-...
# 既定投稿先など（任意）
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
- DATABASE_URL または PG* 系: ローカル PostgreSQL の接続文字列/情報
- DEV_LOGIN_PASSWORD: 開発用ログインの共通パスワード（デフォルト `saihai`）
- JWT_SECRET / JWT_TTL_MINUTES: JWT 署名キーと有効期限（分）
- SLACK_BOT_TOKEN / SLACK_SIGNING_SECRET / SLACK_APP_TOKEN: Slack アプリ管理画面（Basic Information / OAuth & Permissions / Socket Mode）
- SLACK_ALLOW_UNSIGNED: ローカル検証用の署名検証無効化フラグ（`true` のときのみ許可）
- INTERNAL_API_TOKEN: Watchdog の内部実行 API に付与するトークン（未設定の場合は無効）

保存先
- ローカル開発: リポジトリ直下に `.env`（バックエンドの `.env` 読み込みに準拠）
- CI/CD / 本番: GitHub Secrets / AWS Systems Manager Parameter Store など。運用規約に従って安全に保管。

## ローカル動作確認（サマリ）

- AI: `STRANDS_BEDROCK.md` のサンプル実行で応答が得られる
- DB: Docker の PostgreSQL に接続でき、`vector` 拡張とスキーマが適用できる
- Slack: `auth.test` で `ok: true`
- Watchdog: `cd backend && python scripts/watchdog_enqueue.py` → `python scripts/watchdog_worker.py`
- アプリ
  - Backend: `cd backend && uvicorn app.main:app --reload` で `GET /api/health` が `{"status":"ok"}` を返す
  - Frontend: `cd frontend && npm i && npm start` でローカル起動（運用は S3+CloudFront を想定）

## ドキュメントの配置/参照

- 配置: `docs/setup.md`（本ファイル）
- 参照: リポジトリの `README.md` からリンク（下部の「Setup / 外部サービス」セクション）
- 関連: `docs/slack-app.md`（Slack App 設計）
- 関連: `docs/aws-setup.md`（staging の AWS リソース構築手順）
