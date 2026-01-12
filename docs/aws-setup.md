# AWS リソース構築手順（staging）

本書は、SaihAI の staging 環境で必要となる AWS リソース（**Bedrock / PostgreSQL+pgvector**）を最小構成で用意し、取得値を環境変数・GitHub Secrets に反映するための手順です。PoC / localhost での接続確認もこの手順の範囲に含みます（ALB/CloudFront は後回し）。

- 必須: AWS Bedrock（AI） / AWS PostgreSQL + pgvector（ベクトルDB）
- 任意: ALB / CloudFront（配信・負荷分散は後回し）

参照:
- ローカル起動/環境変数: `docs/setup.md`
- Bedrock 疎通サンプル: `STRANDS_BEDROCK.md`
- AWS へ配信（Frontend/Backend）: `docs/aws-deploy.md`

## Goals（この手順書で到達する状態）

- Bedrock と PostgreSQL + pgvector を staging で利用できる
- 取得値（URL/ARN/ID/Endpoint）を環境変数/Secrets に反映できる
- `SAIHAI_API_BASE_URL` を含むフロント/バックエンド設定が確定している
- 最低限の疎通確認（Bedrock/DB）が行える

## 前提

- AWS アカウントが存在し、Bedrock と RDS/Aurora を利用できる権限がある
- ローカルで Backend/Frontend を起動できる（`bash dev-setup.sh` が完了している）

## コンソール（staging）セットアップ手順（全体の流れ）

1) Bedrock の Model access を有効化し、必要な値を控える
2) Aurora PostgreSQL（または RDS for PostgreSQL）を作成し、接続経路を用意する
3) 取得値（URL/ARN/ID/Endpoint）を整理して環境変数/Secrets に対応付ける
4) `backend/.env` を設定し、マイグレーション/seed を実行する
5) ローカルまたは staging で疎通確認を行う

## 取得値（URL/ARN/ID/Endpoint）の控え方

取得値は表（例: スプレッドシート）で管理し、環境変数/Secrets への対応を明確にします。

- Bedrock: `AWS_REGION` / `AWS_BEDROCK_MODEL_ID` / `AWS_BEARER_TOKEN_BEDROCK`
- DB: `DbEndpoint` / `DbName` / `DbUser` / `DbPassword` → `DATABASE_URL`
- API: `SAIHAI_API_BASE_URL`（staging の API base URL）

## サービス別手順（構築 → 取得値 → 設定 → 動作確認）

## 1. Bedrock（モデル有効化）

1) AWS Console → Bedrock → Model access で、利用するモデル（例: Claude）を有効化
2) `AWS_REGION` がモデル提供リージョンと一致していることを確認

取得して控える値（`backend/.env` に設定します）:

- `AWS_REGION`
- `AWS_BEDROCK_MODEL_ID`
- `AWS_BEARER_TOKEN_BEDROCK`

動作確認（任意）:

- `STRANDS_BEDROCK.md` の最小サンプルが応答すること

---

## 2. ベクトルDB（AWS PostgreSQL + pgvector）

RDS → Create database で **Aurora PostgreSQL**（または **RDS for PostgreSQL**）を作成します。

### 2.1 接続方法（PoC 推奨）

最短で進める場合は、以下の構成にします（PoC 限定）:

- Public access: `Yes`
- Security Group（DB）: inbound `5432` を **自分のグローバル IP（/32）** のみに制限

補足: DB の SG が `default` のままだと、通常は「SG 自身からの通信のみ許可」になっていてローカルから接続できません（`Operation timed out` になりやすい）ので、PoC 用に SG を作って RDS に付け替えるのが確実です。

1) VPC → Security Groups で SG を作成（例: `saihai-db-dev-sg`、VPC は DB と同じ）
   - Inbound: PostgreSQL / TCP 5432 / Source: `<あなたのIP>/32`
2) RDS → Databases → 対象 DB → Modify → Connectivity で、VPC security groups に 1) の SG を追加（不要なら `default` を外す）
   - Apply immediately（PoC 推奨）

接続テスト（ローカル）:

```bash
nc -vz <DbEndpoint> 5432
```

- `succeeded` になれば疎通OK
- `Operation timed out` の場合は、DB の Public access / SG の許可元IP / 自宅・社内ネットワークの制限（Outbound 5432 ブロック等）を見直してください

補足（IP確認）:

```bash
curl https://checkip.amazonaws.com
```

Public access を使えない場合は、SSM 踏み台 / VPN 等の経路を用意してください（この手順書では詳細は扱いません）。

### 2.2 pgvector 有効化

DB に接続して、以下を実行します（RDS Query Editor v2 / `psql` など）。

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2.3 取得して控える値

- `DbEndpoint`（writer endpoint）
- `DbPort`（通常 5432）
- `DbName`
- `DbUser`
- `DbPassword`

---

## 3. ローカル設定（必須）

### 3.1 `backend/.env` を設定

`backend/.env` に以下を設定します（例）。

```bash
DATABASE_URL=postgresql+psycopg://<DbUser>:<DbPassword>@<DbEndpoint>:5432/<DbName>?sslmode=require
AWS_REGION=ap-northeast-1
AWS_BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
AWS_BEARER_TOKEN_BEDROCK=your-api-key-here
```

### 3.2 マイグレーション/seed

```bash
cd backend
uv run python scripts/db_tool.py up
uv run python scripts/db_tool.py seed --force
```

補足:
- `db_tool.py up` は `CREATE EXTENSION vector;` を含みます。権限エラーの場合は、DB 側で拡張を有効化してから再実行してください。

---

## 4. ローカル起動

```bash
bash dev-start.sh
```

動作確認:

- Backend: `http://localhost:8000/api/health`
- Frontend: `http://localhost:4200/`

ポートが使用中の場合、`dev-start` が `8001` / `4201` に自動で切り替えます（表示される URL を参照してください）。

---

## GitHub Secrets（staging）登録一覧

- `AWS_REGION`: Bedrock/RDS の利用リージョン
- `AWS_BEDROCK_MODEL_ID`: 利用モデル ID
- `AWS_BEARER_TOKEN_BEDROCK`: Bedrock 利用の資格情報（運用ポリシーに従う）
- `DATABASE_URL`: PostgreSQL + pgvector の接続文字列
- `SAIHAI_API_BASE_URL`: Frontend が参照する API base URL

## 構築後チェックリスト（staging）

- [ ] Bedrock の Model access が有効化されている
- [ ] `DATABASE_URL` で DB に接続でき、`db_tool.py up/seed` が通る
- [ ] `STRANDS_BEDROCK.md` のサンプルが応答する
- [ ] `SAIHAI_API_BASE_URL` が正しく設定され、`/api/health` が確認できる
