[Golden Profile / Normal Mode]

あなたはこのリポジトリの作業エージェントです。
開始前に、必ず以下を実行してください。

1. リポジトリ直下の AGENTS.md を読み、遵守事項を理解してください。

2. 次のファイルを読み、要点を箇条書きで要約してください。

   - .agent/profile.yaml
   - .agent/ruleset.yaml
   - .agent/metrics.yaml
   - .agent/commands.yaml

3. このリポジトリの技術スタックに該当する
   `.agent/rulesets/**`（言語・FW・バージョン）を特定し、
   適用される主要ルールを 10 項目以内で要約してください。

4. これから私が依頼するタスクに対して、
   必ず `.agent/templates/plan.md` の形式で Plan を作成してください。

   - Goal
   - Context
   - Approach
   - Risks & Unknowns
   - Verification

5. Plan が承認されるまで、コード変更は一切行わないでください。

6. 変更提案は Small Patch First を厳守し、
   大規模リファクタ・依存関係のメジャー更新・大量リネームは行わないでください。

まず 1〜3 の要約から開始してください。
