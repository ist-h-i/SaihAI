# AWS リソース構築手順（staging）

本書は `staging` 環境向けに、SaihAI が接続して利用する AWS リソースを **できるだけ手作業を減らして** 構築し、アプリが疎通できる状態にする手順をまとめたものです。

- 参照（ローカル開発/環境変数の概要）: `docs/setup.md`
- 参照（想定アーキテクチャ）: `requirement-docs/app-guideline.md`
- 参照（Slack 設計）: `docs/slack-app.md`
- 参照（Bedrock 呼び出し）: `STRANDS_BEDROCK.md`

---

## Goals（この手順書で到達する状態）

- `staging` に必要な AWS リソースが作成され、アプリ（Backend/Frontend/Worker）が接続できる。
- `CDK（TypeScript）` を中心に、デプロイ順序・取得値（URL/ARN/ID/Endpoint）・アプリ設定（環境変数/GitHub Secrets）が 1 つの流れで追える。
- 構築後の最小動作確認（ヘルスチェック/ログ確認/キュー投入）ができる。

## Non-Goals（本書で扱わない）

- 組織の IAM 権限設計・承認フローの策定
- `production` 向けの手順（本書は `staging` のみ）
- ドメイン取得・WAF・監査ログなどの本格運用設計（必要なら別途）

---

## 前提

- AWS アカウントは存在し、各サービス（ECS/RDS/SQS/EventBridge/S3/CloudFront/Bedrock 等）を利用できる権限がある
- 機密情報の保管先は **GitHub Secrets**（本書では「登録するキー名」を env var 名に揃える）
- IaC 方針は **AWS CDK (TypeScript)**（`docs/tasklist.md` の AWS-002 に沿う）

---

## 0. 事前準備（ローカル）

必要ツール:

- AWS CLI v2（`aws --version`）
- Node.js（CDK 実行用。バージョンは運用に合わせて固定）
- Docker（Backend/Worker のコンテナビルド用）
- jq（任意。出力整形）

推奨の環境変数（ローカルで CDK/CLI を叩く場合）:

```bash
export STAGE=staging
export AWS_REGION=ap-northeast-1
export AWS_ACCOUNT_ID="<YOUR_AWS_ACCOUNT_ID>"
```

---

## 1. Bedrock（モデル有効化）

Bedrock は「リソース作成」より先に、**アカウントで対象モデルが有効**になっている必要があります。

1) AWS Console → Bedrock → Model access で、利用するモデル（例: Claude / Titan Embeddings）を有効化  
2) `AWS_REGION` がモデル提供リージョンと一致していることを確認

取得すべき情報:

- `AWS_REGION`
- `AWS_BEDROCK_MODEL_ID`（例: `global.anthropic.claude-haiku-4-5-20251001-v1:0`）
- `AWS_BEARER_TOKEN_BEDROCK`（`STRANDS_BEDROCK.md` の前提に合わせる）

アプリ側の設定（GitHub Secrets / env var）:

- `AWS_REGION`
- `AWS_BEDROCK_MODEL_ID`
- `AWS_BEARER_TOKEN_BEDROCK`

動作確認:

- ローカルで `STRANDS_BEDROCK.md` の最小サンプルが応答すること

---

## 2. CDK（staging）デプロイ手順

> このリポジトリは IaC を `infra/` 配下に置く方針ですが、現時点で `infra/` が未整備の場合があります。  
> 本書は「CDK 中心で運用するための標準手順」をまとめています（手作業の手順は最後に最小限だけ記載）。

### 2.1 `infra/` が未作成の場合（最小セットアップ）

```bash
mkdir -p infra
cd infra
npx aws-cdk@2 init app --language typescript
```

以降、`infra/` に staging 用スタックを作成し、`cdk deploy` で構築します。

### 2.2 Bootstrap（初回のみ）

```bash
cd infra
npx cdk bootstrap "aws://${AWS_ACCOUNT_ID}/${AWS_REGION}"
```

### 2.3 デプロイ順序（推奨）

1) ネットワーク（VPC/SG/サブネット）
2) DB（Aurora PostgreSQL + pgvector）
3) Backend（ECS/Fargate + ALB）
4) Frontend（S3 + CloudFront）
5) Watchdog（EventBridge + SQS + Worker）
6) 監視（CloudWatch Logs / 最低限アラーム）

### 2.4 取得値（Outputs）の見方

CDK の `Outputs` は `cdk deploy` の最後に表示されます。例:

```text
Outputs:
  SaihaiStagingBackendStack.AlbUrl = http://xxxx.ap-northeast-1.elb.amazonaws.com
  SaihaiStagingFrontendStack.CloudFrontUrl = https://dxxxx.cloudfront.net
  SaihaiStagingDatabaseStack.DbEndpoint = saihai-staging.cluster-xxxx.ap-northeast-1.rds.amazonaws.com
```

CLI で確認する場合（CloudFormation Outputs）:

```bash
aws cloudformation describe-stacks \
  --stack-name "<STACK_NAME>" \
  --query "Stacks[0].Outputs" \
  --output table
```

---

## 3. サービス別手順（構築 → 取得値 → 設定 → 動作確認）

### 3.1 ネットワーク（VPC/SG/サブネット）

作成/更新方法:

- CDK で VPC（public/private）と、ECS/RDS 用の Security Group を定義

生成されるアウトプット（取得すべき値）:

- `VpcId`
- `AlbSecurityGroupId`
- `AppSecurityGroupId`
- `DbSecurityGroupId`

アプリ側の設定:

- なし（後続スタックが参照）

動作確認:

- `aws ec2 describe-vpcs --vpc-ids <VpcId>` が成功する

---

### 3.2 DB（Aurora PostgreSQL + pgvector）

作成/更新方法:

- CDK で Aurora PostgreSQL クラスタを作成（staging）
- `pgvector` は DB 側で `CREATE EXTENSION vector;` が必要（初回のみ）

生成されるアウトプット（取得すべき値）:

- `DbEndpoint`（writer endpoint）
- `DbPort`（通常 5432）
- `DbName`
- `DbUser`
- `DbPassword`（GitHub Secrets で管理する場合）

アプリ側の設定（GitHub Secrets / env var）:

- `DATABASE_URL`（推奨。例: `postgresql://<DbUser>:<DbPassword>@<DbEndpoint>:5432/<DbName>`）
  - 分割指定にする場合は `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE` を登録

動作確認（推奨: ECS Exec で実行）:

1) Backend/Worker のタスクに `psql` が入っている前提で接続し、拡張を有効化
   - `CREATE EXTENSION IF NOT EXISTS vector;`
2) `backend/migrations/` と同等のスキーマが適用できることを確認

補足（ローカルから接続したい場合）:

- DB をパブリックにせずに接続するには、SSM 経由の踏み台（EC2）または VPN/DirectConnect 等の経路が必要です。

---

### 3.3 Backend（ECS/Fargate + ALB）

作成/更新方法:

- CDK で以下を作成
  - ECR（Backend イメージ格納）
  - ECS Cluster / TaskDefinition / Service（Fargate）
  - ALB（/api/health を疎通確認に利用）

生成されるアウトプット（取得すべき値）:

- `AlbUrl`（例: `http://xxxx.elb.amazonaws.com`）
- `BackendServiceName` / `BackendClusterName`（ECS Exec 用）
- `BackendLogGroupName`（CloudWatch Logs）

アプリ側の設定（GitHub Secrets / env var）:

- Bedrock: `AWS_REGION` / `AWS_BEDROCK_MODEL_ID` / `AWS_BEARER_TOKEN_BEDROCK`
- DB: `DATABASE_URL`（または `PG*`）
- 認証: `JWT_SECRET` / `JWT_TTL_MINUTES` / `DEV_LOGIN_PASSWORD`
- Slack: `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` / `SLACK_DEFAULT_CHANNEL`
- 内部 API（Watchdog）: `INTERNAL_API_TOKEN`（未設定なら無効）

動作確認:

- `curl -sS "<AlbUrl>/api/health"` が `{"status":"ok"}` を返す（パスは backend 実装に合わせる）
- CloudWatch Logs に起動ログが出る

---

### 3.4 Frontend（S3 + CloudFront）

作成/更新方法:

- CDK で S3 バケット + CloudFront Distribution を作成（SPA 配信）
- Frontend は `frontend/src/assets/runtime-config.json` を参照して API の URL を決める（詳細: `frontend/README.md`）

生成されるアウトプット（取得すべき値）:

- `CloudFrontUrl`（例: `https://dxxxx.cloudfront.net`）
- `FrontendBucketName`

アプリ側の設定（GitHub Secrets / env var）:

- `SAIHAI_API_BASE_URL`（例: `<AlbUrl>/api/v1`）
- `SAIHAI_AUTH_TOKEN`（任意。開発用 Bearer）

動作確認:

- `<CloudFrontUrl>/dashboard` が表示される（初回はキャッシュ反映まで数分かかることがあります）

---

### 3.5 Watchdog（EventBridge + SQS + Worker）

作成/更新方法:

- CDK で以下を作成
  - EventBridge Rule（定期実行）
  - SQS Queue（ジョブ投入）
  - Worker（ECS サービス or スケールドタスク）: キューをポーリングして処理

生成されるアウトプット（取得すべき値）:

- `WatchdogQueueUrl`
- `WatchdogQueueArn`
- `WatchdogRuleArn`
- `WorkerServiceName` / `WorkerClusterName`

アプリ側の設定（GitHub Secrets / env var）:

- Worker が Backend と同等の env（DB/Bedrock 等）を参照できること
- 内部 API を叩く構成の場合は `INTERNAL_API_TOKEN` を一致させる

動作確認（最小）:

```bash
aws sqs send-message --queue-url "<WatchdogQueueUrl>" --message-body '{"kind":"watchdog","stage":"staging"}'
```

- Worker の CloudWatch Logs に「受信→処理」が出ること

---

### 3.6 監視（CloudWatch Logs / 最低限アラーム）

作成/更新方法:

- CDK で LogGroup（Backend/Worker）を作成し、必要ならアラームを追加
  - 例: ALB 5xx、SQS の ApproximateAgeOfOldestMessage、ECS タスク異常終了

生成されるアウトプット（取得すべき値）:

- `BackendLogGroupName`
- `WorkerLogGroupName`

動作確認:

- CloudWatch Logs で、リクエスト実行に応じてログが増える

---

## 4. GitHub Secrets（staging）登録一覧

GitHub のリポジトリ設定で、`staging` 用の Secrets（推奨: GitHub Environments の `staging`）に登録します。

### 4.1 AWS（Bedrock）

- `AWS_REGION`
- `AWS_BEDROCK_MODEL_ID`
- `AWS_BEARER_TOKEN_BEDROCK`

### 4.2 DB

- `DATABASE_URL`（または `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE`）

### 4.3 Backend 認証/開発用

- `JWT_SECRET`
- `JWT_TTL_MINUTES`
- `DEV_LOGIN_PASSWORD`

### 4.4 Slack

- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_DEFAULT_CHANNEL`
- `SLACK_APP_TOKEN`（Socket Mode を使う場合のみ）

### 4.5 Watchdog（内部 API）

- `INTERNAL_API_TOKEN`（利用する場合のみ）

### 4.6 Frontend

- `SAIHAI_API_BASE_URL`
- `SAIHAI_AUTH_TOKEN`（任意）

---

## 5. 構築後チェックリスト（staging）

- Backend: `GET <AlbUrl>/api/health` が `ok`
- Frontend: `<CloudFrontUrl>/dashboard` が表示
- DB: `vector` 拡張が有効、スキーマ適用済み
- Watchdog: SQS に投入 → Worker が処理
- Logs: CloudWatch Logs で Backend/Worker のログが追える

