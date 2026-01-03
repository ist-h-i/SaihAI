# タスクリスト（SaihAI 完成まで） Issue #11

本書は、リポジトリ内の要件/設計/計画ドキュメントと現状実装（`main` 相当）を突き合わせ、**「アプリケーション完成」までに必要なタスク**を網羅的に列挙したものです。

- 出力の分類: **実装 / インフラ構築（AWS） / 外部API連携**
- “主要画面” は **現状の画面一覧（Angular のルーティング）** を正としつつ、要件から見て不足する観点は優先的にタスク化します。

---

## 1. 参照資料一覧（調査対象）

### 1.1 `/docs`（運用・セットアップ）

- `docs/setup.md`（外部サービス/環境変数/ローカル確認）
- `docs/WORKFLOW.md`（ChatOps運用。アプリ要件の一次情報ではないがCI運用前提として参照）
- `docs/coding-guidelines/Angular.md`（Angularコーディング規約）

### 1.2 要件/設計/計画（プロダクト）

- `requirement/functional-requirements.md`（機能要件：UI/UX + Backend/Logic）
- `requirement/initial-display.md`（初期表示・事前分析・Slack/HITLの繋ぎ）
- `requirement/system-prompts.md`（エージェント出力規約/プロンプト）
- `requirement/project-plan.md`（企画書 + 命令書）
- `requirement/data-schema.md`（検証パターン/サンプルプロンプト）
- `requirement-docs/requirement.md`（要件定義）
- `requirement-docs/function-list.md`（機能一覧 + mock受け入れメモ）
- `requirement-docs/app-guideline.md`（技術スタック/採用理由。AWS構成の前提）
- `requirement-docs/database-schema.md`（DBスキーマ/DDL）
- `requirement-docs/human-in-the-loop.md`（HITL設計：承認/監査/冪等性）
- `requirement-docs/response-example.md`（AI応答スキーマ例）
- `requirement-docs/agent-prompts/*.md`（PM/HR/Risk プロンプト）
- `requirement-docs/UI-mock-sample.html`（画面/演出の参考モック）
- `STRANDS_BEDROCK.md`（Bedrock 呼び出し方針の参考）

### 1.3 実装（現状）

- Frontend: `frontend/src/app/app.routes.ts`、`frontend/src/app/pages/*.page.ts`、`frontend/src/app/core/*`
- Backend: `backend/app/main.py`、`backend/app/api/*`、`backend/app/domain/*`、`backend/app/data/*`
- CI/テスト: `.github/workflows/*`、`tests/*`、`playwright.config.js`

---

## 2. 現状実装の棚卸し（要点）

### 2.1 主要画面（現状の画面一覧＝正）

| 画面 | ルート | 実装状況（現状） | 要件上の不足観点（例） |
|---|---|---|---|
| 経営ダッシュボード | `/dashboard` | KPI/人材マップ/アラート風UI（ローカル計算） | 初期表示の“実データ”統合、診断/提案/承認待ちの同期表示 |
| 戦術シミュレーター | `/simulator` | 案件/メンバー選択→`/api/simulate`→A/B/C表示、HITL風オーバーレイ | ドラッグ&ドロップ、要件カバー率、AI議論ログの仕様準拠、承認→外部アクション実行 |
| Genome DB | `/genome` | メンバー一覧/フィルタ/カード表示（ローカル） | Genome詳細（推移/志向/根拠）、ベクトル検索/類似検索、詳細画面の情報設計 |

> 追加の主要画面候補（要件からの不足抽出）: **ログイン/認証**, **Slack介入の結果確認（履歴/監査）**, **プロジェクト詳細（体制図/アサイン状況）** など。

### 2.2 Backend API（現状）

- `GET /api/health`（ヘルス）
- `GET /api/projects` / `GET /api/members`（seed.json返却）
- `POST /api/simulate`（ルールベースでパターン/スコア/3プラン生成）
- `GET/POST /api/v1/...`（KPI/alerts/simulations/plans/approvals/messages などが **メモリ保持のモック実装**）

### 2.3 外部サービス（現状）

- Bedrock / DB / Slack の **セットアップ手順ドキュメントは存在**（`docs/setup.md`）するが、アプリ実装としての連携は未整備。

---

## 3. タスク運用基準（最小基準）

### 3.1 優先度（Priority）

- **P0**: 「完成の最低条件」を満たすためのブロッカー（主要画面/認証/主要API疎通/AI応答生成）
- **P1**: Betaとして要件の核（Slack/HITL/Watchdog/永続化）に到達するために必要
- **P2**: 仕上げ・拡張（性能/演出/追加連携など）。ただし重大な不足を埋める場合はP1に繰り上げ

### 3.2 見積り粒度（Size）

- **S**: 半日〜1日
- **M**: 2〜5日
- **L**: 1〜2週（複数コンポーネント横断）

### 3.3 マイルストーン（Milestone）

- **M0（設計確定）**: 主要画面/主要エンドポイント/認証方式/AI応答スキーマ/デプロイ形態を確定
- **M1（MVP）**: 主要画面が実データで動き、認証込みの主要API疎通ができ、AIが構造化レスポンスを生成できる
- **M2（Beta）**: Slack通知・承認（HITL）・Watchdog（自動起動）・永続化/冪等性が通る
- **M3（Release）**: AWS上での本番形に寄せ、非機能（運用可能な最低ライン）を満たす

---

## 4. “完成”の最低条件（M1）をタスク化するための完了条件

### 4.1 主要画面の完成（M1）

- `/dashboard`: 初期表示で「アラート/診断/提案/承認待ち」を**バックエンド集約API**から取得して描画できる
- `/simulator`: シミュレーション→3プラン表示→（最低限）**承認フロー**まで到達できる（外部実行はモックでも可、ただしHITLの状態遷移が成立）
- `/genome`: メンバー詳細（スキル/志向/兆候/根拠）を**API経由**で参照できる（暫定でもよいが、データモデルはM0で確定）

### 4.2 FE/BE API疎通（認証込み + 主要エンドポイント一式決定）

- 認証方式をM0で決め、M1でフロント/バック双方に実装（少なくとも「未認証アクセスの拒否」が機能）
- 主要エンドポイント（後述の“暫定案”）を **M0で確定→M1で疎通**（最低限のCRUD/シミュレーション/承認）

### 4.3 AIエージェント応答生成（M1）

- `requirement-docs/response-example.md` を基準に、**画面が直接利用できる構造化JSON**を返す
- “どのエンドポイントでLLMを呼ぶか” と “呼ぶ場合の要件（モデル/ストリーミング/ツール/失敗時挙動）” を **エンドポイント単位**で決める（M0）

---

## 5. タスクリスト

### 5.1 実装（Implementation）

| Done | ID | P | Size | MS | Depends | 概要 | 完了条件（成果物/確認方法） |
|---:|---|---|---|---|---|---|---|
| [ ] | IMP-001 | P0 | S | M0 |  | “主要画面”の完成定義を確定 | 本書 4.1 の完成定義をチーム合意し、差分があれば本書を更新 |
| [ ] | IMP-002 | P0 | M | M0 |  | 認証方式の決定（Web） | 選定理由/フロー図/トークン形式/権限（manager等）を `docs/` に明文化（例: `docs/auth.md`） |
| [ ] | IMP-003 | P0 | M | M0 | IMP-002 | 主要エンドポイント一式の確定 | OpenAPI（またはMarkdown）でエンドポイント一覧/req-res/認証要件が固定される |
| [ ] | IMP-004 | P0 | M | M0 | IMP-003 | FE↔BE のAPIクライアント設計 | `frontend` 側のbase URL/認証ヘッダ/エラー方針を環境変数化し、疎通できる |
| [ ] | IMP-005 | P0 | M | M0 |  | DBモデル方針の確定（seed→DB） | `requirement-docs/database-schema.md` を基準に、最小の実装対象テーブルを決定 |
| [ ] | IMP-006 | P0 | L | M1 | IMP-005 | Backend: DB接続 + マイグレーション導入 | ローカルPostgresで起動し、テーブル作成/seed投入/CRUDが通る |
| [ ] | IMP-007 | P0 | M | M1 | IMP-003,IMP-006 | Backend: `/api/v1/projects` `/members` の実装 | DB裏の一覧取得ができ、既存seedの置き換え方針が明確 |
| [ ] | IMP-008 | P0 | L | M1 | IMP-003,IMP-006 | Backend: Dashboard初期表示API | `requirement/initial-display.md` の「初期表示で必要なデータ群」を1回で返す（例: `GET /api/v1/dashboard/initial`） |
| [ ] | IMP-009 | P0 | L | M1 | IMP-004,IMP-008 | Frontend: `/dashboard` を実データ駆動に置換 | KPI/アラート/提案/承認待ちがAPI由来で表示される |
| [ ] | IMP-010 | P0 | L | M1 | IMP-003,IMP-006 | Backend: シミュレーションAPI（評価→プラン生成） | `POST /api/v1/simulations/evaluate` → `POST /api/v1/simulations/{id}/plans/generate` が通る |
| [ ] | IMP-011 | P0 | L | M1 | IMP-004,IMP-010 | Frontend: `/simulator` をv1 APIへ接続 | 実データで評価→3プラン表示→選択（推奨表示）が可能 |
| [ ] | IMP-012 | P0 | M | M1 | IMP-003 | Frontend: “要件カバー率”UIの完成 | requiredSkills 等の要件カバー率が表示される（`function-list.md` の不足観点） |
| [ ] | IMP-013 | P1 | L | M2 | IMP-010 | Frontend: ドラッグ&ドロップ手動シミュレーション | 手動配置→リアルタイム評価（予算/要件/リスク）が成立 |
| [ ] | IMP-014 | P0 | M | M1 | IMP-003 | Frontend: `/genome` の“詳細”情報設計 | 詳細に必要な項目（志向/推移/根拠/検索）を決定しAPIに反映 |
| [ ] | IMP-015 | P0 | L | M1 | IMP-006,IMP-014 | Backend: Genome関連API | `GET /api/v1/members/{id}` 等で詳細が返る（暫定でも型が固い） |
| [ ] | IMP-016 | P0 | M | M1 | IMP-004,IMP-015 | Frontend: `/genome` を実データ駆動に置換 | メンバー詳細がAPI由来で表示/フィルタできる |
| [ ] | IMP-017 | P1 | M | M2 | IMP-006 | “承認待ち状態”の永続化（DB） | 承認依頼→承認/却下→実行ログがDBに残る（監査ログを含む） |
| [ ] | IMP-018 | P1 | M | M2 | IMP-017 | 承認の冪等性/多重実行防止 | `requirement-docs/human-in-the-loop.md` の要件を満たし、二重クリック等で破綻しない |
| [ ] | IMP-019 | P0 | M | M0 | IMP-003 | AI応答スキーマ（画面直結）を確定 | `requirement-docs/response-example.md` を基準に Pydantic/TS 型を整備 |
| [ ] | IMP-020 | P0 | M | M0 | IMP-019 | AI呼び出し要件を“エンドポイント単位”で確定 | 下の「5.4 AIエンドポイント要件表」を埋め、根拠（参照資料/実装）を付与 |
| [ ] | IMP-021 | P0 | L | M1 | IMP-020,EXT-001 | AI: 3プラン生成をLLM化 | 3プラン（推奨/スコア/議論要約）がLLM生成で返る（失敗時フォールバック含む） |
| [ ] | IMP-022 | P1 | L | M2 | IMP-018,EXT-003 | HITL: 介入指示→再計算→再提示 | “Steer”入力で条件を反映し、再度プラン/下書きが更新される |
| [ ] | IMP-023 | P0 | M | M1 | IMP-002,IMP-003 | FE/BE 認証つなぎ込み | FEでログイン→トークン保持→APIが認可される（未認証は拒否） |
| [ ] | IMP-024 | P1 | M | M2 | IMP-010,IMP-017 | 実行（Execute）を非同期化 | 承認後の実行をジョブ化し、状態遷移（pending→executed/failed）が追える |
| [ ] | IMP-025 | P0 | M | M1 | IMP-010,IMP-019 | Backend: 根回し（nemawashi）下書きAPI | `POST /api/v1/plans/{plan_id}/nemawashi/generate` が画面向けの構造で返る |
| [ ] | IMP-026 | P0 | M | M1 | IMP-011,IMP-025 | Frontend: 根回し下書き表示/承認UI | 下書き→承認依頼→承認/却下が画面上で完結する |
| [ ] | IMP-027 | P1 | L | M2 | IMP-006,IMP-020,EXT-001 | LangGraph導入（Orchestrator + Checkpoint） | `interrupt/resume` がDB永続化され、スレッド単位で再開できる |
| [ ] | IMP-028 | P1 | L | M2 | IMP-027,AWS-007 | Shadow Monitoring（Watchdog）処理の実装 | 定期起動で解析→アラート生成→通知候補がDBに蓄積される |
| [ ] | IMP-029 | P2 | M | M3 | IMP-027 | 長時間AI処理の進捗配信（SSE/WS） | FEが進捗/議論ログをストリーミング表示できる |
| [ ] | IMP-030 | P1 | M | M2 | IMP-010 | Backend: 監査ログ（最低限） | 承認/実行/介入の履歴が“誰が/いつ/何を”で追える |
| [ ] | IMP-031 | P1 | M | M2 | IMP-009,IMP-011,IMP-016 | 主要フローのE2E（証跡方針含む） | 主要画面の到達/表示/主要操作が自動テストで担保される |
| [ ] | IMP-032 | P2 | M | M3 |  | CIのビルド/テストを実アプリ向けに更新 | `frontend build`/`backend` の検証をCIに組み込み、破綻を早期検知する |

### 5.2 インフラ構築（AWS）

| Done | ID | P | Size | MS | Depends | 概要 | 完了条件（成果物/確認方法） |
|---:|---|---|---|---|---|---|---|
| [ ] | AWS-001 | P0 | M | M0 |  | AWSデプロイ形態の確定（整合性確認） | `requirement-docs/app-guideline.md`（ECS/Fargate, Aurora, EventBridge, S3/CloudFront）に沿って最終決定 |
| [ ] | AWS-002 | P0 | M | M0 | AWS-001 | IaC方式の決定（Terraform/CDK等） | リポジトリ内にIaCディレクトリ/READMEが作られ、作業手順が確定 |
| [ ] | AWS-003 | P0 | L | M1 | AWS-002 | ネットワーク基盤（VPC/SG/サブネット） | ECS/Aurora/（必要なら）NAT を含む最小構成が作れる |
| [ ] | AWS-004 | P0 | L | M1 | AWS-002,AWS-003 | Aurora PostgreSQL (pgvector) 構築 | 接続情報がSecrets Manager等で管理され、ローカル以外でも疎通できる |
| [ ] | AWS-005 | P0 | L | M1 | AWS-002 | ECS(Fargate) にBackendをデプロイ | `GET /api/health` がALB経由で応答し、環境変数/Secretsが注入される |
| [ ] | AWS-006 | P0 | M | M1 | AWS-002 | S3 + CloudFront にFrontendをデプロイ | `/dashboard` 等がCloudFront経由で表示される（SPA対応含む） |
| [ ] | AWS-007 | P1 | M | M2 | AWS-002 | EventBridge + SQS（Watchdog起動） | 定期起動→キュー投入→Workerが処理する導線が成立 |
| [ ] | AWS-008 | P1 | M | M2 | AWS-005,AWS-007 | Worker実行基盤（ECS or Lambda） | Shadow Monitoring を非同期で回せる（重い処理はECS推奨） |
| [ ] | AWS-009 | P1 | M | M2 | AWS-002 | ログ/メトリクスの最低ライン | CloudWatch Logs/基本アラーム（5xx, キュー滞留, DB接続失敗） |

### 5.3 外部API連携

| Done | ID | P | Size | MS | Depends | 概要 | 完了条件（成果物/確認方法） |
|---:|---|---|---|---|---|---|---|
| [ ] | EXT-001 | P0 | M | M1 |  | AWS Bedrock（LLM）呼び出し基盤 | `docs/setup.md` / `STRANDS_BEDROCK.md` 前提で、BackendからBedrockを呼べる |
| [ ] | EXT-002 | P1 | M | M2 | EXT-001,AWS-004 | 埋め込み（pgvector用）生成 | 週報/ログをembeddingしDBに保存、類似検索が通る（モデルは要選定） |
| [ ] | EXT-003 | P1 | M | M2 |  | Slack App（権限/イベント）設計 | Bot権限・Events/Interactive/署名検証の方針が確定し、手順がdocs化される |
| [ ] | EXT-004 | P1 | L | M2 | EXT-003,IMP-017 | Slack: 通知（Block Kit）送信 | Shadow Monitoring の結果をSlackに通知できる（要約+リンク+承認UI） |
| [ ] | EXT-005 | P1 | L | M2 | EXT-003,IMP-018 | Slack: 承認/却下/介入 受信 | `POST /slack/events` 等で受け、DB更新→再開が成立（署名/リプレイ対策含む） |
| [ ] | EXT-006 | P2 | L | M3 | IMP-024 | 外部アクション（メール送信）連携 | 送信API（SES/Gmail等）を選定し、承認後に実行できる |
| [ ] | EXT-007 | P2 | L | M3 | IMP-024 | 外部アクション（カレンダー予約）連携 | Google/Outlook等を選定し、承認後に予約できる |
| [ ] | EXT-008 | P2 | L | M3 |  | 入力データソース連携（週報/勤怠/チャット） | 収集元を決定し、最小1ソースの取り込みが自動化される |

---

## 5.4 AIエンドポイント要件表（M0で確定する）

> 目的: “AIエージェントによるレスポンス生成”を、**エンドポイントごと**に仕様化し、実装/テスト/運用のブレを無くす。

| Endpoint（案） | 用途 | LLM | モデル候補 | ストリーミング | ツール/検索 | 失敗時挙動 | 根拠（参照資料/実装） |
|---|---|---:|---|---|---|---|---|
| `POST /api/v1/simulations/evaluate` | 入力の評価（定量+定性） | TBD | TBD | TBD | DB/pgvector | TBD | `requirement/functional-requirements.md` |
| `POST /api/v1/simulations/{id}/plans/generate` | 3案A/B/C生成 | TBD | TBD | TBD | DB/ログ | TBD | `requirement-docs/response-example.md` |
| `POST /api/v1/plans/{plan_id}/nemawashi/generate` | 下書き生成 | TBD | TBD | TBD | テンプレ+差分 | TBD | `requirement-docs/human-in-the-loop.md` |
| `POST /slack/events`（intervention） | 介入文の解釈 | TBD | TBD | TBD | 状態取得 | TBD | `requirement/initial-display.md` |
| `POST /api/v1/watchdog/run`（内部） | 自動解析の起動 | TBD | TBD | TBD | DB/pgvector | TBD | `requirement/initial-display.md` |

---

## 6. 主要エンドポイント一覧（暫定案 / IMP-003で確定）

> ここは “決定の叩き台” です。M0で確定したら本書を更新します。

- Auth
  - `POST /api/v1/auth/login`（方式により差し替え）
  - `GET /api/v1/me`
- Dashboard
  - `GET /api/v1/dashboard/initial`（初期表示を一括取得）
- Master
  - `GET /api/v1/projects`
  - `GET /api/v1/members`
  - `GET /api/v1/members/{id}`
- Simulator / HITL
  - `POST /api/v1/simulations/evaluate`
  - `POST /api/v1/simulations/{id}/plans/generate`
  - `POST /api/v1/plans/{plan_id}/nemawashi/generate`
  - `POST /api/v1/nemawashi/{draft_id}/request-approval`
  - `POST /api/v1/approvals/{approval_id}/approve`
  - `POST /api/v1/approvals/{approval_id}/reject`
  - `POST /api/v1/nemawashi/{draft_id}/execute`
- Slack
  - `POST /slack/events`（Interactive + Events）

---

## 7. 残課題/リスク/未確定（タスク化の前提）

- 認証方式（Cognito/Slack OAuth/独自JWT等）が未確定（IMP-002）。
- “MVPのAI” をどこまでLLMに寄せるか（ルール/LLM併用・フォールバック方針）（IMP-020）。
- DBスキーマが資料内で複数案存在（`requirement-docs/database-schema.md` の冒頭表 vs DDL）。M0で実装対象を確定（IMP-005）。
- AWSのIaC方式が未確定（AWS-002）。
