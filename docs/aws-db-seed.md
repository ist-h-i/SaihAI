# AWS DB 初期データ準備・投入手順（PoC / staging）

AWS にデプロイ済みの環境で、DB が空の状態から **アプリ利用に必要な初期データ** を投入する手順です。

## 前提

- DB は PostgreSQL + pgvector（RDS/Aurora）
- `backend/.env` に `DATABASE_URL` が設定済み
- 既存の DB ツールを利用: `backend/scripts/db_tool.py`
- ログインパスワードは DB ではなく環境変数で判定  
  - `DEV_LOGIN_PASSWORD`（未設定の場合のデフォルトは `saihai`）

## 登録するデータ（何を入れるか）

1) アプリユーザ（ログイン用）

- `users` テーブルに `user_id` が存在することが必須
- パスワードは DB に保存しない（`DEV_LOGIN_PASSWORD` で判定）
- 登録対象ユーザ:
  - `inoue` / `saihai`
  - `yumoto` / `saihai`
  - `hashira` / `saihai`

2) エンジニア（メンバー）/ プロジェクト / その他のアプリ必須データ

- ソース: `backend/app/data/seed.json`
- `db_tool.py seed` で以下のテーブルへ投入される  
  - `projects`, `users`, `user_profiles`, `user_skills`, `weekly_reports`
  - `assignments`, `assignment_patterns`
  - `ai_analysis_results`, `ai_strategy_proposals`, `autonomous_actions`
  - `project_health_snapshots`

補足:
- `users` は **ログインユーザとメンバーが共通テーブル**（現状の仕様）
- `user_id` / `project_id` は `VARCHAR(10)` のため 10 文字以内

## データ準備（seed.json の編集）

`backend/app/data/seed.json` を編集して、プロジェクト/メンバーの初期データを整えます。  
現状は **本番デモ想定のデータを反映済み（プロジェクト3件 / メンバー6名）** です。

### 現在の seed.json

```json
{
  "projects": [
    {
      "id": "ec",
      "name": "ECリニューアル (炎上)",
      "budget": 200,
      "requiredSkills": ["Java", "Leadership", "Legacy", "Risk"]
    },
    {
      "id": "hr",
      "name": "HRシステム保守",
      "budget": 120,
      "requiredSkills": ["Java", "Ops", "Stability"]
    },
    {
      "id": "ai",
      "name": "新規AI開発PoC",
      "budget": 180,
      "requiredSkills": ["Python", "Cloud", "ML"]
    }
  ],
  "members": [
    {
      "id": "watanabe",
      "name": "渡辺 救",
      "cost": 90,
      "availability": 90,
      "skills": ["TechLead", "Java", "Incident", "Leadership"],
      "notes": "面談: 立て直し経験が豊富で即応可。体調良好。"
    },
    {
      "id": "tanaka",
      "name": "田中 未来",
      "cost": 95,
      "availability": 70,
      "skills": ["Senior", "Java", "Legacy", "PM"],
      "notes": "週報: 疲労が抜けず腰痛も再発。レガシー案件に飽きている。"
    },
    {
      "id": "sato",
      "name": "佐藤 健太",
      "cost": 60,
      "availability": 100,
      "skills": ["Junior", "Java", "Go", "Backend"],
      "notes": "週報: 伸びしろを感じており新領域に挑戦したい。育成枠希望。"
    },
    {
      "id": "saionji",
      "name": "西園寺 豪",
      "cost": 150,
      "availability": 50,
      "skills": ["CTO", "Architecture", "Security", "Strategy"],
      "notes": "面談: 高単価だが短期で成果を約束。"
    },
    {
      "id": "genda",
      "name": "源田 剛",
      "cost": 88,
      "availability": 80,
      "skills": ["Lead", "Java", "Ops", "Delivery"],
      "notes": "面談: 対人トラブルの噂があり、以前の現場で強い叱責が問題化。"
    },
    {
      "id": "suzuki",
      "name": "鈴木 一郎",
      "cost": 85,
      "availability": 60,
      "skills": ["PM", "Risk", "Java", "Process"],
      "notes": "面談: 育児のため週1の夜間稼働のみ。顧問として参加希望。"
    }
  ]
}
```

## データ登録方法（AWS DB への投入）

### 1. マイグレーション適用

```bash
cd backend
uv run python scripts/db_tool.py up
```

### 2. seed データ投入

```bash
cd backend
uv run python scripts/db_tool.py seed --force
```

補足:
- DB が空なら `--force` は不要（安全に再投入したいときだけ利用）

### 3. アプリユーザの登録（SQL）

`users` にログイン用ユーザを追加します（`psql` / RDS Query Editor v2）。

```sql
INSERT INTO users (user_id, name, role, skill_level, unit_price, can_overtime, career_aspiration)
VALUES
  ('inoue', 'Inoue', 'Admin', 5, 0, true, 'login user'),
  ('yumoto', 'Yumoto', 'Admin', 5, 0, true, 'login user'),
  ('hashira', 'Hashira', 'Admin', 5, 0, true, 'login user')
ON CONFLICT (user_id) DO UPDATE
SET name = EXCLUDED.name,
    role = EXCLUDED.role,
    skill_level = EXCLUDED.skill_level,
    unit_price = EXCLUDED.unit_price,
    can_overtime = EXCLUDED.can_overtime,
    career_aspiration = EXCLUDED.career_aspiration;
```

補足:
- ログインは `DEV_LOGIN_PASSWORD` のみで判定されるため、DB にパスワードは不要
- `users` は `/members` にも出るため、必要であれば role/notes で識別する

## 投入後の確認

```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM projects;
SELECT COUNT(*) FROM assignments;
```

API で確認する場合（要ログイン）:

- `GET /api/v1/projects`
- `GET /api/v1/members`
