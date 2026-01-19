# AWS デプロイ手順（PoC / staging・開発メンバーのみ）

PoC の staging は **開発メンバーのみがアクセス**できればよく、可用性やスケールは優先しません。  
そのため **ALB / ECS / CloudFront は使わず**、最小構成（EC2 1台）で構築します。

## 目的（到達状態）

- AWS 上に staging 環境（Frontend + Backend）があり、開発メンバーだけがアクセスできる
- Backend が `GET /api/health` を返す
- Frontend から Backend を呼べる（CORS で詰まらない）
- Bedrock / PostgreSQL+pgvector へ接続できる（外部依存は既存手順を利用）

## 採用構成（最小）

- **EC2 1台**（Public）
  - Nginx: Frontend の静的配信 + `/api/*` を Backend へリバースプロキシ
  - Backend: FastAPI（uvicorn）
- **RDS/Aurora(PostgreSQL+pgvector)** + **Bedrock**: 既存手順 `docs/aws-setup.md` を利用
- **アクセス制限**: Security Group で **開発メンバーのグローバルIP(/32) のみ**許可（PoC 前提）

この構成では Frontend と Backend が同一オリジン（同一ホスト）になるため、Backend の CORS 設定を触らずに動きます。

## 前提

- `docs/aws-setup.md` を完了しており、以下が揃っている
  - `DATABASE_URL`
  - `AWS_REGION`, `AWS_BEDROCK_MODEL_ID`, `AWS_BEDROCK_INFERENCE_PROFILE_ID`（任意）, `AWS_BEARER_TOKEN_BEDROCK`
- 開発メンバーのアクセス元グローバルIPが把握できる（固定IPが無い場合は VPN / Client VPN 等を検討）

---

## 1. DB / Bedrock（必須）

先に `docs/aws-setup.md` を実施してください（PoC 最小: Bedrock + PostgreSQL+pgvector）。

以降の手順では DB の Security Group に「EC2 からの 5432」を許可します。

---

## 2. EC2 を作成（staging）

### 2.1 セキュリティグループ（重要）

Inbound は **開発メンバーのIPだけ**にします。

- HTTP: `80` → `<dev_ip_1>/32`, `<dev_ip_2>/32`, ...
- （任意）HTTPS: `443` → `<dev_ip_*>/32`（PoC では必須ではありません）
- （任意）SSH: `22` → `<dev_ip_*>/32`（可能なら使わず、SSM 推奨）

Outbound は既定のままでOK（Bedrock/DB への接続に必要）。

### 2.2 EC2 インスタンス

コンソールで以下を作成します。

- AMI: Amazon Linux 2023（推奨）または Ubuntu
- Instance type: `t3.small` など（PoC は小さめから）
- Subnet: Public subnet
- Public IP: 有効
- Security Group: 2.1 の SG を付与

（任意・推奨）固定のURLが欲しい場合:
- Elastic IP を確保し、EC2 に関連付け

### 2.3 IAM ロール（推奨）

PoC でも最低限、以下を付与します。

- SSM で接続する場合: `AmazonSSMManagedInstanceCore`
- Bedrock を呼ぶ場合: 運用方針に従い必要権限（PoC は一時的に広めでも可）

---

## 3. EC2 にアプリを配置して起動する

ここでは「EC2 内でビルドして起動」する最短手順を記載します（Docker は必須ではありません）。

補足:
- ホストに Node/uv を入れたくない場合は、Backend/Frontend を Docker 化して `docker compose up` で起動する運用がより簡単です（PoC 方針に合わせて採用してください）。

### 3.1 依存のインストール（例）

EC2 にログインし、Node.js / uv / Nginx をインストールします（OS によりコマンドは異なります）。

- Node.js（Frontend build 用）
- `uv`（Backend 依存解決用）
- Nginx（静的配信 + リバプロ）

### 3.2 リポジトリ配置

```bash
sudo mkdir -p /opt/saihai
sudo chown -R "$(whoami)":"$(whoami)" /opt/saihai
cd /opt/saihai
git clone <YOUR_REPO_URL> app
cd app
```

### 3.3 環境変数（Backend）

EC2 上で `.env` を用意します（例: `/opt/saihai/app/.env`）。  
Backend は `backend/app/env.py` により、カレント or リポジトリルートの `.env` を読みます。

最低限（例）:

```bash
DATABASE_URL=postgresql+psycopg://<DbUser>:<DbPassword>@<DbEndpoint>:5432/<DbName>?sslmode=require
JWT_SECRET=CHANGE_ME_TO_RANDOM
DEV_LOGIN_PASSWORD=CHANGE_ME
LOG_LEVEL=INFO
LOG_HTTP_REQUESTS=1

AWS_REGION=ap-northeast-1
AWS_BEDROCK_MODEL_ID=...
AWS_BEDROCK_INFERENCE_PROFILE_ID=...
AWS_BEARER_TOKEN_BEDROCK=...
```

### 3.4 DB 初期化（migration / seed）

```bash
cd /opt/saihai/app/backend
uv sync
uv run python scripts/db_tool.py up
uv run python scripts/db_tool.py seed --force
```

### 3.5 Backend 起動（systemd 推奨）

まずは手動起動で疎通します。

```bash
cd /opt/saihai/app/backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

疎通:

```bash
curl -sS http://127.0.0.1:8000/api/health
```

systemd 化（例）:

1) `which uv` で uv のフルパスを確認（例: `/home/ec2-user/.local/bin/uv`）
2) `/etc/systemd/system/saihai-backend.service` を作成

```ini
[Unit]
Description=SaihAI Backend (FastAPI)
After=network.target

[Service]
WorkingDirectory=/opt/saihai/app/backend
EnvironmentFile=/opt/saihai/app/.env
ExecStart=<PATH_TO_UV> run uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

3) 反映

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now saihai-backend
sudo systemctl status saihai-backend
```

### 3.6 Frontend build

staging は同一ホスト配下で `/api/*` を Nginx が Backend に転送するため、Frontend の API base URL は相対パスが最短です。

```bash
cd /opt/saihai/app/frontend
npm ci
SAIHAI_API_BASE_URL=/api/v1 npm run build
```

ビルド成果物は `frontend/dist/frontend/browser/` に出力されます。

### 3.7 Nginx 設定（静的配信 + リバプロ）

Nginx の設定例（概略）:

- `/` は `frontend/dist/frontend/browser/` を配信
- `/api/` は `http://127.0.0.1:8000` にプロキシ
- SPA 対応で `try_files ... /index.html`

例（`/etc/nginx/conf.d/saihai.conf`）:

```nginx
server {
  listen 80;

  root /opt/saihai/app/frontend/dist/frontend/browser;
  index index.html;

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

反映:

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

### 3.8 動作確認（外部）

- Frontend: `http://<EC2_PUBLIC_IP_OR_EIP>/dashboard`
- Backend: `http://<EC2_PUBLIC_IP_OR_EIP>/api/health`

---

## 4. 更新手順（PoC 運用）

1) EC2 上で `git pull`
2) Frontend: `cd frontend && npm ci && SAIHAI_API_BASE_URL=/api/v1 npm run build`
3) Backend: `cd backend && uv sync`
4) Backend プロセスを再起動（systemd 化している場合は `sudo systemctl restart <service>`）

---

## 5. PoC セキュリティ最小ライン（必須）

- Security Group の `80/443/22` は **開発メンバーのIP(/32) のみ**（`0.0.0.0/0` は禁止）
- `JWT_SECRET` / `DEV_LOGIN_PASSWORD` は必ず変更（PoC でも漏洩前提で短命に）
- DB の inbound `5432` は **EC2 の SG からのみ**許可（ローカル接続が必要なら自分のIP(/32)だけ追加）

---

## 6. 片付け（コスト停止）

- EC2 を停止/削除（EIP を使った場合は解放）
- Nginx / ログの保存が必要ならスナップショット等で退避
- RDS/Aurora を停止/削除（スナップショット要否に注意）
