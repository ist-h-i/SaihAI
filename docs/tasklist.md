# リリースまでの計画　作成日: 2026-01-13  

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

- [x] (P0/M1) NEW-REQ-001: “主要フロー”の受け入れ条件を確定（Web: dashboard/simulator/genome + Slack: 通知/承認/介入）
- [x] (P0/M1) NEW-REQ-002: 本番で扱うデータ範囲（PII/人事データ/保持期間）を定義（ログ出力方針・マスキング方針の前提）
- [x] (P0/M3) NEW-REQ-003: （対象ユーザー、IdP、ロール、運用）を確定

#### A2. UI/UX 方針（P1/P2）

- [x] (P2/M3) NEW-UX-001: UI/UX 改善の適用範囲を決め、`docs/uiux-improvement-plan.md` を Issue 化して実行レーンに載せる

#### B2. ロール/権限（P1）

- [x] (P1/M2) NEW-AUTHZ-001: ロール定義（例: manager/admin）- [ ] (P1/M2) NEW-AUTHZ-002: 重要操作（承認/実行/介入）に権限制御を適用する

### C. Webアプリ（Angular）

#### C2. `/dashboard`（P0）

- [x] (P0/M1) IMP-008: Backend: Dashboard初期表示API（`GET /api/v1/dashboard/initial`）
- [x] (P0/M1) IMP-009: Frontend: `/dashboard` をDBデータ駆動に置換（KPI/アラート/提案/承認待ち）

#### C3. `/simulator`（P0/P1）

- [x] (P0/M1) IMP-010: Backend: シミュレーションAPI（評価→プラン生成）
- [x] (P0/M1) IMP-011: Frontend: `/simulator` を v1 API へ接続（評価→3プラン表示→選択）

#### C4. `/genome`（P0/P1）

- [x] (P0/M1) IMP-014: Frontend: `/genome` の“詳細”情報設計（志向/推移/根拠/検索）
- [x] (P0/M1) IMP-015: Backend: Genome関連API（`GET /api/v1/members/{id}` 等）
- [x] (P0/M1) IMP-016: Frontend: `/genome` をDBデータ駆動に置換（詳細表示/フィルタ）
- [ ] (P1/M2) EXT-002: 埋め込み生成 + 類似検索（pgvector）を UI に段階導入

### D. Backend/API（FastAPI）

#### D1. DB/マイグレーション（P0）

- [x] (P0/M1) IMP-006: Backend: DB接続 + マイグレーション導入（seed→DBへ移行）

#### D2. マスタ/API（P0）

- [x] (P0/M1) IMP-007: Backend: `/api/v1/projects` `/members` の実装（DB裏）

#### D3. 根回し（nemawashi）/承認（P0/P1）

- [x] (P0/M1) IMP-025: Backend: 根回し下書きAPI（`POST /api/v1/plans/{plan_id}/nemawashi/generate`）
- [x] (P0/M1) IMP-026: Frontend: 根回し下書き表示/承認UI（下書き→承認依頼→承認/却下）
- [ ] (P1/M2) IMP-017: “承認待ち状態”の永続化（DB）
- [ ] (P1/M2) IMP-024: 実行（Execute）を非同期化（ジョブ化 + 状態遷移）

### E. AI/Agent（Bedrock + LangGraph + RAG）

#### E1. LLM 基盤（P0）

- [x] (P0/M1) EXT-001: AWS Bedrock（LLM）呼び出し基盤（CIではモック可能）

#### E2. 生成系（P0）

- [x] (P0/M1) IMP-021: 3プラン生成を LLM 化（フォールバック含む、構造化レスポンス）

#### E3. LangGraph/HITL（P1）

- [ ] (P1/M2) IMP-027: LangGraph導入（Orchestrator + Checkpoint / interrupt-resume 永続化）
- [ ] (P1/M2) IMP-022: HITL: 介入指示→再計算→再提示（Steer）

#### E4. ベクトル検索（P1）

- [ ] (P1/M2) EXT-002: 埋め込み生成（`amazon.titan-embed-text-v2` / 1024次元）→保存→類似検索

### F. Googleシステム・Slack/HITL（通知・承認・介入）

#### F1. Slack アプリ（P1）

- [ ] (P1/M2) EXT-003: Slack App（権限/Events/Interactive/署名検証）の設計と docs 化
- [ ] (P1/M2) EXT-005: Slack: 承認/却下/介入 受信（`/slack/interactions` / `/slack/events`、署名/リプレイ対策）

#### F2. 通知（P1）

- [ ] (P1/M2) EXT-004: Slack: 通知（Block Kit）送信（要約+リンク+承認UI）

#### F3. 結果通知/導線（P1/P2）

- [ ] (P1/M2) NEW-SLACK-001: 承認/実行/介入の結果を Slack に集約通知（Webへの deep link を含む）

### G. Watchdog（自動起動）/非同期処理

#### G1. 処理ロジック（P1）

- [ ] (P1/M2) IMP-028: Shadow Monitoring（Watchdog）処理の実装（解析→アラート生成→通知候補の蓄積）

#### G2. AWS トリガー/ワーカー（P1）

- [ ] (P1/M2) AWS-007: EventBridge + SQS（Watchdog起動）

### H. AWS/環境（staging→prod）

#### H1. 本番形の基盤（P0）

- [x] (P0/M1) AWS-004: Aurora PostgreSQL（pgvector）構築（接続情報を Secrets Manager 等で管理）
