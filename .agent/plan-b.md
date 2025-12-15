# Plan

## Goal

- Plan A と同じ「明るく希望に満ちたSaihAI UXを完成させつつ、`backend/.env` に API キーを入れれば実エージェント接続が可能な状態にする」ゴールだが、**PM→HR→RISK→GUNSHI の順で逐次的に LLM を呼び出し、それぞれの decision/risk から合意形成の流れを UI に正確に表現する**。

## Context

- system-prompts.md に PM/HR/RISK/GUNSHI それぞれの人格・ルールが定義済み。現状はモック/単発のままなので、実稼働に向けて各 agent の発話を順にシミュレートする必要がある。  
- Golden Profile の制約（Small Patch/Explainability/Plan before Patch）に則り、Plan B は「順序型 agent runner + UI log 表現」の変更だけに集中する。

## Approach

- `backend/app/ai/agent_runner.py`（新規）で system-prompts を読み込み、PM→HR→RISK→GUNSHI の順に prompt を投げ、JSON/構造化された回答をパースする `run_agent_sequence` を実装する。各ステップは `.env` の `LLM_PROVIDER`/`LLM_API_KEY`/`LLM_BASE_URL` を参照し、未設定時は現行モックにフォールバック（fallback モードで `simulate` を再計算／mock meeting log）。  
- `backend/app/api/simulate.py` は `run_agent_sequence` を呼び出し、各 agent の decision/risk/risk_reason を `meetingLog` へ格納、さらに `plans` に順化された `agents` オブジェクトを追加。`component_id` を `api.simulate.agent_sequence` として明示。
- UI 側（`frontend/src/app/pages/simulator.page.ts`）は overlay の meetingLog 表示を拡充。`agent_id` ごとに色分け（PM=blue, HR=green, RISK=rose, GUNSHI=gold）し、逐次実行中は animating log + spinner で「検証中」を表示。送信前に prompt preview ステップを追加（modal 内で `Run PM → ...` のステータスをドラッグ）。
- status indicator/overlay Chat で `prefers-reduced-motion` を尊重しつつ 3D/Canvas 背景を維持。`NeuralOrbComponent` は既存実装を再利用して GPU heavy にならないよう maintain。

## Risks & Unknowns

- 各 agent の出力が JSON 非準拠／部分失敗した場合の fallback（mock を代替）とログ記録。これを `agent_runner` で `retry` し、デグレ対応で `meetingLog` に `error` などを記録。  
- 逐次的な LLM 呼び出しは latency/cost が増えるため `.env` で `LLM_PROVIDER=mock` の切り替えを維持。  
- 実際の Bedrock / OpenAI との互換性（param/ベースURLが異なる）を `.env.example` に反映し、ドキュメントを `STRANDS_BEDROCK.md` などと統合するか検討。

## Verification

- Backend: `uv run python -m compileall -q app` + manual `uvicorn` run for sequential runner path (mock + actual).  
- Frontend: `npm run build` + manual `dev-start.bat` で overlay を開き、`Plan` ボタンから sequential log 発話が「PM → HR → RISK → GUNSHI」の順で出ること。  
- Manual: `.env` を用意した状態で `/simulator` を開き、prompt preview → 実行 → meeting log/plan selection で risk scores/decisions が表示されること。***
