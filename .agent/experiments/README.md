# experiments/

このディレクトリは、A/B テストのための **差分 Variant（実験プロンプト）** を置く場所です。

## 重要ルール

- ここに置くのは **差分のみ**（全文コピー禁止）
- `rulesets/`, `templates/`, `checklists/`, `commands/`, `metrics/` に対する **パッチ（patch.operations）** として表現します
- 勝った要素は Selective Merge で抽出し、Promotion Gate を通して `rulesets/` 等へ昇格させます
- 金融/公共などの厳格環境では、このディレクトリは **ローカル専用（共有しない）** 運用が可能です

## バリデーション

`schemas/experiment.schema.json` に準拠してください。
