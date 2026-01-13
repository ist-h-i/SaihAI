# 本番リリース計画（SaihAI）

作成日: 2026-01-13  
対象: `frontend/` / `backend/` / `infra/`（AWS）  
詳細バックログ: `docs/tasklist.md`（ID: `IMP-*` / `AWS-*` / `EXT-*`）  
関連: `requirement/functional-requirements.md`, `requirement-docs/function-list.md`, `docs/setup.md`, `docs/aws-setup.md`, `docs/aws-deploy.md`, `docs/uiux-improvement-plan.md`

---

## 0. 使い方（運用ルール）

- 本書は「本番リリース（Release=Milestone M3）」に向けた、**優先度付きWBS（大/中/小項目）**です。
- 小項目は **GitHub Issue 1つ**（= 1PR〜数PR）に分割する前提です。
  - 既存の詳細IDがあるものは、Issue タイトルに `IMP-xxx-yy:` の形式で入れます（方針は `docs/tasklist.md` の 3.4 を参照）。
- 既存IDの完了/未完了（`[x]/[ ]`）は `docs/tasklist.md` を正とし、本書は **「順序・抜け漏れ防止」**が主目的です。

---

## 1. 優先度・マイルストーン（定義）

### 1.1 優先度（P0/P1/P2）

- **P0**: リリースブロッカー（主要画面/認証/主要API疎通/AI応答生成 + 本番で事故らない最低限）
- **P1**: Betaの核（Slack/HITL/Watchdog/永続化/冪等性）+ 運用可能な最低ラインを満たす
- **P2**: 仕上げ・拡張（性能/演出/追加連携/入力ソース拡張/運用の磨き込み）

### 1.2 マイルストーン（M0〜M3）

`docs/tasklist.md` に準拠します。

- **M1（MVP）**: 主要画面が実データで動き、認証込みの主要API疎通ができ、AIが構造化レスポンスを生成できる
- **M2（Beta）**: Slack通知・承認（HITL）・Watchdog（自動起動）・永続化/冪等性が通る
- **M3（Release）**: AWS上での本番形に寄せ、非機能（運用可能な最低ライン）を満たす

---

## 2. 本番リリース（M3）Go/No-go（完了条件）

### 2.1 機能（ユーザー価値）

- Web（Angular）
  - `/login`: 認証が成立し、未認証アクセスは拒否される
  - `/dashboard`: 初期表示で「アラート/診断/提案/承認待ち」が **実データ**で見える
  - `/simulator`: 評価 → 3プラン提示 → 根回し下書き → 承認依頼 まで到達できる（外部実行は段階導入可）
  - `/genome`: メンバー詳細（スキル/志向/兆候/根拠）を検索・参照できる（類似検索は段階導入可）
- Slack
  - Watchdog 由来の通知（要約 + 参照リンク + 必要なら承認UI）が届く
  - 承認/却下/介入（Steer）が **冪等**に処理され、結果が追跡できる

### 2.2 非機能（運用可能な最低ライン）

- **認証/認可**: 本番方針（SSO含む）が確定し、権限境界が明確
- **監査**: 「誰が/いつ/何を（承認/却下/介入/実行）」したかが追える（改ざん困難な追記型ログ）
- **監視**: 5xx、ジョブ滞留、DB接続失敗などのアラートがあり、一次切り分けができる
- **秘密情報管理**: トークン/鍵が Secrets Manager 等で管理され、環境ごとに分離される
- **バックアップ/復旧**: DB のバックアップと、復旧手順（最低1回のリハーサル）がある
- **リリース手順**: ロールバック手順と影響範囲がドキュメント化されている

---

## 3. 実行順序（クリティカルパス）

1) **M1（P0）を最短で通す**（Webの主要画面×実データ×認証×主要API×AIの構造化応答）  
2) **AWS で “動く staging” を作る**（本番形に寄せたデプロイ形態で疎通）  
3) **M2（P1）を一連の運用導線として成立**（Slack/HITL/Watchdog/永続化/冪等性/監査/監視）  
4) **M3（Release）で非機能の最低ラインを満たす**（監視、復旧、セキュリティ、運用手順）  
5) **RC（リリース候補）→ 本番リリース**（最終チェック、段階ロールアウト、事後監視）

---

## 4. タスクリスト（WBS）

> 記法: `[ ] (P0/M1) IMP-006 ...` のように **優先度/マイルストーン/既存ID** を併記します。  
> 既存IDがないものは `NEW-*` として起票候補にします（後で `docs/tasklist.md` に正式追加推奨）。

### A. プロダクト/要件（横断）

#### A1. リリーススコープ/受け入れ条件（P0）

- [ ] (P0/M1) NEW-REQ-001: “主要フロー”の受け入れ条件を確定（Web: dashboard/simulator/genome + Slack: 通知/承認/介入）
- [ ] (P0/M1) NEW-REQ-002: 本番で扱うデータ範囲（PII/人事データ/保持期間）を定義（ログ出力方針・マスキング方針の前提）
- [ ] (P0/M3) NEW-REQ-003: 本番SSO（Cognito/OIDC 等）の要件（対象ユーザー、IdP、ロール、運用）を確定

#### A2. UI/UX 方針（P1/P2）

- [ ] (P2/M3) NEW-UX-001: UI/UX 改善の適用範囲を決め、`docs/uiux-improvement-plan.md` を Issue 化して実行レーンに載せる

### B. 認証/認可（Web + API）

#### B1. MVP 認証（P0）

- [ ] (P0/M1) IMP-023: FE/BE 認証つなぎ込み（ログイン→トークン保持→未認証拒否）

#### B2. ロール/権限（P1）

- [ ] (P1/M2) NEW-AUTHZ-001: ロール定義（例: manager/admin）と API 権限チェック方針を決める（監査ログとセットで）
- [ ] (P1/M2) NEW-AUTHZ-002: 重要操作（承認/実行/介入）に権限制御を適用する

#### B3. 本番SSO（P0〜P1）

- [ ] (P0/M3) NEW-AUTH-SSO-001: Cognito/OIDC 方式決定（Hosted UI/ALB OIDC/独自実装のいずれか）
- [ ] (P0/M3) NEW-AUTH-SSO-002: トークン検証（JWKS）/ロール付与/失効（logout/期限）を実装
- [ ] (P0/M3) NEW-AUTH-SSO-003: 既存JWT（開発用）との共存/移行（staging→prod）を設計

### C. Webアプリ（Angular）

#### C1. 共通基盤（P0/P1）

- [ ] (P0/M1) IMP-004: FE↔BE APIクライアント設計の見直し（base URL/認証ヘッダ/タイムアウト/エラー方針）
- [ ] (P1/M2) NEW-FE-001: 画面共通のエラーハンドリング（401/403/5xx/ネットワーク断）と再試行導線を整備
- [ ] (P1/M2) NEW-FE-002: 監査・相関のため、リクエストID（例: `X-Request-ID`）を FE→BE に付与（ログと突合できる）

#### C2. `/dashboard`（P0）

- [ ] (P0/M1) IMP-008: Backend: Dashboard初期表示API（`GET /api/v1/dashboard/initial`）
- [ ] (P0/M1) IMP-009: Frontend: `/dashboard` を実データ駆動に置換（KPI/アラート/提案/承認待ち）

#### C3. `/simulator`（P0/P1）

- [ ] (P0/M1) IMP-010: Backend: シミュレーションAPI（評価→プラン生成）
- [ ] (P0/M1) IMP-011: Frontend: `/simulator` を v1 API へ接続（評価→3プラン表示→選択）
- [ ] (P0/M1) IMP-012: Frontend: “要件カバー率”UI を完成（requiredSkills 等）
- [ ] (P1/M2) IMP-013: Frontend: ドラッグ&ドロップ手動シミュレーション（リアルタイム評価）

#### C4. `/genome`（P0/P1）

- [ ] (P0/M1) IMP-014: Frontend: `/genome` の“詳細”情報設計（志向/推移/根拠/検索）
- [ ] (P0/M1) IMP-015: Backend: Genome関連API（`GET /api/v1/members/{id}` 等）
- [ ] (P0/M1) IMP-016: Frontend: `/genome` を実データ駆動に置換（詳細表示/フィルタ）
- [ ] (P1/M2) EXT-002: 埋め込み生成 + 類似検索（pgvector）を UI に段階導入

### D. Backend/API（FastAPI）

#### D1. DB/マイグレーション（P0）

- [ ] (P0/M1) IMP-006: Backend: DB接続 + マイグレーション導入（seed→DBへ移行）

#### D2. マスタ/API（P0）

- [ ] (P0/M1) IMP-007: Backend: `/api/v1/projects` `/members` の実装（DB裏）

#### D3. 根回し（nemawashi）/承認（P0/P1）

- [ ] (P0/M1) IMP-025: Backend: 根回し下書きAPI（`POST /api/v1/plans/{plan_id}/nemawashi/generate`）
- [ ] (P0/M1) IMP-026: Frontend: 根回し下書き表示/承認UI（下書き→承認依頼→承認/却下）
- [ ] (P1/M2) IMP-017: “承認待ち状態”の永続化（DB）
- [ ] (P1/M2) IMP-018: 承認の冪等性/多重実行防止
- [ ] (P1/M2) IMP-024: 実行（Execute）を非同期化（ジョブ化 + 状態遷移）
- [ ] (P1/M2) IMP-030: Backend: 監査ログ（最低限）

#### D4. 防御的設計（P1/P2）

- [ ] (P1/M3) NEW-BE-SEC-001: rate limit/abuse 対策（少なくとも重要操作とAI系エンドポイント）
- [ ] (P2/M3) NEW-BE-SEC-002: 入力バリデーション/サイズ制限/タイムアウトの統一（LLM入力やSlack payload含む）

### E. AI/Agent（Bedrock + LangGraph + RAG）

#### E1. LLM 基盤（P0）

- [ ] (P0/M1) EXT-001: AWS Bedrock（LLM）呼び出し基盤（CIではモック可能）

#### E2. 生成系（P0）

- [ ] (P0/M1) IMP-021: 3プラン生成を LLM 化（フォールバック含む、構造化レスポンス）

#### E3. LangGraph/HITL（P1）

- [ ] (P1/M2) IMP-027: LangGraph導入（Orchestrator + Checkpoint / interrupt-resume 永続化）
- [ ] (P1/M2) IMP-022: HITL: 介入指示→再計算→再提示（Steer）

#### E4. ベクトル検索（P1）

- [ ] (P1/M2) EXT-002: 埋め込み生成（`amazon.titan-embed-text-v2` / 1024次元）→保存→類似検索

#### E5. 長時間処理UX（P2）

- [ ] (P2/M3) IMP-029: 長時間AI処理の進捗配信（SSE/WS）を主要フローに統合（画面/ログのUXを整える）

#### E6. 変更管理（P1/P2）

- [ ] (P1/M3) NEW-AI-OPS-001: プロンプト/モデル設定のバージョニング（環境差分、ロールバック）
- [ ] (P2/M3) NEW-AI-OPS-002: コスト可視化（呼び出し回数/トークン/失敗率）と上限制御

### F. Slack/HITL（通知・承認・介入）

#### F1. Slack アプリ（P1）

- [ ] (P1/M2) EXT-003: Slack App（権限/Events/Interactive/署名検証）の設計と docs 化
- [ ] (P1/M2) EXT-005: Slack: 承認/却下/介入 受信（`/slack/interactions` / `/slack/events`、署名/リプレイ対策）

#### F2. 通知（P1）

- [ ] (P1/M2) EXT-004: Slack: 通知（Block Kit）送信（要約+リンク+承認UI）

#### F3. 結果通知/導線（P1/P2）

- [ ] (P1/M2) NEW-SLACK-001: 承認/実行/介入の結果を Slack に集約通知（Webへの deep link を含む）
- [ ] (P2/M3) NEW-SLACK-002: 通知のノイズ制御（抑制、まとめ、優先度、スヌーズ）

### G. Watchdog（自動起動）/非同期処理

#### G1. 処理ロジック（P1）

- [ ] (P1/M2) IMP-028: Shadow Monitoring（Watchdog）処理の実装（解析→アラート生成→通知候補の蓄積）

#### G2. AWS トリガー/ワーカー（P1）

- [ ] (P1/M2) AWS-007: EventBridge + SQS（Watchdog起動）
- [ ] (P1/M2) AWS-008: Worker実行基盤（ECS 推奨）

#### G3. 運用設計（P1/P2）

- [ ] (P1/M3) NEW-WATCHDOG-001: 実行頻度/対象範囲/リトライ/サーキットブレーカ設計（過負荷・誤検知を抑える）
- [ ] (P2/M3) NEW-WATCHDOG-002: バッチ/キュー滞留時の優先度制御（SQS設計 or アプリ側のスケジューリング）

### H. AWS/環境（staging→prod）

#### H1. 本番形の基盤（P0）

- [ ] (P0/M1) AWS-003: ネットワーク基盤（VPC/SG/サブネット）
- [ ] (P0/M1) AWS-004: Aurora PostgreSQL（pgvector）構築（接続情報を Secrets Manager 等で管理）
- [ ] (P0/M1) AWS-005: ECS(Fargate) に Backend をデプロイ（ALB 経由で疎通）
- [ ] (P0/M1) AWS-006: S3 + CloudFront に Frontend をデプロイ（SPA対応）

#### H2. 観測性（P1）

- [ ] (P1/M2) AWS-009: ログ/メトリクスの最低ライン（5xx, キュー滞留, DB接続失敗）
- [ ] (P1/M3) NEW-OBS-001: CloudWatch ダッシュボード + アラート運用（誰が見るか/一次対応/エスカレーション）

#### H3. 本番セキュリティ（P0/P1）

- [ ] (P0/M3) NEW-AWS-SEC-001: HTTPS/TLS（ACM）+ 独自ドメイン + HSTS（CloudFront）
- [ ] (P1/M3) NEW-AWS-SEC-002: WAF（必要なら）/Bot対策/レート制限（少なくとも重要API）
- [ ] (P1/M3) NEW-AWS-SEC-003: 秘密情報のローテーション方針（Bedrock/Slack/JWT/SSO）と手順化

#### H4. IaC（方針再確認・任意）

- [ ] (P2/M3) NEW-IAC-001: 本番だけでも IaC（CDK 等）を採用するか再判断（構築/復旧/差分管理の観点）

### I. 品質（テスト/CI/証跡）

#### I1. 主要フローE2E（P1）

- [ ] (P1/M2) IMP-031: 主要フローの E2E（証跡方針含む）を整備（Playwright）

#### I2. CI（P2）

- [ ] (P2/M3) IMP-032: CI のビルド/テストを実アプリ向けに更新（frontend build/backend validation 等）

#### I3. 本番前の検証（P1/P2）

- [ ] (P1/M3) NEW-TEST-001: 負荷/性能の最低ラインを定義し、スモーク負荷試験を用意（シミュレーション/生成系）
- [ ] (P1/M3) NEW-TEST-002: セキュリティ検査（依存脆弱性/設定ミス）をCIに組み込む（最低限: npm/pip audit 相当）

### J. 運用/セキュリティ/コンプライアンス

#### J1. ログ/監査/データ保持（P0/P1）

- [ ] (P1/M2) IMP-030: 監査ログ（最低限）を実装し、検索/追跡の手順を docs 化
- [ ] (P0/M3) NEW-DATA-001: ログのPIIマスキング方針（フロント/バック/Slack）を確定し、実装で担保
- [ ] (P1/M3) NEW-DATA-002: データ保持期間/削除（退職者対応等）の運用ルールを決める

#### J2. バックアップ/復旧（P0）

- [ ] (P0/M3) NEW-DR-001: DB バックアップ/リストア手順を作成し、最低1回リハーサルする（RTO/RPOを暫定でも置く）

#### J3. リリース/障害対応（P1）

- [ ] (P1/M3) NEW-OPS-001: リリース手順（手動/自動、ロールバック、権限、チェック）を runbook 化
- [ ] (P1/M3) NEW-OPS-002: 障害時の一次対応フロー（アラート→切り分け→復旧→事後）を整備

---

## 5. 直近の推奨「起票順」（迷ったらこれ）

1) **M1（P0）疎通ライン**: `IMP-006` → `IMP-007` → `IMP-008` → `IMP-009` → `IMP-010` → `IMP-011` → `IMP-023`  
2) **Genome を実データ化**: `IMP-014` → `IMP-015` → `IMP-016`  
3) **LLM を核に接続**: `EXT-001` → `IMP-021` → `IMP-025` → `IMP-026`  
4) **AWS staging（本番形）**: `AWS-003` → `AWS-004` → `AWS-005` → `AWS-006`  
5) **M2（P1）運用導線**: `IMP-017` → `IMP-018` → `EXT-003` → `EXT-004` → `EXT-005` → `IMP-027` → `IMP-028` → `AWS-007` → `AWS-008` → `AWS-009` → `IMP-031`  
6) **M3（Release）仕上げ**: SSO/HTTPS/監視/復旧（`NEW-*`）→ 必要なら外部アクション/入力ソース拡張（`EXT-*`）

