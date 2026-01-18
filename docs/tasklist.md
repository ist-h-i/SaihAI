<!-- ASCII padding to avoid Windows apply_patch char-boundary bug when truncating command strings. -->
<!-- ................................................................................................................................................................................................................................................ -->

# タスクリスト

本書は、プロダクト完遂までのタスクリスト（バックログ）です。完了/未完了（`[x]/[ ]`）は本書を正とします。

## 参照資料一覧

- `README.md`
- `docs/WORKFLOW.md`
- `docs/release-plan.md`
- `docs/setup.md`
- `docs/aws-setup.md`
- `docs/aws-deploy.md`
- `docs/uiux-improvement-plan.md`
- `requirement/` / `requirement-docs/`

## 現状実装の棚卸し

- Frontend: `frontend/`（Angular）
- Backend: `backend/`（FastAPI）
- Infra: `infra/`（AWS）
- Docs/Tests: `docs/`, `tests/`

## 主要画面（現状の画面一覧＝正）

- `/dashboard`
- `/simulator`
- `/genome`

## タスク運用基準

### Issue→PR

- Issue は「目的（成果物）」単位で作成し、PR で完結させる
- Issue/PR タイトルには既存ID（例: `IMP-*` / `AWS-*` / `EXT-*`）を付ける

### サブタスク（PR単位）

- 大きい ID（例: `IMP-017`）は、PR の単位で `IMP-017-01` のようにサブタスク化して管理する
- チェックボックスは「その ID が満たされたか」を表す（完了時に `[x]`）

## AIエンドポイント要件表

認証ヘッダ（共通）: `Authorization: Bearer JWT`

| 区分 | パス | 用途 | 備考 |
| --- | --- | --- | --- |
| Web | `/dashboard` | ダッシュボード | 主要画面 |
| Web | `/simulator` | 介入シミュレーション | 主要画面 |
| Web | `/genome` | メンバー詳細/根拠 | 主要画面 |

## 主要エンドポイント一覧

- `GET /api/v1/dashboard/initial`
- `GET /api/v1/simulator/plan`
- `GET /api/v1/genome/search`

## タスクリスト

### 実装（Implementation）

- [ ] IMP-003: Backend/Frontend の土台（API/データ取得の骨格）を整備
- [x] IMP-017-01: HITL 承認フロー（Slack→承認要求→状態遷移）
- [x] IMP-018-01: HITL 監査ログの永続化と追跡
- [x] IMP-022-01: Watchdog の実行ジョブ管理（起動/完了/失敗）
- [x] IMP-024-01: Watchdog アラートの永続化（通知/参照）
- [x] IMP-030-01: Slack 通知（運用導線の最低ライン）
- [x] IMP-029: M3 P2: 進捗ストリーミング（UI 反映）
- [x] IMP-032: M3 P2: 外部アクション実行の導線（最小）

### インフラ構築（AWS）

- [ ] AWS-001: Staging の最小構成（Bedrock + DB + 配信）を用意

### 外部API連携

- [ ] EXT-001: 外部連携（最小構成）の方針決定と接続テスト
- [x] EXT-003-01: Slack Interactions 受信（/slack/interactions）
- [x] EXT-004-01: Slack Events 受信（/slack/events）
- [x] EXT-005-01: Slack からの承認（Approve）処理
- [x] EXT-005-02: Slack からの却下（Reject）処理
- [x] EXT-006: M3 P2: 外部アクション実行（最小）
- [x] EXT-007: M3 P2: 入力ソース取り込み（最小）
- [x] EXT-008: M3 P2: 取り込み→処理→表示の導線

## M0 実行ロードマップ

- まずはローカルで「画面が動く」状態を作る（PoC）
- ドキュメントとタスク運用を確立する

## M1 実行ロードマップ

- Web の主要画面が実データで動く
- 認証込みの主要API疎通ができる

## M2 実行ロードマップ

- Slack 通知・承認（HITL）・Watchdog が一連の運用導線として成立
- 永続化/冪等性/監査ログが揃う

## M3 実行ロードマップ

- AWS 上での本番形に寄せ、非機能の最低ラインを満たす
- 監視/復旧/セキュリティ/運用手順を整備する
