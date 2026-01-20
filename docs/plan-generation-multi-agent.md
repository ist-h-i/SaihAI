# プラン生成: マルチAIオーケストレーション仕様

## 概要
- プラン生成時に PM/HR/RISK の3サービスを先に呼び出し、結果を統合して SaihAI-Gunshi-Orchestrator に渡す。
- Orchestrator の JSON 出力を既存の SimulationPlan (A/B/C) へ変換して返す。

## 呼び出し順
1. PM/HR/RISK に `{{data}}` を埋め込んだユーザープロンプトで個別評価 (JSON 出力)。
2. SaihAI-Gunshi-Orchestrator に `project_context` / `candidate_profile` / `pm_opinion` / `hr_opinion` / `risk_opinion` を埋め込んで最終プラン生成 (JSON 出力)。
3. Orchestrator 出力 `three_plans` を A/B/C の計画案へマッピング。

## 入力データ
- `data`: シミュレーションのコンテキスト全体 (project / team / metrics / pattern / requirement_result)。
- `project_context`: { project, metrics, pattern, requirement_result }
- `candidate_profile`: { team }

## モデル設定
- PM: temperature=1.0, max_tokens=3167
- HR: temperature=1.0, max_tokens=25240
- RISK: temperature=1.0, max_tokens=2000
- Gunshi Orchestrator: temperature=1.0, max_tokens=64000

## ログ出力 (プロンプト)
- 各ロール呼び出し直前に、置換済みの「組み立て済みプロンプト」をログ出力する。
- PM/HR/RISK: `{{data}}` を埋め込んだユーザープロンプト全文を出力。
- Gunshi: `project_context` / `candidate_profile` / `pm_opinion` / `hr_opinion` / `risk_opinion` を埋め込んだユーザープロンプト全文を出力。
- Gunshi のシステム命令も同時にログ出力する。

## 変換ルール (Orchestrator → SimulationPlan)
- `planType`: Plan_A/B/C → A/B/C
- `summary`: description (なければ gunshi_summary)
- `score`: recommendation_score
- `recommended`: is_recommended (なければ score 最大のプラン)
- `pros`: debate_summary の PM/HR/Gunshi を採用
- `cons`: debate_summary の Risk を採用
- `logs`: PM/HR/RISK の discussion_draft → opinion_summary → detailed_analysis の順で採用

## 例外時の挙動
- Bedrock 呼び出しに失敗した場合は既存のフォールバックプランを返す。
