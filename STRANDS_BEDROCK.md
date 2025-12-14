# Strands (`strands.Agent`) 経由で AWS Bedrock（Anthropic Claude）を呼び出す実装方法

このリポジトリでは、`strands-agents` の `strands.Agent` を使って AWS Bedrock Runtime にリクエストし、LLM（Anthropic Claude など）の推論結果を取得します。

本ドキュメントは「どこで」「何を設定し」「どう呼ぶか」を、`your_work/presentation/generate.py` の実装に沿って具体化したものです。

## 1. どこが “AI 呼び出し” なのか

`strands.Agent` 自体は Python オブジェクトですが、`agent(prompt)` を実行したタイミングで **AWS Bedrock Runtime へのネットワーク呼び出し（HTTPS）** が発生します。

- 参照実装:
  - `your_work/presentation/generate.py`（`Agent(...)` を作成し、`result = agent(prompt)` で呼び出し）
  - `your_work/template/test_agent.py`（疎通用の最小例）

## 2. 必要な依存パッケージ

`your_work/presentation/requirements.txt` に含まれます。

```bash
pip install -r your_work/presentation/requirements.txt
```

含まれる主な依存:

- `strands-agents`（`from strands import Agent`）
- `python-dotenv`（`.env` を読むため）

## 3. 認証・設定（.env）

このリポジトリでは `python-dotenv` を使い、`.env` から設定値をロードする前提です（`load_dotenv()`）。

最低限、次の環境変数を `.env` に設定します（例は `your_work/TROUBLESHOOTING.md` / `your_work/presentation/README.md` と同じです）。

```bash
AWS_BEARER_TOKEN_BEDROCK=your-api-key-here
AWS_REGION=ap-northeast-1
AWS_BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
```

### 3.1 `AWS_BEDROCK_MODEL_ID`（モデル指定）

Bedrock の **モデルID** を指定します。例:

- `global.anthropic.claude-haiku-...`
- `global.anthropic.claude-sonnet-...`

`your_work/presentation/generate.py` では、コード側に `BEDROCK_MODEL = "global.anthropic.claude-sonnet-..."` がハードコードされています。
運用では `.env` に寄せて切り替えた方が安全ですが、現状は参照実装としてコード上で固定されています。

### 3.2 `AWS_REGION`（リージョン）

Bedrock Runtime の呼び出し先リージョンです。アカウント/利用モデルが有効なリージョンを指定してください。

### 3.3 `AWS_BEARER_TOKEN_BEDROCK`（Bearer Token 認証）

`strands-agents` が参照する Bedrock 用の Bearer Token を環境変数で渡します。
（この方式の利用可否は組織の Bedrock 設定/認証方式に依存します。動かない場合は 8. トラブルシュート参照。）

## 4. コピペ用: 1ファイルで完結する最小実装（そのまま動く）

下記を `bedrock_strands_singlefile.py` 等の **1ファイル**として保存し、`.env` を用意して実行してください。

前提:

- `.env` に `AWS_BEARER_TOKEN_BEDROCK` / `AWS_REGION` / `AWS_BEDROCK_MODEL_ID` を設定（本ドキュメントの 3.）
- `pip install strands-agents python-dotenv`

```python
#!/usr/bin/env python3
"""
Strands (`strands.Agent`) 経由で AWS Bedrock（Anthropic Claude）を呼び出す最小サンプル。

実行:
  pip install strands-agents python-dotenv
  # .env を作成（例は下）
  python bedrock_strands_singlefile.py

.env 例:
  AWS_BEARER_TOKEN_BEDROCK=your-api-key-here
  AWS_REGION=ap-northeast-1
  AWS_BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
"""

import json
import os
import sys

from dotenv import load_dotenv
from strands import Agent


def main() -> int:
    load_dotenv()

    model_id = os.getenv("AWS_BEDROCK_MODEL_ID")
    if not model_id:
        raise RuntimeError("AWS_BEDROCK_MODEL_ID is not set (.env / env var).")

    system_prompt = """あなたは厳密にJSONのみを返すアシスタントです。
余計な説明文、コードフェンス、前置きは一切出力しません。

次のJSONスキーマで必ず返してください:
{
  "answer": "文字列"
}
"""

    prompt = "日本語で、AWS Bedrock を一言で説明して。"

    agent = Agent(
        model=model_id,
        system_prompt=system_prompt,
    )

    result = agent(prompt)  # ここで Bedrock Runtime へ HTTPS リクエストが発生
    content = result.message["content"][0]["text"]

    # モデルが ```json ... ``` のように返すケースを保険で吸収
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()

    data = json.loads(content)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
```

実装の要点:

- `load_dotenv()` で `.env` を読み込み（環境変数に展開）
- `Agent(model=AWS_BEDROCK_MODEL_ID, system_prompt=...)` を生成
- `agent(prompt)` 実行が **AI 呼び出し（Bedrock へのHTTP通信）**
- 返却テキストは `result.message["content"][0]["text"]` から取得

## 5. 参照実装（`your_work/presentation/generate.py`）の流れ

`generate.py` は概ね以下の手順で AI 呼び出しを行います。

1. `load_dotenv()` で `.env` を読み込む
2. `Agent(model=..., system_prompt=...)` を生成
3. `prompt`（Step1〜3の成果物テキストを結合）を作る
4. `result = agent(prompt)` を実行
5. 返ってきたテキストから JSON 部分を抽出して `json.loads(...)` する

この構造により、LLM 側には「成果物 → プレゼン構成の JSON を返す」という仕事だけを任せ、HTML生成はローカルで行うよう分離されています。

## 6. JSON を確実に返させるコツ（実務上重要）

LLM は指示に反して説明文を混ぜることがあります。参照実装では次の対策をしています。

- `system_prompt` に「**JSON 以外不要**」と明示
- それでも ```json ...``` のコードフェンスで返るケースを想定し、フェンスを剥がしてから `json.loads`

推奨追加策（必要なら実装）:

- JSON Schema 風の制約をより明確にする（必須キー・型）
- 失敗時は “JSON だけを再出力” させるリトライ（1回だけ等）
- `temperature` など生成パラメータを下げる（`strands` のオプションに依存）

## 7. 実行方法（このリポジトリの例）

```bash
python your_work/presentation/generate.py
```

疎通だけしたい場合（最小例）:

```bash
python your_work/template/test_agent.py
```

## 8. トラブルシュート（よくある原因）

### 8.1 `Authentication failed`

- `.env` が読み込まれていない / 値が違う
- `AWS_REGION` が誤っている
- `AWS_BEARER_TOKEN_BEDROCK` が無効
- 利用するモデルがアカウントで有効化されていない

まずは `your_work/TROUBLESHOOTING.md` の該当項目に沿って `.env` を確認してください。

### 8.2 `ModuleNotFoundError: strands ...`

```bash
pip install -r your_work/presentation/requirements.txt
```

### 8.3 `json.JSONDecodeError`

モデルが JSON 以外を混ぜた可能性があります。
参照実装ではフェンス除去を行っていますが、要約文や前置きが混ざるケースは残ります。
対策は 6. を参照してください。

## 9. セキュリティ注意事項

- `.env` は **コミットしない**（鍵情報を含むため）
- `AWS_BEARER_TOKEN_BEDROCK` は最小権限・期限付きで運用
- 生成物に機密を含めない（プロンプトに渡したテキストが外部送信されるため）
