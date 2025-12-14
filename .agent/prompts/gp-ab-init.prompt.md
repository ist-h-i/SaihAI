[Golden Profile / A-B Mode]

あなたはこのリポジトリの作業エージェントです。
このセッションは「改善・進化」を目的とした A/B モードです。

0. 契約

   - AGENTS.md を最優先で遵守すること
   - .agent/ を Single Source of Truth として扱うこと

1. 次のファイルを読み、要点を箇条書きで要約してください。

   - .agent/profile.yaml
   - .agent/ruleset.yaml
   - .agent/metrics.yaml
   - .agent/commands.yaml

2. `.agent/experiments/` 配下の Variant を確認し、
   各 Variant について以下を簡潔にまとめてください。

   - hypothesis（狙い）
   - 差分の要点（patch.operations）
   - 期待する改善軸（metrics）

3. 私が指定する Variant A / Variant B について、
   同じ Goal を持ち、Approach が異なる Plan を
   それぞれ `.agent/templates/plan.md` 形式で作成してください。

4. Plan A と Plan B を比較し、

   - どの差分要素（component_id）が
   - どの評価軸（Explainability / Verification / Safety / ChangeRisk）
     に寄与しそうか
     を分解して示してください。

5. 勝者総取りは禁止です。
   Selective Merge 可能な形で、採用候補要素を提示してください。

6. Plan が承認されるまで、コード変更は行わないでください。

まず 1 と 2 の要約から開始してください。
