# AGENTS.md — Golden Profile Operating Contract (SES)

このリポジトリでは、`.agent/` 配下の Golden Profile を「正（Single Source of Truth）」として扱う。
Codex / エージェントは、作業開始時に必ず `.agent/` を読み、以下の契約に従うこと。

---

## 0. Always Read First

- `.agent/profile.yaml`
- `.agent/ruleset.yaml`
- `.agent/metrics.yaml`
- `.agent/commands.yaml`
- 該当スタックの `.agent/rulesets/**`
- （A/B実験を行う場合）`.agent/experiments/**`

---

## 1. Default Policy (Offline-First)

- デフォルトは **オフライン**（外部通信・アップロード前提で進めない）
- オンライン利用が必要な場合は、必ず事前に「送信内容のプレビュー」と「理由」を提示し、承認を待つ
- 送信する場合も **差分のみ**を原則とする（コード全体や機密情報の送信は禁止）

---

## 2. Non-Negotiable Principles

以下は必ず遵守する（`.agent/ruleset.yaml` の原則を優先）：

- **Small Patch First**：変更は小さく刻む
- **Explainability**：意図・根拠・トレードオフを必ず残す
- **Reproducibility**：再現可能な手順と判定基準を残す
- **No Silent Risk**：リスクは明示。未確定は保留
- **Boy Scout Rule**：触るなら少しだけ良くする（目的外の大改修は禁止）

---

## 3. Work Protocol (Plan → Patch → Review → Decision)

作業は必ず次の順序で出力する。

### 3.1 Plan（必須）

- `.agent/templates/plan.md` 形式で作成する
- Plan が未承認の状態ではコード変更に着手しない

### 3.2 Patch（小さく）

- 変更ファイル数／変更行数は `.agent/ruleset.yaml` の制約を守る
- 大規模リファクタ・依存関係のメジャー更新・大量リネームは禁止（必要なら分割提案）

### 3.3 Review（必須）

- `.agent/templates/review.md` 形式でセルフレビューを出す
- リスク、テスト方針、ロールバックを必ず明記

### 3.4 Decision（必須）

- `.agent/templates/decision.md` 形式で採否判断材料を提示する
- “採用条件 / 保留条件” を明確化する（HITL前提）

---

## 4. Verification Gates (Recommended)

- `.agent/commands.yaml` の gate（lint/test/build）を可能な範囲で実行する
- 実行できない場合は、代替の手動テストを **手順＋観測点** つきで記載する

---

## 5. A/B Experiments (Optional but Supported)

A/B を行う場合：

- `.agent/experiments/*.yaml` を使用する（差分のみ）
- “勝者総取り”は禁止。**Selective Merge（良い要素のみ抽出）** を基本とする
- 実験結果は `.agent/metrics.yaml` の評価軸に沿って比較し、HITLで判断可能な形で提示する

---

## 6. Safety & Security

- secrets / PII / 機密をログや差分に含めない
- 入力検証、認証認可への影響、SQL文字列結合、動的コード実行などは常に警戒する
- 不明点がある場合は、推測で進めず質問する

---

## 7. Output Style

- 曖昧な一般論は避ける。具体（対象ファイル、変更点、理由、リスク、テスト、戻し方）で書く
- 変更提案は **差分が小さい順**に提示する

## 8. Slash Commands (Entry Points)

- 通常運用は `/gp-init`
- 改善・進化は `/gp-ab-init`
