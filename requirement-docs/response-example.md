{
  "analysis_meta": {
    "candidate_name": "string",
    "debate_intensity": "string (Low/Mid/High)"
  },
  "three_plans": [
    {
      "id": "Plan_A",
      "is_recommended": "boolean",
      "recommendation_score": "number (0-100)",
      "risk_score": "number (0-100)",
      "risk_reward_ratio": "string",
      "description": "string (具体的なアサイン変更内容)",
      "predicted_future_impact": "string (将来の影響予測)",
      "final_judgment": {
        "decision": "採用/不採用/条件付",
        "total_score": "number (0-100)",
        "gunshi_summary": "string (このプランにおける最終的な総括/30〜40文字程度)"
      },
      "debate_summary": [
        { "speaker": "PM", "content": "string (15-20文字)" },
        { "speaker": "HR", "content": "string (15-20文字)" },
        { "speaker": "Risk", "content": "string (15-20文字)" },
        { "speaker": "Gunshi", "content": "string (例：総合スコア 20。判断を保留します。)" }
      ]
    },
    {
      "id": "Plan_B",
      "is_recommended": "boolean",
      "recommendation_score": "number (0-100)",
      "risk_score": "number (0-100)",
      "risk_reward_ratio": "string",
      "description": "string",
      "predicted_future_impact": "string",
      "final_judgment": {
        "decision": "採用/不採用/条件付",
        "total_score": "number (0-100)",
        "gunshi_summary": "string (30〜40文字程度)"
      },
      "debate_summary": [
        { "speaker": "PM", "content": "string" },
        { "speaker": "HR", "content": "string" },
        { "speaker": "Risk", "content": "string" },
        { "speaker": "Gunshi", "content": "string (例：総合スコア 85。推奨に値します。)" }
      ]
    },
    {
      "id": "Plan_C",
      "is_recommended": "boolean",
      "recommendation_score": "number (0-100)",
      "risk_score": "number (0-100)",
      "risk_reward_ratio": "string",
      "description": "string",
      "predicted_future_impact": "string",
      "final_judgment": {
        "decision": "採用/不採用/条件付",
        "total_score": "number (0-100)",
        "gunshi_summary": "string (30〜40文字程度)"
      },
      "debate_summary": [
        { "speaker": "PM", "content": "string" },
        { "speaker": "HR", "content": "string" },
        { "speaker": "Risk", "content": "string" },
        { "speaker": "Gunshi", "content": "string (例：総合スコア 40。リスクを注視すべきです。)" }
      ]
    }
  ]
}

ーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーー

1. 全体構造のイメージ
大きな箱（全体）の中に、「分析のメタ情報」と「3つのプランの配列」が入っています。

2. analysis_meta（共通情報）
画面のどこかに常に表示しておく情報です。
candidate_name: 対象者の名前。
debate_intensity: 議論の白熱度（Low/Mid/High）。演出（BGMやエフェクトの強弱など）に使用します。

3. three_plans（プランごとの詳細情報）
配列の要素（Plan_A, B, C）ごとに、以下の情報がパッケージ化されています。タブを切り替えた際、ここにある情報をそのまま画面に流し込むだけでUIが完成します。
基本パラメータ:
is_recommended: このプランが「軍師のイチオシ」かどうか（バッジ表示用）。
recommendation_score / risk_score: 推奨度とリスク度の数値（グラフ用）。
risk_reward_ratio: 「ハイリスク・ハイリターン」などのラベル。
description: このアサイン案の具体的な内容。
predicted_future_impact: 将来の影響予測（短文）。
final_judgment（軍師の最終判定）:
decision: 採用 / 不採用 / 条件付。判定結果のメインラベル。
total_score: 軍師の総合点（数値）。
gunshi_summary: 30〜40文字の短い総括。判定理由の要約です。
debate_summary（チャット・議論ログ）:
PM、HR、Risk、そしてGunshi（軍師）の4名による発言リストです。
Gunshiの発言内: ここにも「総合スコア 〇〇」という文言が含まれるため、チャットの最後を締めくくるセリフとしてそのまま表示できます。
