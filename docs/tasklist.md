# タスクリスト（SaihAI 完成まで） Issue #11

本書は、リポジトリ内の要件/設計/計画ドキュメントと現状実装（`main` 相当）を突き合わせ、**「アプリケーション完成」までに必要なタスク**を網羅的に列挙したものです。

- タスク分類: **実装 / インフラ構築（AWS） / 外部API連携**
- “主要画面” は **現状の画面一覧（Angular のルーティング）** を正としつつ、要件から見て不足する観点は優先的にタスク化します。
- 以降は **人間=要件/Issue起票、AI=実装/テスト/証跡** の完全分離運用を前提にしています（詳細: 3.4）。

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

> 要件から見た不足観点（追加の画面/導線候補）: **ログイン/認証**, **Slack介入の結果確認（履歴/監査）**, **プロジェクト詳細（体制図/アサイン状況）** など。  
> ただし本Issueでは「現状の画面一覧」を正とし、追加画面は **必要最小** を P0/P1 としてタスク化します。

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

- **S**: 半日〜1日（原則 1PR で完結）
- **M**: 2〜5日（原則 1PR、難しければ 2PR に分割）
- **L**: 1〜2週（必ず **PR単位のサブタスク**に分割してから着手）

### 3.3 マイルストーン（Milestone）

- **M0（設計確定）**: 主要画面/主要エンドポイント/認証方針/AI応答スキーマ/デプロイ形態/IaC 方針を確定
- **M1（MVP）**: 主要画面が実データで動き、認証込みの主要API疎通ができ、AIが構造化レスポンスを生成できる
- **M2（Beta）**: Slack通知・承認（HITL）・Watchdog（自動起動）・永続化/冪等性が通る
- **M3（Release）**: AWS上での本番形に寄せ、非機能（運用可能な最低ライン）を満たす

### 3.4 Issue→PR 運用（人間要件–AIコーディング完全分離）

このリポジトリでは、以降の開発を **「人間=要件、AI=実装」** に完全分離します。

- 人間（Issue起票者）が行うこと
  - `docs/tasklist.md` の **サブタスクID** を 1 つ選び、Issue タイトルに含める（例: `IMP-009-02: Dashboard を v1 API で表示`）
  - Issue 本文に **Goals / Non-Goals / Acceptance Criteria / Evidence** を書く（不足があると AI が“安全側の判断”で作業を止める）
  - PR のコントロール（レビュー/マージ/優先度調整）のみを行う
- AI（実装担当）が行うこと
  - Issue の Acceptance Criteria を満たす実装・ドキュメント更新・テスト追加を行う
  - `npm run lint` / `npm run build` / `npm test` を **常にグリーン**に戻す
  - UI の変更がある場合、必要に応じて `evidence/scenarios.json` と `tests/e2e/evidence.spec.js` を更新し、Playwright 証跡が残るようにする
  - 変更したサブタスクIDを `docs/tasklist.md` 上で `[x]` にし、PR が紐づく場合はリンクを追記する（任意）

### 3.5 “不足情報”の扱い（AIの決め方）

- 資料/実装から確定できるものは **本書の方針に寄せて決定**し、実装を進める
- どうしても確定できない場合は、実装を止めずに **「安全側の暫定」** を置く（例: フォールバックを残す、フラグで切替、モックで先に通す）
- 暫定にした点は、該当サブタスクに **「残課題/リスク」** として明記し、必要なら追加のサブタスクを起票候補として追記する

### 3.6 PR の Done 定義（全サブタスク共通）

- コード変更（必要な場合）
- ドキュメント更新（必要な場合）
- テスト追加/更新（受け入れ条件を検証できること）
- 画面証跡の更新（必要なら `evidence/scenarios.json` を更新）

---

## 4. “完成”の最低条件（M1）をタスク化するための完了条件

### 4.1 主要画面の完成（M1）

- `/dashboard`: 初期表示で「アラート/診断/提案/承認待ち」を **バックエンド集約API**（`GET /api/v1/dashboard/initial`）から取得して描画できる
- `/simulator`: シミュレーション→3プラン表示→（最低限）**承認フロー**まで到達できる（外部実行はモックでも可、ただし状態遷移が成立）
- `/genome`: メンバー詳細（スキル/志向/兆候/根拠）を **API経由**で参照できる（暫定でもよいが、データモデルは固定される）

### 4.2 FE/BE API疎通（認証込み + 主要エンドポイント一式決定）

- 認証は **M1 で必須**（少なくとも「未認証アクセスの拒否」が機能）
- 主要エンドポイント（6. 参照）は **本書で確定**し、M1 で疎通する

### 4.3 AIエージェント応答生成（M1）

- `requirement-docs/response-example.md` を基準に、**画面が直接利用できる構造化JSON**を返す
- LLM 呼び出し要件は **エンドポイント単位で本書に固定**する（5.4）

---

## 5. タスクリスト（上位タスク）

> 各上位タスクは “一覧性” を優先して大きめです。実際の Issue 起票は 7 章の **サブタスク（PR単位）** を使います。

### 5.1 実装（Implementation）

| Done | ID | P | Size | MS | Depends | 概要 | 完了条件（成果物/確認方法） |
|---:|---|---|---|---|---|---|---|
| [x] | IMP-001 | P0 | S | M0 |  | “主要画面”の完成定義を確定 | 本書 4.1 の完成定義が固定されている |
| [x] | IMP-002 | P0 | M | M0 |  | 認証方針を確定（Web） | 本書 6.1/7.1 に認証方針・主要APIが固定されている |
| [x] | IMP-003 | P0 | M | M0 | IMP-002 | 主要エンドポイント一式の確定 | 本書 6. に主要エンドポイント一覧が固定されている |
| [x] | IMP-004 | P0 | M | M0 | IMP-003 | FE↔BE のAPIクライアント設計 | `frontend` 側の base URL/認証ヘッダ/エラー方針を環境変数化し、疎通できる |
| [x] | IMP-005 | P0 | M | M0 |  | DBモデル方針の確定（seed→DB） | 本書 6.2/7.2 に “正” のスキーマ参照が固定されている |
| [ ] | IMP-006 | P0 | L | M1 | IMP-005 | Backend: DB接続 + マイグレーション導入 | ローカルPostgresで起動し、テーブル作成/seed投入/CRUDが通る |
| [ ] | IMP-007 | P0 | M | M1 | IMP-003,IMP-006 | Backend: `/api/v1/projects` `/members` の実装 | DB裏の一覧取得ができ、既存seedの置き換え方針が明確 |
| [ ] | IMP-008 | P0 | L | M1 | IMP-003,IMP-006 | Backend: Dashboard初期表示API | `requirement/initial-display.md` の「初期表示で必要なデータ群」を1回で返す（`GET /api/v1/dashboard/initial`） |
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
| [x] | IMP-019 | P0 | M | M0 | IMP-003 | AI応答スキーマ（画面直結）の型を整備 | `requirement-docs/response-example.md` を基準に Pydantic/TS 型が整備される |
| [x] | IMP-020 | P0 | M | M0 | IMP-003 | AI呼び出し要件を“エンドポイント単位”で確定 | 5.4 の表が埋まり、方針が固定されている |
| [ ] | IMP-021 | P0 | L | M1 | IMP-020,EXT-001 | AI: 3プラン生成をLLM化 | 3プラン（推奨/スコア/議論要約）がLLM生成で返る（失敗時フォールバック含む） |
| [ ] | IMP-022 | P1 | L | M2 | IMP-018,EXT-003 | HITL: 介入指示→再計算→再提示 | “Steer”入力で条件を反映し、再度プラン/下書きが更新される |
| [ ] | IMP-023 | P0 | M | M1 | IMP-002,IMP-003 | FE/BE 認証つなぎ込み | FEでログイン→トークン保持→APIが認可される（未認証は拒否） |
| [ ] | IMP-024 | P1 | M | M2 | IMP-010,IMP-017 | 実行（Execute）を非同期化 | 承認後の実行をジョブ化し、状態遷移（pending→executed/failed）が追える |
| [ ] | IMP-025 | P0 | M | M1 | IMP-010,IMP-019 | Backend: 根回し（nemawashi）下書きAPI | `POST /api/v1/plans/{plan_id}/nemawashi/generate` が画面向けの構造で返る |
| [ ] | IMP-026 | P0 | M | M1 | IMP-011,IMP-025 | Frontend: 根回し下書き表示/承認UI | 下書き→承認依頼→承認/却下が画面上で完結する |
| [ ] | IMP-027 | P1 | L | M2 | IMP-006,IMP-020,EXT-001 | LangGraph導入（Orchestrator + Checkpoint） | `interrupt/resume` がDB永続化され、スレッド単位で再開できる |
| [ ] | IMP-028 | P1 | L | M2 | IMP-027,AWS-007 | Shadow Monitoring（Watchdog）処理の実装 | 定期起動で解析→アラート生成→通知候補がDBに蓄積される |
| [x] | IMP-029 | P2 | M | M3 | IMP-027 | 長時間AI処理の進捗配信（SSE/WS） | FEが進捗/議論ログをストリーミング表示できる |
| [ ] | IMP-030 | P1 | M | M2 | IMP-010 | Backend: 監査ログ（最低限） | 承認/実行/介入の履歴が“誰が/いつ/何を”で追える |
| [ ] | IMP-031 | P1 | M | M2 | IMP-009,IMP-011,IMP-016 | 主要フローのE2E（証跡方針含む） | 主要画面の到達/表示/主要操作が自動テストで担保される |
| [x] | IMP-032 | P2 | M | M3 |  | CIのビルド/テストを実アプリ向けに更新 | `frontend build`/`backend` の検証をCIに組み込み、破綻を早期検知する |

### 5.2 インフラ構築（AWS）

| Done | ID | P | Size | MS | Depends | 概要 | 完了条件（成果物/確認方法） |
|---:|---|---|---|---|---|---|---|
| [x] | AWS-001 | P0 | M | M0 |  | AWSデプロイ形態の確定（整合性確認） | `requirement-docs/app-guideline.md`（ECS/Fargate, Aurora, EventBridge, S3/CloudFront）に沿って採用を固定 |
| [x] | AWS-002 | P0 | M | M0 | AWS-001 | IaC方式の決定（CDK採用） | IaC は **AWS CDK (TypeScript)** を採用し、`infra/` 配下に構成を置く方針が固定 |
| [ ] | AWS-003 | P0 | L | M1 | AWS-002 | ネットワーク基盤（VPC/SG/サブネット） | ECS/Aurora/（必要なら）NAT を含む最小構成が作れる |
| [ ] | AWS-004 | P0 | L | M1 | AWS-002,AWS-003 | Aurora PostgreSQL (pgvector) 構築 | 接続情報がSecrets Manager等で管理され、ローカル以外でも疎通できる |
| [ ] | AWS-005 | P0 | L | M1 | AWS-002 | ECS(Fargate) にBackendをデプロイ | `GET /api/health` がALB経由で応答し、環境変数/Secretsが注入される |
| [ ] | AWS-006 | P0 | M | M1 | AWS-002 | S3 + CloudFront にFrontendをデプロイ | `/dashboard` 等がCloudFront経由で表示される（SPA対応含む） |
| [ ] | AWS-007 | P1 | M | M2 | AWS-002 | EventBridge + SQS（Watchdog起動） | 定期起動→キュー投入→Workerが処理する導線が成立 |
| [ ] | AWS-008 | P1 | M | M2 | AWS-005,AWS-007 | Worker実行基盤（ECS 推奨） | Shadow Monitoring を非同期で回せる（重い処理はECS推奨） |
| [ ] | AWS-009 | P1 | M | M2 | AWS-002 | ログ/メトリクスの最低ライン | CloudWatch Logs/基本アラーム（5xx, キュー滞留, DB接続失敗） |

### 5.3 外部API連携（キー管理/モック方針込み）

| Done | ID | P | Size | MS | Depends | 概要 | 完了条件（成果物/確認方法） |
|---:|---|---|---|---|---|---|---|
| [ ] | EXT-001 | P0 | M | M1 |  | AWS Bedrock（LLM）呼び出し基盤 | `docs/setup.md` / `STRANDS_BEDROCK.md` 前提でBedrockを呼べる。CIでは **モック**でテスト可能（キーなしで落ちない） |
| [ ] | EXT-002 | P1 | M | M2 | EXT-001,AWS-004 | 埋め込み（pgvector用）生成 | **`amazon.titan-embed-text-v2`（1024次元）**を既定とし、embedding→保存→類似検索が通る |
| [ ] | EXT-003 | P1 | M | M2 |  | Slack App（権限/イベント）設計 | Bot権限・Events/Interactive/署名検証の方針が確定し、手順がdocs化される |
| [ ] | EXT-004 | P1 | L | M2 | EXT-003,IMP-017 | Slack: 通知（Block Kit）送信 | Shadow Monitoring の結果をSlackに通知できる（要約+リンク+承認UI） |
| [ ] | EXT-005 | P1 | L | M2 | EXT-003,IMP-018 | Slack: 承認/却下/介入 受信 | `POST /slack/interactions` / `POST /slack/events` で受け、DB更新→再開が成立（署名/リプレイ対策含む） |
| [x] | EXT-006 | P2 | L | M3 | IMP-024 | 外部アクション（メール送信）連携 | 送信API（SES等）を選定し、承認後に実行できる |
| [x] | EXT-007 | P2 | L | M3 | IMP-024 | 外部アクション（カレンダー予約）連携 | Google/Outlook等を選定し、承認後に予約できる |
| [x] | EXT-008 | P2 | L | M3 |  | 入力データソース連携（週報/勤怠/チャット） | 収集元を決定し、最小1ソースの取り込みが自動化される |

---

## 5.4 AIエンドポイント要件表（確定）

> 目的: “AIエージェントによるレスポンス生成”を **エンドポイントごと**に仕様化し、実装/テスト/運用のブレを無くす。  
> 既定プロバイダは **AWS Bedrock（Anthropic Claude）**（`docs/setup.md` / `STRANDS_BEDROCK.md`）。

| Endpoint | 用途 | LLM | 既定モデル | ストリーミング | ツール/検索 | 失敗時挙動 | 根拠（参照資料/実装） |
|---|---:|---:|---|---|---|---|---|
| `POST /api/v1/simulations/evaluate` | 定量評価/前処理 | No（M1） | - | No | DB/SQL（M1） | ルールベースのみで返す | `backend/app/api/v1.py`（現状の evaluate 相当） |
| `POST /api/v1/simulations/{id}/plans/generate` | 3案A/B/C生成 | Yes | Claude Sonnet（既定） | No（M1） | 参照: `system-prompts` /（M2で pgvector） | 既存ルールベースの3案へフォールバック + `aiFallback=true` | `requirement-docs/response-example.md` / `requirement/system-prompts.md` |
| `POST /api/v1/plans/{plan_id}/nemawashi/generate` | 根回し下書き生成 | Yes | Claude Sonnet（既定） | No（M1） | テンプレ +（M2でDB参照） | テンプレ生成にフォールバック（固定文面） | `requirement/functional-requirements.md` / `requirement-docs/human-in-the-loop.md` |
| `POST /slack/events` | 介入テキスト受信（スレッド返信） | Yes（軽量） | Claude Haiku（既定） | No | 状態取得（DB） | ルール（正規表現）で最低限パースし、安全側で no-op | `requirement/initial-display.md` |
| `POST /slack/interactions` | 承認/却下/選択ボタン | No | - | No | 状態遷移（DB） | 認可NGは 403 + 監査ログ | `requirement-docs/human-in-the-loop.md` |
| `POST /api/v1/watchdog/run`（内部） | 自動解析（Shadow Monitoring） | Yes | Claude Sonnet（既定） | No | DB/pgvector（必須） | 失敗は“未解析”として保存し、次回に再試行 | `requirement/initial-display.md` / `requirement-docs/app-guideline.md` |

---

## 6. 主要エンドポイント一覧（確定）

> 注: 現状実装の `/api/*` はモック互換のため残っている。完成形は **`/api/v1` を正**とし、順次移行する。

### 6.1 認証（方針）

- API は **Bearer JWT** を採用（`Authorization: Bearer <token>`）。M1 は “開発用ログイン” を許可し、M3 で本番SSO（Cognito等）を追加しても API 形は維持する。
- 期待する最低条件: **未認証アクセスは 401**、ロール（manager 等）は claim で判定できる。

### 6.2 DB（“正” の参照）

- DB スキーマの “正” は `requirement-docs/database-schema.md` の **DDL セクション** とする（冒頭表に差分がある場合は DDL を優先）。
- pgvector の embedding 次元は **1024**（`amazon.titan-embed-text-v2` を想定）。

### 6.3 エンドポイント一覧

- Health
  - `GET /api/health`（LB/監視向け。認証なし）
- Auth
  - `POST /api/v1/auth/login`（M1: 開発用ログイン含む）
  - `GET /api/v1/me`
- Dashboard（初期表示）
  - `GET /api/v1/dashboard/initial`
  - `GET /api/v1/alerts`
  - `POST /api/v1/alerts/{alert_id}/ack`
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
  - `POST /slack/events`（Events: スレッド返信=介入）
  - `POST /slack/interactions`（Interactive: ボタン=承認/選択）
- Watchdog
  - `POST /api/v1/watchdog/run`（内部。EventBridge/SQS 経由で起動）

---

## 7. サブタスク（PR単位 / Issue起票単位）

> ここが “AI が実装開始できる粒度” の単位。Issue は **必ずこのサブタスクID** を 1 つ選んで起票します。  
> メタ情報（`領域 / P / Size / MS / Depends`）は **親タスク（5章の表）を継承**します（追加依存がある場合のみサブタスク側に追記）。

### 7.1 認証（IMP-002/IMP-023）

- [ ] IMP-002-01 認証方針の docs 固定（完了条件: 本書 6.1 が方針を満たす / 検証: `tests/docs/tasklist-doc.spec.js`）
- [x] IMP-023-01 Backend: JWT 検証ミドルウェア + 401（完了条件: 保護APIが未認証で401 / 検証: APIテスト）
- [x] IMP-023-02 Backend: `POST /api/v1/auth/login`（開発用ユーザーでJWT発行）（完了条件: JWT を返せる / 検証: APIテスト）
- [x] IMP-023-03 Frontend: ログイン導線（最小） + トークン保持（完了条件: 画面からログイン→保持 / 検証: E2E）
- [x] IMP-023-04 Frontend: ガード（未ログイン→ログインへ） + API 401 ハンドリング（完了条件: 未ログインで遷移不可 / 検証: E2E）

### 7.2 DB 基盤（IMP-005/IMP-006）

- [ ] IMP-005-01 DBスキーマ “正” の固定（完了条件: 本書 6.2 が方針を満たす / 検証: `tests/docs/tasklist-doc.spec.js`）
- [x] IMP-006-01 Backend: DB 接続設定（env: `DATABASE_URL`）追加（完了条件: ローカルDBへ接続できる / 検証: 接続テスト）
- [x] IMP-006-02 Alembic（または同等）導入 + 初回マイグレーション（完了条件: migrate up/down / 検証: CI or ローカル）
- [x] IMP-006-03 seed.json を DB に投入する seed スクリプト（完了条件: 一覧APIがDB由来 / 検証: APIテスト）
- [ ] IMP-006-04 CI で DB を立てて最小の統合テストを回す（完了条件: CIで再現 / 検証: `npm test` または別ジョブ）

### 7.3 API/クライアント/マスタ（IMP-003/IMP-004/IMP-007）

- [ ] IMP-003-01 OpenAPI 生成方針の確定（FastAPI 由来を正）（完了条件: OpenAPI を出力できる / 検証: `GET /openapi.json`）
- [ ] IMP-003-02 主要エンドポイントの req/res を Pydantic で型定義（完了条件: OpenAPI に反映 / 検証: 差分確認）
- [x] IMP-004-01 Frontend: API base URL を環境変数で切替（完了条件: 切替で疎通 / 検証: E2E）
- [x] IMP-004-02 Frontend: Auth ヘッダ注入（HttpInterceptor）実装（完了条件: 認証APIが通る / 検証: E2E）
- [x] IMP-004-03 Frontend: API エラーの統一 UI（toast 等）実装（完了条件: エラーが可視化 / 検証: E2E）
- [x] IMP-007-01 Backend: `GET /api/v1/projects`（DB裏）実装（完了条件: DB から返る / 検証: APIテスト）
- [x] IMP-007-02 Backend: `GET /api/v1/members`（DB裏）実装（完了条件: DB から返る / 検証: APIテスト）
- [x] IMP-007-03 Backend: マスタAPIのシード置換方針を docs 化（完了条件: 移行手順が残る / 検証: レビュー）

### 7.4 Dashboard（IMP-008/IMP-009）

- [x] IMP-008-01 `GET /api/v1/dashboard/initial` のレスポンス型（Pydantic）を定義（完了条件: OpenAPI に型が出る / 検証: OpenAPI）
- [x] IMP-008-02 DB から初期表示データを集約して返す（完了条件: 初期表示の必要データが揃う / 検証: API統合テスト）
- [x] IMP-009-01 Frontend: 初期表示を `dashboard/initial` に統合（完了条件: API駆動で描画 / 検証: 画面確認）
- [x] IMP-009-02 Frontend: “承認待ち” を一覧表示（完了条件: 画面に出る / 検証: E2E）
- [ ] IMP-009-03 Evidence 更新（必要時のみ）（完了条件: 証跡が取れる / 検証: `evidence/scenarios.json` + Playwright）

### 7.5 Simulator（IMP-010/IMP-011/IMP-012）

- [x] IMP-010-01 `POST /api/v1/simulations/evaluate` を DB 裏で動かす（完了条件: DB 前提で動く / 検証: APIテスト）
- [x] IMP-010-02 `POST /api/v1/simulations/{id}/plans/generate` を返せる（完了条件: 3案が返る / 検証: APIテスト）
- [x] IMP-011-01 Frontend: v1 evaluate → generate の呼び出し接続（完了条件: 実データで表示 / 検証: E2E）
- [x] IMP-012-01 要件カバー率 UI をデータ駆動に修正（完了条件: requiredSkills が表示 / 検証: E2E）
- [ ] IMP-013-01 Drag & Drop UI（手動配置）実装（完了条件: UIで配置変更できる / 検証: E2E）
- [ ] IMP-013-02 手動配置→再評価（budget/skill/risk）導線（完了条件: 評価が更新 / 検証: E2E）
- [ ] IMP-013-03 手動シミュレーションの仕様（制約/Undo 等）を docs 化（完了条件: 仕様が残る / 検証: レビュー）

### 7.6 Genome（IMP-014/IMP-015/IMP-016）

- [x] IMP-014-01 Genome 詳細項目を API レスポンスに落とす（完了条件: 型が確定 / 検証: OpenAPI）
- [x] IMP-015-01 `GET /api/v1/members/{id}` を実装（完了条件: 詳細が返る / 検証: APIテスト）
- [x] IMP-016-01 Frontend: 詳細表示を API から取得（完了条件: 画面に出る / 検証: E2E）

### 7.7 AI/Watchdog（IMP-019/IMP-021/IMP-025/IMP-027/IMP-028/IMP-029 + EXT-001/EXT-002）

- [x] IMP-019-01 `response-example.md` の JSON を Pydantic/TS に型起こし（完了条件: 型が参照できる / 検証: 型チェック）
- [ ] EXT-001-01 Bedrock クライアントラッパ（本番）+ モック実装（CI）を用意（完了条件: キー無しでもテストが通る / 検証: ユニット）
- [ ] IMP-021-01 Plans Generate: LLM プロンプト/システムプロンプト整備（完了条件: JSON を必ず返す / 検証: モックで検証）
- [ ] IMP-021-02 Plans Generate: LLM 失敗時フォールバック（完了条件: fallback が返る / 検証: 失敗再現）
- [ ] IMP-025-01 Nemawashi Generate: LLM で下書き生成（完了条件: 画面向け構造 / 検証: APIテスト）
- [x] EXT-002-01 Embedding 生成（Titan）+ pgvector 保存（完了条件: 1024次元で保存 / 検証: DB統合）
- [ ] EXT-002-02 類似検索 API（メンバー/週報）導入（完了条件: topK が返る / 検証: APIテスト）
- [x] IMP-027-01 LangGraph: Orchestrator（最小）導入（完了条件: グラフが動く / 検証: ユニット）
- [ ] IMP-027-02 LangGraph: Checkpoint 永続化（thread_id）導入（完了条件: resume できる / 検証: 統合テスト）
- [x] IMP-028-01 Watchdog: 1回起動で1件分析→保存（完了条件: DB に結果 / 検証: 統合テスト）
- [ ] IMP-028-02 Watchdog: 失敗時リトライ/スキップ方針（完了条件: 破綻しない / 検証: 失敗再現）
- [ ] IMP-029-01 長時間AI処理の進捗 API（SSE/WS）導入（完了条件: FEが追える / 検証: E2E）

### 7.8 Slack/HITL（IMP-017/IMP-018/IMP-022/IMP-024/IMP-026/IMP-030 + EXT-003/EXT-004/EXT-005）

- [x] IMP-017-01 DB に approval/state/audit の最小テーブルを作る（完了条件: 主要キー/制約あり / 検証: migrate + API）
- [x] IMP-018-01 冪等キー設計 + 多重実行防止（完了条件: 2回実行で1回だけ / 検証: テスト）
- [x] IMP-022-01 介入（Steer）受付→ state 更新→再生成（完了条件: 介入が反映 / 検証: 統合テスト）
- [x] IMP-024-01 Execute をジョブ化（キュー/worker）し状態遷移（完了条件: pending→done/failed / 検証: 統合テスト）
- [ ] IMP-026-01 Frontend: 根回し下書き表示 + 承認依頼 UI（完了条件: 画面で完結 / 検証: E2E）
- [x] IMP-030-01 監査ログ（append-only）最小実装（完了条件: thread_id で追える / 検証: APIテスト）
- [x] EXT-003-01 Slack App 権限/Events/Interactivity 設計を docs 化（完了条件: 手順が再現可能 / 検証: レビュー）
- [x] EXT-004-01 Slack 通知（Block Kit）送信（完了条件: 送信できる / 検証: dry-run）
- [x] EXT-005-01 `/slack/interactions` 署名検証 + 状態遷移（完了条件: 署名NGで拒否 / 検証: サンプルpayload）
- [x] EXT-005-02 `/slack/events` で介入テキスト受信 + AI パース（完了条件: 介入が取れる / 検証: サンプルpayload）

### 7.9 AWS（AWS-003〜AWS-009）

- [ ] AWS-002-01 `infra/`（CDK）初期セットアップ + `cdk synth`（完了条件: synth が通る / 検証: CI）
- [ ] AWS-003-01 VPC/SG などネットワークを CDK で定義（完了条件: 最小NWが定義 / 検証: synth diff）
- [x] AWS-004-01 Aurora(pgvector) + Secrets Manager（完了条件: 秘密情報が外に出ない / 検証: review）
- [ ] AWS-005-01 ECS(Fargate)+ALB で Backend を公開（完了条件: `/api/health` / 検証: staging）
- [ ] AWS-006-01 S3+CloudFront で Frontend を公開（完了条件: SPAが動く / 検証: staging）
- [x] AWS-007-01 EventBridge→SQS を構成（完了条件: enqueue できる / 検証: staging）
- [x] AWS-008-01 Worker 実行（ECS）で watchdog を消費（完了条件: 1件処理 / 検証: staging）
- [x] AWS-009-01 CloudWatch Logs + 最低限アラーム（完了条件: 監視できる / 検証: staging）

### 7.10 品質/CI/証跡（IMP-031/IMP-032）

- [x] IMP-031-01 主要フローのE2E（Dashboard→Simulator→Approval）追加（完了条件: 安定して通る / 検証: `npm test`）
- [x] IMP-031-02 証跡シナリオ更新（主要画面のURL/操作）（完了条件: trace/video が残る / 検証: Artifacts）
- [ ] IMP-032-01 CI に `frontend` ビルドを追加（完了条件: CIでビルド / 検証: workflow）
- [ ] IMP-032-02 CI に `backend` のユニット/型チェックを追加（完了条件: 破綻検知 / 検証: workflow）

### 7.11 外部アクション/入力ソース（EXT-006/EXT-007/EXT-008）

- [ ] EXT-006-01 メール送信（SES）を抽象化インタフェース化（完了条件: モック/本番差し替え / 検証: ユニット）
- [ ] EXT-006-02 承認後にメール送信が 1 回だけ実行（完了条件: 多重実行しない / 検証: 統合）
- [ ] EXT-007-01 カレンダー予約APIの候補選定→抽象化（完了条件: 選定理由が残る / 検証: レビュー）
- [ ] EXT-007-02 承認後に予約が 1 回だけ実行（完了条件: 多重実行しない / 検証: 統合）
- [ ] EXT-008-01 週報/勤怠/チャットの“最小1ソース”を決定（完了条件: 仕様が残る / 検証: レビュー）
- [ ] EXT-008-02 取り込みジョブ（定期/手動）実装（完了条件: DBに保存 / 検証: 統合）

---

## 8. 残課題/リスク/未確定（タスク化の前提）

- UI の追加画面（履歴/監査、プロジェクト詳細）は要件上有用だが、M1/M2 の進捗を阻害しない範囲で段階導入する。
- 本番SSO（Cognito等）の詳細は M3 で詰める（M1 は JWT で先に進める）。

---

## 9. M0 実行ロードマップ（優先順位/起票順）

### 9.1 スコープ

- 対象: **MS=M0 の未完了タスク（P0/P1）**。
- 注: 本書の後半（10章以降）に、M1〜M3 までの実行ロードマップも同様に記載する。

### 9.2 M0 未完了の上位タスク（依存関係込み）

- IMP-019（Depends: IMP-003）
- IMP-004（Depends: IMP-003）

### 9.3 起票順（サブタスクID）

1) IMP-019-01（AI応答スキーマの型起こし。FE/BE の型整合を先に固定）
2) IMP-004-01（API base URL の環境変数化。以降の疎通土台）
3) IMP-004-02（Auth ヘッダ注入。認証導線の前提）
4) IMP-004-03（API エラー統一UI。疎通時の可視化）

### 9.4 並列可否（参考）

- IMP-019-01 と IMP-004-01 は独立。並列実施可。
- IMP-004-02/IMP-004-03 は IMP-004-01 完了後に実施。

---

## 10. M1 実行ロードマップ（MVP到達: 認証+DB+主要画面疎通）

### 10.1 スコープ

- 対象: **MS=M1 の P0 タスクを中心に、MVP（M1 完了条件）に到達するまで**。
- 前提: **M0（9章）の未完了が解消**していること（特に `IMP-004-*` の疎通土台）。

### 10.2 先に開通させる “疎通ライン”（DoD）

- ローカル: `frontend` → `backend` → `db` の疎通（認証ありの `GET /api/v1/me` が通る）
- 主要API: `GET /openapi.json` / `GET /api/v1/projects` / `GET /api/v1/members` が **DB裏**で応答
- 最低限E2E: ログイン→`/dashboard` 初期表示→`/simulator` evaluate→generate が **Playwright** で自動化できる

### 10.3 起票順（サブタスクID）

1) DB基盤（最優先で “データの正” を作る）
   - IMP-006-01（DB接続設定）
   - IMP-006-02（マイグレーション導入）
   - IMP-006-03（seed投入）
   - IMP-006-04（CIでDB統合テストを回す）

2) 認証（APIを “守る”）
   - IMP-023-01（JWT検証 + 401）
   - IMP-023-02（`POST /api/v1/auth/login`）
   - IMP-023-03（Frontend: ログイン導線 + トークン保持）
   - IMP-023-04（Frontend: ガード + 401ハンドリング）

3) マスタAPI（画面の土台データ）
   - IMP-007-01（`GET /api/v1/projects`）
   - IMP-007-02（`GET /api/v1/members`）
   - IMP-007-03（移行方針docs化）

4) Dashboard（初期表示の一本化）
   - IMP-008-01（`dashboard/initial` のレスポンス型）
   - IMP-008-02（DB集約で初期表示データ返却）
   - IMP-009-01（Frontend: `/dashboard` 実データ化）
   - IMP-009-02（“承認待ち” 表示）
   - IMP-009-03（Evidence 更新）

5) Simulator（v1 API 接続）
   - IMP-010-01（evaluate をDB裏で動かす）
   - IMP-010-02（`plans/generate` を返せる）
   - IMP-011-01（Frontend: evaluate→generate 接続）
   - IMP-012-01（要件カバー率UIのデータ駆動化）

6) Genome（詳細表示まで）
   - IMP-014-01（詳細情報設計の確定）
   - IMP-015-01（Backend: member詳細等）
   - IMP-016-01（Frontend: `/genome` 実データ化）

7) AI（M1で “LLM化” まで進める場合）
   - EXT-001-01（Bedrock 呼び出し基盤）
   - IMP-021-01（3プラン生成のLLM化 + フォールバック）
   - IMP-025-01（根回し下書きAPI）
   - IMP-026-01（Frontend: 根回し表示 + 承認依頼UI）

### 10.4 並列可否（参考）

- Lane A（Backend/DB）: IMP-006-* → IMP-007-* / IMP-008-* / IMP-010-* / IMP-015-01
- Lane B（Frontend）: IMP-023-03/04 → IMP-009-* / IMP-011-01 / IMP-016-01
- Lane C（External/AI）: EXT-001-01 は DB と並列可（ただし IMP-021/IMP-025/IMP-026 は Simulator 系完了後が安全）
- ブロッカー: DB（IMP-006）未完だと M1 の大半が止まるため、最優先で “先頭固定”

---

## 11. M2 実行ロードマップ（P1: Slack/HITL/Watchdog/永続化）

### 11.1 スコープ

- 対象: **MS=M2 の P1 タスク**（Slack/HITL/Watchdog/永続化/Worker/監視）を “一連の運用導線” として成立させる。
- 前提: **M1 が成立**していること（認証+DB+主要画面が疎通）。

### 11.2 起票順（サブタスクID）

1) 承認/監査の永続化（Slackより先に “状態の正” を作る）
   - IMP-017-01（approval/state/audit の最小テーブル）
   - IMP-030-01（監査ログ append-only）
   - IMP-018-01（冪等/多重実行防止）

2) Slack 基盤（設計→受信→送信の順）
   - EXT-003-01（Slack App 設計 docs）
   - EXT-005-01（interactions 署名検証 + 状態遷移）
   - EXT-005-02（events 受信 + 介入テキストパース）
   - EXT-004-01（通知送信）

3) HITL（介入→再生成→再提示）
   - IMP-022-01（Steer 受付→state更新→再生成）

4) Execute の非同期化（承認後の “実行” を安全にする）
   - IMP-024-01（Execute ジョブ化 + 状態遷移）

5) Orchestrator/Watchdog（Shadow Monitoring）
   - IMP-027-01（LangGraph導入 + Checkpoint）
   - AWS-007-01（EventBridge→SQS）
   - AWS-008-01（Worker 実行基盤）
   - IMP-028-01（Watchdog 処理）
   - AWS-009-01（Logs/Alarm）

6) pgvector/embedding（Watchdog の精度を上げる）
   - AWS-004-01（Aurora pgvector）
   - EXT-002-01（埋め込み生成）

7) 品質/証跡（M2 の “動作証拠” を残す）
   - IMP-031-01（主要フローE2E）
   - IMP-031-02（証跡シナリオ更新）

### 11.3 並列可否（参考）

- Lane A（DB/Backend）: IMP-017-01 → IMP-018-01/IMP-030-01 → IMP-022-01/IMP-024-01
- Lane B（Slack）: EXT-003-01 → EXT-005-* → EXT-004-01（ただし state テーブルが無いと “正しい遷移” が作りづらい）
- Lane C（Infra）: AWS-007-01/AWS-008-01/AWS-009-01 は M1 のAWS基盤がある前提で並列可

---

## 12. M3 実行ロードマップ（P2: 仕上げ/拡張）

### 12.1 スコープ

- 対象: **MS=M3 の P2 タスク**（長時間処理のUX、CI強化、外部アクション、入力ソース連携）。
- 前提: **M2 の “運用導線” が成立**していること（状態永続化 + Slack/HITL + Watchdog）。

### 12.2 起票順（サブタスクID）

1) UX/安定性（長時間AI処理の進捗配信）
   - [x] IMP-029-01（SSE/WS で進捗/議論ログ配信）

2) CI/品質（破綻の早期検知）
   - [x] IMP-032-01（CIに `frontend` build）
   - [x] IMP-032-02（CIに `backend` の検証）

3) 外部アクション（承認後の実行先を増やす）
   - [x] EXT-006-01/EXT-006-02（メール送信連携）
   - [x] EXT-007-01/EXT-007-02（カレンダー予約連携）

4) 入力ソース（学習/解析の材料を増やす）
   - [x] EXT-008-01（最小1ソース決定: 週報）
   - [x] EXT-008-02（取り込みジョブ実装）

### 12.3 並列可否（参考）

- Lane A（App/UX）: IMP-029-01
- Lane B（CI）: IMP-032-01/IMP-032-02
- Lane C（External）: EXT-006/EXT-007/EXT-008（ただし Execute/監査の要件に沿って実装する）
