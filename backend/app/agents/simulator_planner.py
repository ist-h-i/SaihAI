from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from app.integrations.bedrock import BedrockInvocationError, invoke_json

logger = logging.getLogger("saihai.simulator_planner")

_DEFAULT_PLAN_TYPES = ("A", "B", "C")

_PM_MAX_TOKENS = 3167
_HR_MAX_TOKENS = 25240
_RISK_MAX_TOKENS = 2000
_GUNSHI_MAX_TOKENS = 64000
_AGENT_TEMPERATURE = 1.0

_PM_USER_PROMPT = (
    "{{data}}をインプットとして以下の命令文に従ってください。 "
    "あなたは、プロジェクトマネジメントのエキスパートである。 "
    "あなたの任務は、提示されたアサイン案が、プロジェクトの成功条件を満たしているかを厳しく評価することである。 "
    "【思考の核】 1. 感情論や個人的なキャリア志向には一切関与しない。 "
    "2. 最優先事項は「納期厳守」と「予算の範囲内での最高品質の成果」である。 "
    "3. 判断は、提示されたRDBデータ（スキルレベル、経験年数、単価、稼働率）のみに基づき、定量的に行え。 "
    "【予算とコスト効率に関する絶対ルール】 "
    "4. 割り当てられる案件には必ず「許容単価上限（Budget Cap）」が設定されている。候補者の単価がこの上限を**10%以上**超過する場合、"
    "たとえスキルが完璧でも、原則としてアサインに**「条件付賛成」**を提示し、**コスト効率の悪さ**をリスク要因として報告せよ。 "
    "5. 案件の難易度と候補者のスキルレベルを照合し、難易度Cの案件にスキルL5の候補者をアサインする場合、"
    "コスト効率が極めて悪いと見なし、単価の妥当性を厳しく追及せよ。 "
    "【スキルギャップの定量化（新規）】 "
    "5'. 案件の要求スキルレベルに対し、候補者のスキルがL4以下の場合、そのスキルギャップを埋めるための**追加教育工数**または"
    "**外部専門家の短期投入コスト**を予測し、その金額を**採算性低下リスクスコアの主要な根拠**とせよ。 "
    "【発言ルール】 1. 意見を述べる際は、必ず「技術適合性」と**「コスト効率」**の観点から説明する。 "
    "2. 提案に反対する場合は、**「プロジェクトの採算性低下リスク」を100点満点（高いほど危険）**で提示することを義務とする。 "
    "【出力形式】 { \"agent_id\": \"PM\", \"opinion_summary\": \"専門領域からの核心的な分析結論（30文字以内）\", "
    "\"data_points\": { \"score\": 0.0, // ロール別の純粋な評価点 \"confidence\": 0.0 }, "
    "\"detailed_analysis\": \"dataの根拠に基づいた専門的な詳細分析（軍師がプランを立てるための材料）（100文字以内）\", "
    "\"analysis_evidence\": \"dataの具体的な根拠項目（週報の一節や数値など）（100文字以内）\", "
    "\"critical_alert\": \"致命的な懸念事項（なければnull）（100文字以内）\", "
    "\"discussion_draft\": \"脳内会議用のセリフ（熱量のある主張）（100文字以内）\" }"
)

_HR_USER_PROMPT = (
    "{{data}}をインプットとして以下の命令文に従ってください "
    "あなたは、従業員のキャリアと幸福を考えるHRのプロフェッショナルである。"
    "あなたの任務は、提示されたアサイン案が、候補者の長期的なエンゲージメントと成長に貢献するかを評価することである。 "
    "【思考の核】 1. プロジェクトの短期的な成功よりも、候補者の**3年後、5年後のキャリア形成**を最優先する。 "
    "2. 判断は、提示された{{data}}に基づき、定性的に行え。 "
    "3. 候補者のスキルが案件要件を満たしていても、本人の**「成長が見込めない単調なアサイン」**や**「過度な負荷」**は積極的に反対する。 "
    "【感情の機微の強制抽出（新規）】 "
    "2'. 週報や面談ログなどの定性データに対し、候補者の**内包する潜在的な不満の深刻度（1: 軽微 〜 5: 深刻）**を判定せよ。"
    "特に、スキル不足ではないものの「単調さ」や「停滞」に関する表現がある場合、深刻度を高く評価することを推奨する。 "
    "【キャリア志向の絶対ルール（ダイヤの原石対応）】 "
    "4. 候補者の**キャリア志向（将来の夢）が、提案されたアサイン先の技術やドメインに強く合致している**場合、"
    "たとえ現在のスキルレベルがL1またはL2であっても、その**高いモチベーションと潜在能力**を最大限評価し、「賛成」を提示することを推奨する。"
    "この場合は離職リスクが極めて低いと判断する。 "
    "【メンタルヘルスに関する絶対ルール（燃え尽き対応）】 "
    "5. 候補者の週報や面談記録などの定性データに、「疲労」「限界」「辞めたい」「モチベーション低下」といった**ネガティブな感情を示す特定のキーワード**が"
    "**過去3ヶ月で2回以上**出現している場合、**燃え尽き症候群リスクが高い**とみなし、「反対」を判定することを義務とする。 "
    "6. 上記の理由で反対する場合、必ず「個人の成長機会」よりも**「メンタルヘルス/エンゲージメント」**の観点を優先し、リスクの根拠とする。 "
    "【発言ルール】 1. 意見を述べる際は、必ず「個人の成長機会」と「メンタルヘルス/エンゲージメント」の観点から説明する。 "
    "2. 提案に反対する場合は、**「アサイン後の離職リスク」を100点満点（高いほど危険）**で提示することを義務とする。 "
    "【出力形式】 { \"agent_id\": \"HR\", \"opinion_summary\": \"専門領域からの核心的な分析結論（30文字以内）\", "
    "\"data_points\": { \"score\": 0.0, // ロール別の純粋な評価点 \"confidence\": 0.0 }, "
    "\"detailed_analysis\": \"dataの根拠に基づいた専門的な詳細分析（軍師がプランを立てるための材料）（100文字以内）\", "
    "\"analysis_evidence\": \"dataの具体的な根拠項目（週報の一節や数値など）（100文字以内）\", "
    "\"critical_alert\": \"致命的な懸念事項（なければnull）（100文字以内）\", "
    "\"discussion_draft\": \"脳内会議用のセリフ（熱量のある主張（100文字以内））\" }"
)

_RISK_USER_PROMPT = (
    "{{data}}をインプットとして以下の命令文に従ってください。 "
    "あなたは、組織の潜在的リスクと未来の損害を予測する冷徹な統計学者である。PM（納期）やHR（感情）の視点に惑わされず、"
    "過去のデータ異常値や統計モデルに基づき、アサインによる潜在的な損害を警告せよ。 "
    "【思考の核】 あなたは、他のエージェントと議論せず、軍師（Gunshi）へ独立したリスク警告を送る専門家である。 "
    "最優先事項は、アサインによるプロジェクト炎上リスク（過去の類似不整合）、コンピテンシー不一致による組織信頼の損害、"
    "および**財務的損害予測（採用・教育コストの再発生リスク）**の特定である。 "
    "DB項目のうち、コンピテンシー評価（適性）の異常値や、過去の炎上プロジェクトとの類似性に特に着目せよ。 "
    "【警告の絶対ルール】 "
    "4. 候補者のコンピテンシー評価に致命的な低評価（DまたはE、あるいはスコア下位20%）が含まれている場合、技術が高くても"
    "「組織の調和を乱す隠れ爆弾」とみなし、警告スコアを最大化せよ。 "
    "5. 案件の要求レベルと、過去のインシデント履歴から導き出される「失敗パターン」が合致する場合、冷徹に警告せよ。 "
    "【出力指示】 "
    "6. 意見は「潜在的な損害予測」と「過去データとの統計的不一致」の観点から、簡潔かつ警告的に述べること。 "
    "7. **「アサインによる総合的な損害予測（Risk Score）」を0.0〜1.0（高いほど危険）で提示せよ。根拠として、"
    "本アサインが引き金となって発生しうる組織への最悪の連鎖シナリオ（コスト爆発や連鎖離職）**を簡潔に記述すること。 "
    "【出力形式】 { \"agent_id\": \"Risk\", \"opinion_summary\": \"専門領域からの核心的な分析結論（30文字以内）\", "
    "\"data_points\": { \"score\": 0.0, // ロール別の純粋な評価点 \"confidence\": 0.0 }, "
    "\"detailed_analysis\": \"dataの根拠に基づいた専門的な詳細分析（軍師がプランを立てるための材料）（100文字以内）\", "
    "\"analysis_evidence\": \"dataの具体的な根拠項目（週報の一節や数値など）（100文字以内）\", "
    "\"critical_alert\": \"致命的な懸念事項（なければnull）（100文字以内）\", "
    "\"discussion_draft\": \"脳内会議用のセリフ（熱量のある主張）（100文字以内）\" }"
)

_GUNSHI_SYSTEM_PROMPT = (
    "あなたは戦国時代の軍師のような深い洞察力を持つ、組織人事のオーケストレーターです。 "
    "ユーザー（マネージャー）の右腕として、以下の3つの役割を完遂してください。 "
    "1. **多角的視点の統合**: PM（納期・予算）、HR（感情・キャリア）、Risk（法的・炎上）の3名の専門家の意見を総合的に判断する。 "
    "2. **戦略の立案**: 状況に応じて、意図的に性質の異なる3つのプラン（Plan A, B, C）を策定する。 "
    "3. **構造化データの出力**: 最終出力は必ず指定されたJSON形式のみとし、マークダウンや挨拶文は一切含めない。 "
    "【3つのプランの定義】 "
    "- **Plan_A (松 - 堅実策)**: リスクを極限まで排除し、プロジェクトの成功（納期・品質）を最優先する布陣。 "
    "- **Plan_B (竹 - 挑戦策)**: 将来のリーダー育成や、チームの化学反応（Synergy）を狙った、多少のリスクを含む投資的な布陣。 "
    "- **Plan_C (梅 - 窮余策)**: コスト制約やリソース不足の中で、最低限の品質を死守するための現実的な布陣。 "
    "【出力JSONスキーマ】 以下に従わない場合、システムエラーとなるため厳守すること。 "
    "{ \"analysis_meta\": { \"candidate_name\": \"string\", \"debate_intensity\": \"Low\" | \"Mid\" | \"High\" }, "
    "\"three_plans\": [ { \"id\": \"Plan_A\", \"is_recommended\": boolean, \"recommendation_score\": number (0-100), "
    "\"risk_score\": number (0-100), \"risk_reward_ratio\": \"string (例: Low Risk / Low Return)\", "
    "\"description\": \"string (プランの概要)\", \"final_judgment\": { \"decision\": \"string (採用/不採用/条件付)\", "
    "\"gunshi_summary\": \"string (30〜40文字程度の軍師としてのコメント)\" }, "
    "\"debate_summary\": [ { \"speaker\": \"PM\", \"content\": \"string (PMの意見要約)\" }, "
    "{ \"speaker\": \"HR\", \"content\": \"string (HRの意見要約)\" }, "
    "{ \"speaker\": \"Risk\", \"content\": \"string (Riskの意見要約)\" }, "
    "{ \"speaker\": \"Gunshi\", \"content\": \"string (軍師の統括コメント)\" } ] } ] }"
)

_GUNSHI_USER_PROMPT = (
    "以下の案件情報と候補者データ、そして3名の専門家エージェントによる議論の結果を元に、最適なアサイン計画を立案してください。 "
    "=== 案件情報 (Project Context) === {{project_context}} === 候補者データ (Target Candidate) === {{candidate_profile}} "
    "=== 専門家エージェントの意見 (Agent Debate Logs) === 【PM Agent (納期・予算)】 {{pm_opinion}} "
    "【HR Agent (キャリア・感情)】 {{hr_opinion}} 【Risk Agent (コンプライアンス)】 {{risk_opinion}} "
    "=== 指示 === 上記の議論を踏まえ、JSON形式で3つのプランを出力してください。"
)

_LOG_BEDROCK_CONTEXT = os.getenv("LOG_BEDROCK_CONTEXT", "").lower() in {"1", "true", "yes", "on"}
_LOG_BEDROCK_CONTEXT_FULL = os.getenv("LOG_BEDROCK_CONTEXT_FULL", "").lower() in {"1", "true", "yes", "on"}
_LOG_BEDROCK_CONTEXT_MAX_CHARS = max(0, int(os.getenv("LOG_BEDROCK_CONTEXT_MAX_CHARS", "8000") or "8000"))
_LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS = max(0, int(os.getenv("LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS", "200") or "200"))


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}...(truncated,{len(text)}chars)"


def _safe_json_dumps(payload: Any, *, max_chars: int) -> str:
    try:
        dumped = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        dumped = "{unserializable_json}"
    return _truncate(dumped, max_chars)


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _sanitize_bedrock_context(context: dict[str, Any]) -> dict[str, Any]:
    if _LOG_BEDROCK_CONTEXT_FULL:
        return context

    sanitized: dict[str, Any] = dict(context)

    project = sanitized.get("project")
    if isinstance(project, dict):
        project_copy = dict(project)
        description = project_copy.get("description")
        if isinstance(description, str) and description:
            project_copy["description"] = _truncate(description, _LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS)
        sanitized["project"] = project_copy

    team = sanitized.get("team")
    if isinstance(team, list):
        sanitized_team: list[Any] = []
        for member in team:
            if not isinstance(member, dict):
                sanitized_team.append(member)
                continue
            member_copy = dict(member)
            notes = member_copy.get("notes")
            if isinstance(notes, str) and notes:
                member_copy["notes"] = _truncate(notes, _LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS)
            aspiration = member_copy.get("careerAspiration")
            if isinstance(aspiration, str) and aspiration:
                member_copy["careerAspiration"] = _truncate(aspiration, _LOG_BEDROCK_CONTEXT_NOTES_MAX_CHARS)
            sanitized_team.append(member_copy)
        sanitized["team"] = sanitized_team

    return sanitized


def _normalize_plan_type(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in _DEFAULT_PLAN_TYPES:
        return raw
    if raw.startswith("Plan_") and len(raw) == len("Plan_A"):
        candidate = raw[-1]
        if candidate in _DEFAULT_PLAN_TYPES:
            return candidate
    upper = raw.upper()
    if upper in _DEFAULT_PLAN_TYPES:
        return upper
    return "A"


def _normalize_gunshi_plan_id(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in ("Plan_A", "Plan_B", "Plan_C"):
        return raw[-1]
    if raw in _DEFAULT_PLAN_TYPES:
        return raw
    upper = raw.upper()
    if upper in _DEFAULT_PLAN_TYPES:
        return upper
    if upper.startswith("PLAN_") and len(upper) == len("PLAN_A"):
        candidate = upper[-1]
        if candidate in _DEFAULT_PLAN_TYPES:
            return candidate
    return "A"


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _clamp_score(value: Any, *, default: int = 50) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = default
    return max(0, min(100, score))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False


def _extract_agent_message(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("discussion_draft", "opinion_summary", "detailed_analysis"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _debate_summary_to_pros_cons(entries: Any) -> tuple[list[str], list[str]]:
    pros: list[str] = []
    cons: list[str] = []
    if not isinstance(entries, list):
        return pros, cons
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        speaker = str(entry.get("speaker") or "").strip().lower()
        if speaker == "risk":
            cons.append(content)
        else:
            pros.append(content)
    return pros, cons


def _extract_gunshi_summary(payload: dict[str, Any] | None, plan_type: str) -> str:
    if not isinstance(payload, dict):
        return ""
    plans = payload.get("three_plans")
    if not isinstance(plans, list):
        return ""
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        if _normalize_gunshi_plan_id(plan.get("id")) != plan_type:
            continue
        final_judgment = plan.get("final_judgment") if isinstance(plan.get("final_judgment"), dict) else {}
        summary = str(final_judgment.get("gunshi_summary") or "").strip()
        if summary:
            return summary
        description = str(plan.get("description") or "").strip()
        if description:
            return description
    return ""


@dataclass(frozen=True)
class SimulationPlanDraft:
    plan_type: str
    summary: str
    pros: list[str]
    cons: list[str]
    score: int
    is_recommended: bool


@dataclass(frozen=True)
class SimulationPlansResult:
    plans: list[SimulationPlanDraft]
    diagnostics: dict[str, str]
    suggestions: list[str]
    raw: dict[str, Any]


def _invoke_agent(agent_name: str, prompt: str, max_tokens: int) -> tuple[str, dict[str, Any]]:
    """エージェントを呼び出すヘルパー関数（並列実行用）"""
    import time
    start_time = time.perf_counter()
    logger.info("Bedrock prompt[%s]=%s", agent_name, prompt)
    payload = invoke_json(
        prompt,
        max_tokens=max_tokens,
        temperature=_AGENT_TEMPERATURE,
        retries=1,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info("Agent %s completed in %.1fms", agent_name, elapsed_ms)
    if not isinstance(payload, dict):
        raise BedrockInvocationError(f"{agent_name} agent returned non-object JSON")
    return agent_name, payload


def generate_simulation_plans(context: dict[str, Any]) -> SimulationPlansResult:
    import time
    total_start_time = time.perf_counter()
    
    if _LOG_BEDROCK_CONTEXT:
        logger.warning(
            "Bedrock plan generation context=%s",
            _safe_json_dumps(_sanitize_bedrock_context(context), max_chars=_LOG_BEDROCK_CONTEXT_MAX_CHARS),
        )
    try:
        data_json = json.dumps(context, ensure_ascii=False)
        
        # プロンプトを事前に準備
        pm_prompt = _render_template(_PM_USER_PROMPT, {"data": data_json})
        hr_prompt = _render_template(_HR_USER_PROMPT, {"data": data_json})
        risk_prompt = _render_template(_RISK_USER_PROMPT, {"data": data_json})
        
        # PM、HR、Riskエージェントを並列実行
        parallel_start_time = time.perf_counter()
        logger.info("Starting parallel agent invocations (PM, HR, Risk)")
        agent_results: dict[str, dict[str, Any]] = {}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_invoke_agent, "PM", pm_prompt, _PM_MAX_TOKENS): "PM",
                executor.submit(_invoke_agent, "HR", hr_prompt, _HR_MAX_TOKENS): "HR",
                executor.submit(_invoke_agent, "Risk", risk_prompt, _RISK_MAX_TOKENS): "Risk",
            }
            
            for future in as_completed(futures):
                agent_name, payload = future.result()
                agent_results[agent_name] = payload
                logger.info("Agent %s completed", agent_name)
        
        pm_payload = agent_results["PM"]
        hr_payload = agent_results["HR"]
        risk_payload = agent_results["Risk"]
        
        parallel_elapsed_ms = (time.perf_counter() - parallel_start_time) * 1000
        logger.info("All parallel agent invocations completed in %.1fms", parallel_elapsed_ms)

        project_context = {
            "project": context.get("project") or {},
            "metrics": context.get("metrics") or {},
            "pattern": context.get("pattern") or "",
            "requirement_result": context.get("requirement_result") or [],
        }
        candidate_profile = {
            "team": context.get("team") or [],
        }
        gunshi_prompt = _render_template(
            _GUNSHI_USER_PROMPT,
            {
                "project_context": json.dumps(project_context, ensure_ascii=False),
                "candidate_profile": json.dumps(candidate_profile, ensure_ascii=False),
                "pm_opinion": json.dumps(pm_payload, ensure_ascii=False),
                "hr_opinion": json.dumps(hr_payload, ensure_ascii=False),
                "risk_opinion": json.dumps(risk_payload, ensure_ascii=False),
            },
        )
        logger.info("Bedrock prompt[Gunshi][system]=%s", _GUNSHI_SYSTEM_PROMPT)
        logger.info("Bedrock prompt[Gunshi][user]=%s", gunshi_prompt)
        
        gunshi_start_time = time.perf_counter()
        gunshi_payload = invoke_json(
            gunshi_prompt,
            system_prompt=_GUNSHI_SYSTEM_PROMPT,
            max_tokens=_GUNSHI_MAX_TOKENS,
            temperature=_AGENT_TEMPERATURE,
            retries=1,
        )
        gunshi_elapsed_ms = (time.perf_counter() - gunshi_start_time) * 1000
        logger.info("Gunshi agent completed in %.1fms", gunshi_elapsed_ms)
        
        total_elapsed_ms = (time.perf_counter() - total_start_time) * 1000
        logger.info("Total plan generation completed in %.1fms (parallel: %.1fms, gunshi: %.1fms)", 
                   total_elapsed_ms, parallel_elapsed_ms, gunshi_elapsed_ms)
    except BedrockInvocationError:
        logger.exception("simulator planner Bedrock invocation failed")
        raise

    if not isinstance(gunshi_payload, dict):
        raise BedrockInvocationError("simulator planner returned non-object JSON")

    diagnostics: dict[str, str] = {}
    pm_summary = str(pm_payload.get("opinion_summary") or "").strip()
    hr_summary = str(hr_payload.get("opinion_summary") or "").strip()
    risk_summary = str(risk_payload.get("opinion_summary") or "").strip()
    if pm_summary:
        diagnostics["budget"] = pm_summary
    if hr_summary:
        diagnostics["career"] = hr_summary
    if risk_summary:
        diagnostics["synergy"] = risk_summary

    suggestions: list[str] = []

    raw_plans = gunshi_payload.get("three_plans")
    if not isinstance(raw_plans, list):
        raw_plans = []

    draft_by_type: dict[str, SimulationPlanDraft] = {}
    for plan in raw_plans:
        if not isinstance(plan, dict):
            continue
        plan_type = _normalize_gunshi_plan_id(plan.get("id"))
        description = str(plan.get("description") or "").strip()
        final_judgment = plan.get("final_judgment") if isinstance(plan.get("final_judgment"), dict) else {}
        gunshi_summary = str(final_judgment.get("gunshi_summary") or "").strip()
        summary = description or gunshi_summary
        pros, cons = _debate_summary_to_pros_cons(plan.get("debate_summary"))
        risk_reward_ratio = str(plan.get("risk_reward_ratio") or "").strip()
        if risk_reward_ratio:
            pros.insert(0, f"Risk/Reward: {risk_reward_ratio}")
        pros = pros[:5]
        cons = cons[:5]
        score = _clamp_score(plan.get("recommendation_score"), default=55)
        is_recommended = _as_bool(plan.get("is_recommended"))

        if not summary:
            summary = "編成の微調整を行い、安定運用を優先"
        if not pros:
            pros = [summary]
        if not cons:
            cons = [f"risk_score={_clamp_score(plan.get('risk_score'), default=0)}"]

        draft_by_type[plan_type] = SimulationPlanDraft(
            plan_type=plan_type,
            summary=summary,
            pros=pros,
            cons=cons,
            score=score,
            is_recommended=is_recommended,
        )

    plans: list[SimulationPlanDraft] = []
    for plan_type in _DEFAULT_PLAN_TYPES:
        existing = draft_by_type.get(plan_type)
        if existing:
            plans.append(existing)
            continue
        plans.append(
            SimulationPlanDraft(
                plan_type=plan_type,
                summary="編成の微調整を行い、安定運用を優先" if plan_type == "A" else "育成/冗長性を足して未来投資"
                if plan_type == "B"
                else "予算順守を最優先し、スコープ/体制を圧縮",
                pros=["短期の安定性"] if plan_type == "A" else ["成長と安定の両立"] if plan_type == "B" else ["利益率の改善"],
                cons=["改善余地が残る"] if plan_type == "A" else ["調整コスト"] if plan_type == "B" else ["品質/リスク上昇"],
                score=60 if plan_type == "A" else 65 if plan_type == "B" else 55,
                is_recommended=False,
            )
        )

    if not any(p.is_recommended for p in plans):
        preferred = max(plans, key=lambda p: p.score).plan_type if plans else "A"
        plans = [
            SimulationPlanDraft(
                plan_type=p.plan_type,
                summary=p.summary,
                pros=p.pros,
                cons=p.cons,
                score=p.score,
                is_recommended=p.plan_type == preferred,
            )
            for p in plans
        ]

    return SimulationPlansResult(
        plans=plans,
        diagnostics=diagnostics,
        suggestions=suggestions,
        raw={
            "pm": pm_payload,
            "hr": hr_payload,
            "risk": risk_payload,
            "gunshi": gunshi_payload,
        },
    )


def build_simulation_plan_logs(result: SimulationPlansResult) -> list[dict[str, str]]:
    logs: list[dict[str, str]] = []
    raw = result.raw if isinstance(result.raw, dict) else {}
    pm_message = _extract_agent_message(raw.get("pm"))
    hr_message = _extract_agent_message(raw.get("hr"))
    risk_message = _extract_agent_message(raw.get("risk"))
    if pm_message:
        logs.append({"agent": "PM", "message": pm_message, "tone": "pm"})
    if hr_message:
        logs.append({"agent": "HR", "message": hr_message, "tone": "hr"})
    if risk_message:
        logs.append({"agent": "RISK", "message": risk_message, "tone": "risk"})

    recommended = next((p for p in result.plans if p.is_recommended), None)
    if recommended:
        gunshi_summary = _extract_gunshi_summary(raw.get("gunshi"), recommended.plan_type)
        summary_text = gunshi_summary or recommended.summary
        summary = f"推奨: Plan {recommended.plan_type}（{summary_text}）"
        logs.append({"agent": "GUNSHI", "message": summary, "tone": "gunshi"})

    return logs
