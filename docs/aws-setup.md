# AWS セットアップ手順（PoC / localhost）

本書は、Frontend/Backend を **localhost で起動**しつつ、アプリの機能上必須の AWS 機能（**Bedrock / PostgreSQL+pgvector**）を使える状態にする手順です。

- 必須: AWS Bedrock（AI） / AWS PostgreSQL + pgvector（ベクトルDB）
- 不要（PoCでは作らない）: ALB / CloudFront（配信・負荷分散は後回し）

参照:
- ローカル起動/環境変数: `docs/setup.md`
- Bedrock 疎通サンプル: `STRANDS_BEDROCK.md`

---

## 0. 前提

- AWS アカウントが存在し、Bedrock と RDS/Aurora を利用できる権限がある
- ローカルで Backend/Frontend を起動できる（`bash dev-setup.sh` が完了している）

---

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
