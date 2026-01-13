from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnalysisMeta(BaseModel):
    candidate_name: str = Field(min_length=1)
    debate_intensity: Literal["Low", "Mid", "High"]


class FinalJudgment(BaseModel):
    decision: Literal["採用", "不採用", "条件付"]
    total_score: int = Field(ge=0, le=100)
    gunshi_summary: str = Field(min_length=1)


class DebateSummaryEntry(BaseModel):
    speaker: Literal["PM", "HR", "Risk", "Gunshi"]
    content: str = Field(min_length=1)


class Plan(BaseModel):
    id: Literal["Plan_A", "Plan_B", "Plan_C"]
    is_recommended: bool
    recommendation_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    risk_reward_ratio: str = Field(min_length=1)
    description: str = Field(min_length=1)
    predicted_future_impact: str = Field(min_length=1)
    final_judgment: FinalJudgment
    debate_summary: list[DebateSummaryEntry]


class AIResponse(BaseModel):
    analysis_meta: AnalysisMeta
    three_plans: list[Plan]
