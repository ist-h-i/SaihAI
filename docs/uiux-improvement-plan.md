# UI/UX 大規模改善計画（SaihAI） Issue #29

作成日: 2026-01-05  
対象: `frontend/`（Angular + Tailwind）  
主要ルート（現状）: `/login` `/dashboard` `/simulator` `/genome`（`frontend/src/app/app.routes.ts`）

---

## 目的/ゴール

- 「文字で説明している箇所が多すぎて疲れる」状態を解消し、見ただけで次の操作が分かる UI/UX へ寄せる。
- サイハイくんの画像表情と発言内容の整合性を上げ、感情表現の一貫性（体系/ルール/実装）を作る。
- 「モダン・エネルギッシュ・スマート・インテリジェンス」なトーン&マナーを具体ルール（色/タイポ/余白/コンポーネント/モーション/アクセシビリティ）に落とし込む。
- 後続の実装 Issue に分割できる粒度で、課題と改善案を整理する。

## 非ゴール

- UI 実装やデザイン制作（Figma、画像制作）の完了。
- AB テスト/ユーザーテストの実施、KPI 達成の保証。
- UI/UX に直接関係しない大規模な仕様変更。

---

## 背景/現状（リポジトリから確認できた範囲）

- 画面構成はルート単位で 4 画面（`frontend/src/app/pages/*.page.ts`）。
- サイハイくんの発話 UI は `app-haisa-speech`（`frontend/src/app/components/haisa-speech.component.ts`）。
  - `tone`（`neutral|info|success|warning|error`）→デフォルト `emotion` の割当あり。
- `frontend/src/app/pages/simulator.page.ts` には別の `HaisaEmotion` 定義と画像マッピングがあり、表情体系が重複。
- 画像アセットが `frontend/src/assets/saihaikun` と `frontend/public/saihaikun` に分散し、命名揺れ（例: `exprosion.png`）が存在。
  - 現状の Angular `assets` 設定では `public/` は favicon のみコピーしており、`public/saihaikun` は配信対象外（`frontend/angular.json`）。
- Tailwind のテーマ拡張は未整備（`frontend/tailwind.config.js` の `extend` が空）。一方で `frontend/src/styles.css` には CSS 変数（`--surface-*`）など独自トークンが存在。

---

## 主要導線（現状）

1. `/login`: ログイン（開発用アカウント前提）→ `/dashboard` へ遷移（`frontend/src/app/pages/login.page.ts`）。
2. `/dashboard`: KPI / アラート / AI 提案（松竹梅）/ 承認待ち / 人材マップ / Watchdog（`frontend/src/app/pages/dashboard.page.ts`）。
3. `/simulator`: 案件/メンバー選択 → AI 自動編成 → 結果 → 介入（HITL）オーバーレイ（`frontend/src/app/pages/simulator.page.ts`）。
4. `/genome`: 検索/スキルフィルタ → 表/カードで一覧 → Hover で詳細（`frontend/src/app/pages/genome.page.ts`）。

---

## 横断課題（全画面共通）

以降の課題は、各画面にも重複して現れます。画面別に直す前に「共通の方針」を決めると、改善が加速します。

### 1) 文字情報過多（Symptoms / Cause / Impact / Evidence）

- 症状: 画面上に“説明文・補足・ログ的出力”が多く、視線が散り「次に何をすれば良いか」が瞬時に分からない。
- 原因: 情報の階層（要約→詳細）がなく、同じ重要度で並列表示される。状態（空/ロード/成功/失敗）ごとの UI テンプレートが未整備。
- 影響: 使い始めの学習コスト増、操作疲れ、意思決定までの時間増。
- 根拠:
  - `/dashboard` 冒頭説明 + KPI 群 + 複数カードが同時に主張（`frontend/src/app/pages/dashboard.page.ts`）。
  - `/simulator` 入力→結果→ログ→オーバーレイの情報量が段階化されていない（`frontend/src/app/pages/simulator.page.ts`）。

### 2) “次アクション”の提示不足

- 症状: 空状態や「準備中」に対して、ユーザーが取れる行動が明示されない（例: “提案を準備中です” で止まる）。
- 原因: 状態遷移設計（状態→主 CTA→補助 CTA→詳細）が未定義で、発話/コピーが“説明”に寄っている。
- 影響: 画面滞留、離脱、誤操作。
- 根拠: `/dashboard` の空状態や、`/simulator` の未選択状態メッセージ（`frontend/src/app/pages/dashboard.page.ts`, `frontend/src/app/pages/simulator.page.ts`）。

### 3) コンポーネント/トークンの統一不足（デザインのブレ）

- 症状: `surface-panel` など独自クラスと Tailwind のユーティリティが混在し、将来の改修で統一が難しくなる。
- 原因: Tailwind のテーマ拡張や「デザイン・トークン定義（色/余白/角丸/影/モーション）」が未整備。
- 影響: 見た目の一貫性低下、変更コスト増、アクセシビリティ対応の抜け漏れ増。
- 根拠: `frontend/tailwind.config.js`（`extend` 空）と `frontend/src/styles.css`（独自トークン）の並存。

### 4) サイハイくんの“感情×文脈”整合の未定義

- 症状: 同じ `tone`/状態でも表情が揺れる、または発言と表情が噛み合わない。
- 原因: emotion 体系が重複し、割当ルールが暗黙。画像アセットも分散/命名揺れ。
- 影響: 違和感、信頼感の低下、キャラクター活用が逆効果になる。
- 根拠:
  - `frontend/src/app/components/haisa-speech.component.ts` と `frontend/src/app/pages/simulator.page.ts` の定義重複。
  - `frontend/src/assets/saihaikun` と `frontend/public/saihaikun` の分散。

---

## 画面別課題と改善案（症状/原因/影響/根拠）

### `/login`

#### 課題: 初見ユーザーに対して情報量が多い

- 症状: 価値説明・演出・フォーム補足が同時に並び、視線誘導が弱い。
- 原因: “ログイン完了までの最短経路”が UI 上で最優先になっていない（情報階層が浅い）。
- 影響: ログイン前の離脱/入力ミス増。
- 根拠: `frontend/src/app/pages/login.page.ts` のヒーロー文 + 2 カード + 説明 speech の併存。
- 改善案:
  - 要約ファースト: ヒーロー文は 1 行 + 1 行（補助）に圧縮し、詳細は折りたたみに。
  - フォームに集約: “この環境でできること”はフォーム内の 3 点箇条書き（アイコン付き）に統合。
  - 発話は 1 個に制限: `app-haisa-speech` を「入力のヒント」または「安心感（ログイン後の期待）」のどちらかに寄せる。

### `/dashboard`

#### 課題: 重要情報（アラート/提案/承認待ち）の優先順位が曖昧

- 症状: KPI・アラート・提案・承認待ち・人材マップが同等の密度で並び、判断の起点が分からない。
- 原因: “今日の意思決定”を 1 つに絞って提示する設計（Primary KPI / Primary CTA）がない。
- 影響: 視線移動が増え、介入までの導線が長くなる。
- 根拠: `frontend/src/app/pages/dashboard.page.ts` の `mt-6 grid` ブロック群。
- 改善案:
  - トップに「今日の 1 件」: アクティブアラート（or 推奨提案）を 1 枚の大カードに統合し、主 CTA を配置（例: “介入へ”）。
  - 提案は 3 つ同時表示→段階化: 推奨のみ展開、残りは “他の提案” として折りたたみ/スワイプ。
  - 承認待ちは “0件/要対応/緊急” のステータス表示に寄せ、リストは詳細として開く。

#### 課題: サイハイくん発話が“ログ”になりやすい

- 症状: 提案メッセージ（`p.description`）が長い場合、読むコストが高い。
- 原因: 発話が「要約 + 根拠 + 次アクション」を分離していない。
- 影響: 読み飛ばし、提案の価値が伝わらない。
- 根拠: `frontend/src/app/pages/dashboard.page.ts` の `app-haisa-speech` へ `message=p.description` を直渡し。
- 改善案:
  - `title` を “結論（何をするか）”、`message` を “理由 2 点 + 次アクション 1 点” に固定（テンプレ化）。
  - 長文は “詳細（根拠ログ）” に退避し、クリックで展開。

### `/simulator`

#### 課題: 入力→結果の段階が UI 上で見えにくい

- 症状: 入力欄と結果欄は左右にあるが、状態（未選択/選択中/実行中/結果/介入）が明確に段階化されていない。
- 原因: Stepper（段階 UI）や空状態テンプレがなく、説明文で補っている。
- 影響: 未選択のまま迷う、実行中の不安、結果の読み取りコスト増。
- 根拠: `frontend/src/app/pages/simulator.page.ts` の未選択メッセージ + `running...` のみ。
- 改善案:
  - 段階 UI（例: 1.選択 → 2.AI実行 → 3.結果 → 4.介入）を上部に表示。
  - 実行中は skeleton + “何をしているか” を 1 行表示（進捗ログは詳細へ）。
  - 空状態は“例/デモ起動”へ誘導（既存の `?demo=alert|manual` を UI から叩けるようにする）。

#### 課題: 介入（HITL）オーバーレイで情報が詰まりやすい

- 症状: Agent Log / プラン選択 / チャットが同一画面にあり、目的が分散する。
- 原因: 介入フェーズの情報設計（見る→選ぶ→指示→承認）が 1 画面で並列。
- 影響: 重要な意思決定点（どのプランを採るか）が埋もれる。
- 根拠: `frontend/src/app/pages/simulator.page.ts` の overlay テンプレート（Agent Log + Plan buttons + Chat）。
- 改善案:
  - レイアウト分割: 左=要約（KPI/結論/根拠の短文）、右=アクション（プラン選択→指示→承認）。
  - Agent Log は折りたたみ（“根拠ログ”）へ。
  - “承認”の意味を UI 上で明確化（空欄=承認は危険。承認ボタンを別で用意し、入力欄は “条件を追加” に限定）。

### `/genome`

#### 課題: Hover 前提の詳細表示（アクセシビリティ/モバイル対応）

- 症状: “Hover で詳細” が必須で、タッチ端末やキーボード操作で使いにくい。
- 原因: 主要操作が hover に依存し、フォーカス/クリックでの代替が弱い。
- 影響: 利用環境による体験差、アクセシビリティ低下。
- 根拠: `frontend/src/app/pages/genome.page.ts` のカード（表裏）と “Hover で詳細” 文言。
- 改善案:
  - クリックで詳細（Drawer/Modal/別ページ）を開く導線を標準化。
  - “一覧で見る情報”と“詳細で見る情報”の分離（要約→詳細）。

---

## 文字情報削減の置換パターン集（実装に落とすための型）

### パターン A: 要約 → 詳細（Progressive Disclosure）

- 使いどころ: 提案文、ログ、根拠、説明コピー全般。
- 実装案:
  - “結論 1 行 + 理由 2 点 + 次アクション 1 点” をデフォルト表示。
  - 長文/ログは `details/summary`、アコーディオン、または “詳細” ボタンで展開。

### パターン B: 空状態テンプレ（Empty State）

- 使いどころ: “準備中/0件/未選択” の全箇所。
- 実装案:
  - 見出し（状態）→ 1 行説明 → 主 CTA（次アクション）→ 補助 CTA（デモ/ヘルプ）。
  - 例: `/dashboard` の “提案を準備中” は “再読み込み” + “シミュレーターへ” を提示。

### パターン C: “次アクション”を固定スロット化

- 使いどころ: `/dashboard` 上部、`/simulator` 結果、オーバーレイ。
- 実装案:
  - 画面右上（または固定バー）に “Next” を 1 つだけ置く。
  - それ以外の行動は overflow メニューに退避。

### パターン D: アイコン+ツールチップ（言葉の圧縮）

- 使いどころ: KPI、ステータス、ラベル、補足説明。
- 実装案:
  - ラベルを “短い単語 + アイコン” にし、説明文は hover/focus のツールチップへ。
  - ただしキーボード/タッチ代替（focus/タップで表示）を用意する。

---

## サイハイくん整合（emotion 体系・割当ルール・アセット整理）

### 現状の問題（症状/原因/影響/根拠）

- 症状: 同じ状況でも表情が揺れたり、表情が説明と合わない。
- 原因:
  - emotion の定義/マッピングが複数箇所に存在（`HaisaSpeechComponent` と `SimulatorPage`）。
  - アセットが分散し、命名揺れ（`exprosion.png` 等）で意図が壊れやすい。
- 影響: キャラクターの信頼低下、UI のノイズ化。
- 根拠:
  - `frontend/src/app/components/haisa-speech.component.ts`
  - `frontend/src/app/pages/simulator.page.ts`
  - `frontend/src/assets/saihaikun/*`, `frontend/public/saihaikun/*`

### 目標（Haisa UX 原則）

1. 表情は「状態の要約」を担う（発話本文の代替ではない）。
2. emotion は **少数精鋭**（8〜10）に固定し、例外は増やさない。
3. 割当は「ルール優先・手動 override 可能」にする（暗黙ルール禁止）。

### emotion 体系（提案）

まずは既に UI 上で使われている画像（`frontend/src/assets/saihaikun`）を正とし、そこに統一します。

| emotion | ラベル（表示名） | 想定シーン | 既存画像 |
|---|---|---|---|
| `standard` | 通常 | 既定/待機 | `standard.png` |
| `hope` | 期待 | 情報共有/次の一手 | `hope.png` |
| `joy` | 喜び | 成功/好転 | `joy.png` |
| `relief` | 安心 | 承認完了/安定 | `relief.png` |
| `anxiety` | 不安 | エラー/警告/リスク | `anxiety.png` |
| `energy` | 活力 | 実行中/前進 | `energy.png` |
| `effort` | 決意 | 介入開始/方針決定 | `effort.png` |
| `haste` | 焦り | 緊急対応/期限 | `haste.png` |
| `explosion` | 爆発 | 重大アラート/危機 | `explosion.png` |

> `frontend/public/saihaikun/*` にある追加画像（`excited.png`, `trouble.png` 等）は、配信対象外かつ用途が未定義のため、まずは整理対象として棚卸し（後述）。

### 割当ルール（tone/状態/イベント → emotion）

最低限、次の 2 層で決めます。

1) `tone` によるデフォルト（既存の方向性を維持）  
`neutral→standard`, `info→hope`, `success→relief`, `warning→haste`, `error→anxiety`

2) 状態/イベントによる override（例）

- Loading/実行中: `energy`（“動いている”を表す）
- 決断/介入開始: `effort`
- リスク高（しきい値）: `anxiety` → `explosion`（重大度で段階）
- 好転/成果: `joy` / `relief`（「達成」と「安堵」を使い分け）

### 実装整理方針（案）

- 単一のソース・オブ・トゥルース化:
  - `HaisaEmotion` の型、ラベル、画像マッピング、デフォルト割当を `frontend/src/app/core/haisa-emotion.ts` に集約。
  - `HaisaSpeechComponent` と `/simulator` のオーバーレイが同じ定義を参照。
- アセット整理:
  - `frontend/src/assets/saihaikun/` に統一し、`public/saihaikun/` は棚卸し後に削除/移動。
  - 命名は `kebab` ではなく現行（`standard.png` 等）を維持し、`exprosion.png` は `explosion.png` に正規化（参照箇所も修正）。

---

## トーン&マナー（Modern / Energetic / Smart / Intelligence）指針

### デザイン原則（UI を判断できる状態に寄せる）

- 1 画面 1 ゴール: “今日の意思決定/次アクション” を 1 つに絞る。
- 3 レイヤー: 要約（常時）/ 詳細（必要時）/ ログ（調査時）を分離する。
- Smart: 情報は短く、根拠は深く。操作は少なく、戻れる。
- Energetic: 微細なモーションとグラデーションで“生きている”を表現。ただし `prefers-reduced-motion` を尊重。

### トークン設計（提案）

Tailwind の `theme.extend` を使い、色/余白/影/角丸/フォーカスをトークン化します。現状の CSS 変数（`--surface-*`）は、トークンの実体として維持してもよいです。

- Color:
  - Primary: indigo/sapphire 系（現状の `indigo-600` 周辺）
  - Accent: cyan/fuchsia（既存の login の雰囲気を踏襲）
  - Semantic: success=emerald, warning=amber, danger=rose
- Typography:
  - 見出し: `tracking-tight` を基準に 2 段階（h1/h2）へ抑制
  - 本文: `text-sm` / 注釈: `text-xs` を標準化（`text-[11px]` の乱用を減らす）
- Spacing:
  - カード内余白は `p-4` を基準に、密度を 2 段階（compact/regular）
- Motion:
  - “強いアニメ”はアラート/推奨など目的がある箇所だけ（常時点滅は避ける）

### コンポーネント指針（置換の単位）

- Cards: `surface-panel` をベースに variant（default/interactive/alert）を定義
- Buttons: primary/secondary/ghost/destructive を固定
- Badges: status（RISK/GROWTH/AI推奨）を共通化
- Forms: input/select の focus ring とエラー表示を共通化
- Overlay/Modal: “閉じる”操作（Esc/フォーカストラップ）を必須化

### アクセシビリティ（最低限のルール）

- キーボード操作: hover 前提を排除し、focus で同等操作ができること。
- コントラスト: 重要情報（CTA/アラート）は背景と十分な差を確保する。
- ラベル: アイコンのみのボタンには `aria-label` を付与（現状の一部は対応済み）。
- Motion: `prefers-reduced-motion` は全アニメに適用（現状は一部のみ）。追加分も同等に。

---

## ロードマップ（Quick wins / 短期 / 中期）

### Quick wins（P0 / S: 〜数日）

- 空状態テンプレを導入し、“次アクション” を必ず出す（`/dashboard`, `/simulator`）。
- 提案文/ログを “要約→詳細” に段階化（折りたたみの導入）。
- サイハイくんの emotion 定義を 1 箇所に集約（重複解消の着手）。

### 短期（P0〜P1 / M: 1〜2週）

- Tailwind トークン整備（色/影/余白/角丸/フォーカス）+ 共通コンポーネント化。
- `/simulator` の介入オーバーレイを「見る→選ぶ→指示→承認」に分割（UI/コピー含む）。
- `/genome` の詳細表示を hover 依存から脱却（drawer/modal/詳細ページ）。

### 中期（P1〜P2 / L: 2〜4週）

- “意思決定の流れ”に合わせた IA（情報設計）を再編（/dashboard 起点の導線最適化）。
- データ可視化（人材マップ/リスク/成長）を再設計し、文字依存をさらに減らす。
- UI のアクセシビリティ監査（focus/contrast/読み上げ）を CI のチェックに組み込む。

---

## 実装フェーズの記録（Issue #31 / 2026-01）

### 実装済み（Quick wins + 短期）

- 共通 UI: 空状態テンプレ / 要約→詳細 / 次アクション枠 / 段階 UI を整理し、各画面で統一。
- `/dashboard`: 今日の 1 件カード、提案の要約→詳細化、承認待ちと Watchdog の段階表示を追加。
- `/simulator`: Stepper 追加、実行状態の段階化、介入オーバーレイを「見る→選ぶ→指示→承認」に分割。
- `/genome`: Hover 依存を廃止し、クリックで詳細パネルを開く UI に変更。
- `/login`: コピー量を圧縮し、フォーム内に “この環境でできること” を集約。
- サイハイくん: emotion 定義を `frontend/src/app/core/haisa-emotion.ts` に集約し、アセットを `frontend/src/assets/saihaikun` に統一。
- Tailwind トークン（色/影/角丸/余白/フォーカス）を `frontend/tailwind.config.js` と CSS 変数で整備。
- Playwright 証跡シナリオに UI 主要導線を追加（`evidence/scenarios.json`）。

### 未着手 / 申し送り（中期以降）

- 情報設計（IA）の再編（/dashboard 起点の導線最適化）。
- 可視化の再設計（人材マップ/リスク/成長のグラフィック化）。
- アクセシビリティ監査と CI への自動チェック組み込み。

---

## 証跡（Playwright）方針（提案）

UI 改修を継続的にレビューできるよう、以下を “基準シナリオ” として撮影できる状態を作ります。

- `login`: 初期表示、エラー表示（入力ミス）
- `dashboard`: アクティブアラートあり/なし、提案あり/なし
- `simulator`: デモ（`?demo=alert` / `?demo=manual`）でオーバーレイまで
- `genome`: フィルタ適用、詳細表示

現状 `tests/e2e/*` は sandbox 制約で `describe.skip` のため、CI ランナー（ブラウザ実行可能）で再有効化する運用が前提です。

---

## 受け入れ基準（本ドキュメントのチェック）

- 画面別（`/login`, `/dashboard`, `/simulator`, `/genome`）に課題が整理され、各課題に「症状/原因/影響/根拠」がある。
- 文字情報削減の方針が、置換パターン（要約→詳細、空状態、次アクション固定、アイコン+ツールチップ）として明記されている。
- サイハイくんの表情体系（emotion 一覧）と割当ルール（tone/状態/イベント→emotion）、整理方針（重複解消/アセット統一）がある。
- トーン&マナーが具体ルール（色/タイポ/余白/コンポーネント/モーション/アクセシビリティ）として提示されている。
- 改善項目が優先度付きで並び、ロードマップがある。
