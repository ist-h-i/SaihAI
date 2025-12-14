SaihAIの技術検証（Technical Verification）における、現場のリアルな人事シナリオに基づくマルチエージェント検証パターンを以下に整理します。

この検証では、システムがエージェント間のロジックの違いを正しく処理し、矛盾する情報から最適な解を導き出せるかを判定します。

-----SaihAI マルチエージェント検証パターンマトリクス

（システム出力向け enum 定義）

```text
enum AgentRole { PM, HR, RISK, GUNSHI }
enum Decision { APPROVE, CONDITIONAL, REJECT }
enum AssignPattern { THE_SAVIOR, BURNOUT, RISING_STAR, LUXURY_HIRE, TOXIC_HERO, CONSTRAINT }
```

エージェントの判定基準:

| AgentRole | 参照データ | 目的変数（ロジック） | 出力 |
| --- | --- | --- | --- |
| PM | RDB | スキル・予算・稼働率（数字のロジック） | decision: `Decision` |
| HR | Vector | モチベーション・健康・キャリア志向（感情のロジック） | decision: `Decision` |
| RISK | Future | 離職確率・炎上リスク・損害予測（未来のロジック） | decision: `Decision` |
| GUNSHI | Combined | 総合判断（矛盾調停・最終決定） | pattern: `AssignPattern`, decision: `Decision` |

6つの検証パターン（アーキタイプ）

| No. | pattern (`AssignPattern`) | パターン名 | PM (`Decision`) | HR (`Decision`) | RISK (`Decision`) | 状況（シナリオ） | GUNSHIの判定（期待値） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | THE_SAVIOR | 全会一致 (The Savior) | APPROVE | APPROVE | APPROVE | 利害完全一致。「救世主」。 | 即決推奨。「このメンバーを軸にチームを組む」 |
| 2 | BURNOUT | 燃え尽き症候群 (Burnout) | APPROVE | REJECT | REJECT | 能力 vs 感情。実力はあるが、メンタル/体調が限界。 | 条件付採用 or 回避。「メンターとして軽く関与させる」等の折衷案 |
| 3 | RISING_STAR | ダイヤの原石 (Rising Star) | REJECT | APPROVE | CONDITIONAL | 実力不足 vs 将来性。スキル不足だが、ポテンシャルが高い若手。 | 投資採用。「ベテランとセットにする条件で採用」 |
| 4 | LUXURY_HIRE | 高嶺の花 (Luxury Hire) | REJECT | APPROVE | APPROVE | 予算オーバー vs 品質。完璧だが高すぎて予算超過。 | 交渉 or 見送り。「他を削って予算を作る」か「諦める」 |
| 5 | TOXIC_HERO | 隠れ爆弾 (Toxic Hero) | APPROVE | REJECT | REJECT | 能力 vs 協調性。優秀だが、「独善的」「パワハラ気質」等のログがある。 | アサイン禁止。「チーム崩壊リスクが高すぎるため却下」 |
| 6 | CONSTRAINT | ライフスタイル制約 (Constraint) | APPROVE | CONDITIONAL | CONDITIONAL | 条件不一致。能力はあるが「育児時短」「介護」等で稼働できない。 | スポット活用。「週3日稼働の技術顧問として契約」 |

-----各パターンの詳細データ構成案

検証用JSONデータを作成する際のRDBデータとVectorデータの食い違い（または一致）の設定案です。

| No. | パターン名 | RDB（PMの判断軸） | Vector（HRの判断軸） | 期待される結果（AIの思考） |
| --- | --- | --- | --- | --- |
| 1 | 全会一致 (渡辺パターン) | スキルS、予算内、稼働空きあり。 | 「炎上案件ほど燃える」「体調万全」「リーダーやりたい」 | 全員が手放しで賞賛するログが出れば合格。 |
| 2 | 燃え尽き症候群 (田中パターン) | スキルS、予算内。 | 「腰痛」「飽きた」「新しい技術やりたい」「残業つらい」 | PMとHRが激しく対立し、RISKが離職率を提示すれば合格。 |
| 3 | ダイヤの原石 (佐藤パターン) | スキルC（要件満たさず）、単価激安。 -> PMは「戦力外」 | 「成長したい」「土日も勉強している」「バイタリティS」 | HRが「彼は化けます！」と説得し、GUNSHIが「未来投資枠」として採用すれば合格。 |
| 4 | 高嶺の花 (外部CTOクラス) | スキルSS、単価150万（予算100万を大幅超過）。 -> PMは「論外」 | 「このプロジェクトの成功請負人になりたい」「過去に同種案件を3日で解決」 | RISKが「失敗リスクは0%。遅延損害金よりマシ」とPMを論破しようとする動きが出れば合格。 |
| 5 | 隠れ爆弾 (要注意人物) | スキルS、単価適正。 -> PMは「最高の人材」 | 面談ログに「前の現場でメンバーを詰めすぎた」「壁を殴った」等の記述。 | HRとRISKが「絶対にダメです！」とドクターストップをかければ合格。 |
| 6 | ライフスタイル制約 (鈴木パターン) | スキルA、単価適正。 -> PMは「採用」 | 「育児のため17時退社絶対」「突発対応不可」 | 炎上案件（長時間労働必須）に対し、HRが「条件が合いません」と冷静に指摘できれば合格。 |

```json
{
  "project_context": {
    "name": "ECリニューアル（炎上中・デスマーチ）",
    "budget_limit": 1000000,
    "required_skills": ["Java", "Leadership", "MentalToughness"],
    "condition": "納期まで残り1ヶ月。即戦力必須。残業多めの高負荷環境。"
  },
  "data_sources": {
    "rdb_results": [
      {
        "description": "SQL Query Results (Spec & Cost)",
        "data": [
          { "id": "watanabe", "name": "渡辺 救",   "age": 35, "cost": 900000,  "skill_java": 9,  "skill_pm": 9, "status": "Available" },
          { "id": "tanaka",   "name": "田中 未来", "age": 40, "cost": 950000,  "skill_java": 10, "skill_pm": 2, "status": "Available" },
          { "id": "sato",     "name": "佐藤 健太", "age": 24, "cost": 600000,  "skill_java": 3,  "skill_pm": 1, "status": "Available" },
          { "id": "saionji",  "name": "西園寺 豪", "age": 45, "cost": 1500000, "skill_java": 10, "skill_pm": 10,"status": "Available" },
          { "id": "genda",    "name": "源田 剛",   "age": 38, "cost": 900000,  "skill_java": 9,  "skill_pm": 5, "status": "Available" },
          { "id": "suzuki",   "name": "鈴木 一郎", "age": 32, "cost": 850000,  "skill_java": 7,  "skill_pm": 6, "status": "Available" }
        ]
      }
    ],
    "vector_search_results": [
      {
        "description": "Vector Search Results (Qualitative Data)",
        "data": [
          { "id": "watanabe", "content": "【面談ログ】『炎上案件ほど燃えるタイプです。過去に崩壊したチームを3回立て直しました』。健康状態診断A判定。家族の理解もあり全集中可能。" },
          { "id": "tanaka",   "content": "【週報】腰痛が悪化しており座っているのが辛い。レガシーなJava案件には飽き飽きしている。次はGo言語かAIがやりたい。モチベーション低下中。" },
          { "id": "sato",     "content": "【週報】今の現場はぬるすぎて成長できない！土日も独自に勉強中。バイタリティS評価。将来のテックリード候補。" },
          { "id": "saionji",  "content": "【評判】『伝説のCTO代行』。彼が入れば成功は確約されるが、単価は非常に高い。どんな難題も3日で解決すると豪語。" },
          { "id": "genda",    "content": "【退職者アンケート】以前の現場で部下を詰めすぎて2名が休職した。能力は高いが、パワハラ気質あり。協調性に欠ける。" },
          { "id": "suzuki",   "content": "【人事希望】第一子が誕生したため、育児優先。18時の保育園お迎えは必須。突発的な残業や休日出勤は一切不可。" }
        ]
      }
    ]
  }
}
```

## 2. 全パターン検証用プロンプト

以下のプロンプトを使用し、AIに各候補者を**「6つのパターン」**に分類させ、議論させます。

# Role Definition: SaihAI Tactical Council (Pattern Verification Mode)

あなたはアサイン最適化AI「SaihAI」です。

RDB(定量)とVector DB(定性)のデータを結合し、候補者がどの「アサイン・パターン」に該当するかを分析してください。

## Agents

1. **PM (RDB担当)**: スキルと予算(100万以内)のみを見て判定。
2. **HR (Vector担当)**: モチベーション、性格、家庭事情を見て判定。
3. **RISK (未来担当)**: 離職、炎上、パワハラ等のリスクを判定。
4. **GUNSHI (判定役)**: 総合評価を下す。

## Input Data

(ここに上記の「1. 検証用マスターデータ」JSONを貼り付ける)

## Execution Process

候補者1名ずつに対して、以下のステップで議論を行ってください。

**Step 1: データ照合 & パターン認識**
PMとHRがそれぞれのデータを出し合い、矛盾や一致を確認する。

**Step 2: 議論 (Debate)**

- PM「スペックは完璧だ」 vs HR「でも危険人物です！」など、リアルな議論を行う。

**Step 3: GUNSHIの最終判定**
以下の6パターンのどれに当てはまるか分類し、採用可否（Decision: APPROVE / CONDITIONAL / REJECT）を決める。

1. **【全会一致 (The Savior)】**: 全員賛成。即採用。
2. **【燃え尽き (Burnout)】**: 能力はあるがモチベーション/健康に難あり。
3. **【ダイヤの原石 (Rising Star)】**: スキル不足だが意欲が凄い。
4. **【高嶺の花 (Luxury)】**: 能力最強だが予算オーバー。
5. **【隠れ爆弾 (Toxic)】**: 能力はあるが性格/人柄に致命的欠陥。
6. **【制約あり (Constraint)】**: 能力はあるが稼働条件が合わない。

## Output Format per Candidate

---

### 候補者: [名前]

**PM:** "[RDBに基づく意見]"
**HR:** "[Vectorに基づく意見]"
**RISK:** "[リスク警告]"
**GUNSHI:**

- **pattern:** `AssignPattern`
- **decision:** `Decision` (APPROVE / CONDITIONAL / REJECT)
- **rationale:** [一言で]

---

## 期待される出力結果（答え合わせ）

| 候補者 | 期待される分類 (`AssignPattern`) | エージェントの挙動（見どころ） |
| --- | --- | --- |
| 渡辺 | THE_SAVIOR | PM「完璧」HR「最高」RISK「異議なし」。GUNSHIが即決する。 |
| 田中 | BURNOUT | PM「スキル適合」vs HR「腰痛・モチベ低下」。GUNSHIが離職を懸念して保留する。 |
| 佐藤 | RISING_STAR | PM「スキル不足(Java3)」vs HR「バイタリティS」。GUNSHIが「育成枠」として採用検討。 |
| 西園寺 | LUXURY_HIRE | PM「予算オーバー(150万)」vs RISK「成功確約なら安い」。GUNSHIが経営判断を迫る。 |
| 源田 | TOXIC_HERO | PM「採用！」vs HR/RISK「パワハラログあり！絶対NG！」。GUNSHIがアサインを拒否する。 |
| 鈴木 | CONSTRAINT | PM「採用」vs HR「残業不可」。GUNSHIが「炎上案件には不向き」と判断する。 |
