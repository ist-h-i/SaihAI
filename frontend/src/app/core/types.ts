export type Vote = 'ok' | 'ng';

export interface Project {
  id: string;
  name: string;
  budget: number;
  requiredSkills?: string[];
}

export interface Member {
  id: string;
  name: string;
  cost: number;
  availability: number;
  skills: string[];
  notes: string;
}

export interface SimulationRequest {
  projectId: string;
  memberIds: string[];
}

export interface SimulationResult {
  project: { id: string; name: string; budget: number };
  team: { id: string; name: string; cost: number }[];
  metrics: {
    budgetUsed: number;
    budgetPct: number;
    skillFitPct: number;
    careerFitPct: number;
    riskPct: number;
  };
  pattern: string;
  timeline: { t: string; level: 'good' | 'ok' | 'bad'; text: string }[];
  meetingLog?: {
    agent_id: 'PM' | 'HR' | 'RISK' | 'GUNSHI';
    decision: 'APPROVE' | 'CONDITIONAL_APPROVE' | 'REJECT';
    risk_score: number;
    risk_reason: string;
    message: string;
  }[];
  agents: {
    pm: { vote: Vote; note: string };
    hr: { vote: Vote; note: string };
    risk: { vote: Vote; note: string };
    gunshi: { recommend: 'A' | 'B' | 'C'; note: string };
  };
  plans: {
    id: 'A' | 'B' | 'C';
    title: string;
    pros: string[];
    cons: string[];
    recommended: boolean;
  }[];
}

export type AiDebateIntensity = 'Low' | 'Mid' | 'High';
export type AiDecision = '採用' | '不採用' | '条件付';
export type AiDebateSpeaker = 'PM' | 'HR' | 'Risk' | 'Gunshi';
export type AiPlanId = 'Plan_A' | 'Plan_B' | 'Plan_C';

export interface AiAnalysisMeta {
  candidate_name: string;
  debate_intensity: AiDebateIntensity;
}

export interface AiFinalJudgment {
  decision: AiDecision;
  total_score: number;
  gunshi_summary: string;
}

export interface AiDebateSummaryEntry {
  speaker: AiDebateSpeaker;
  content: string;
}

export interface AiPlan {
  id: AiPlanId;
  is_recommended: boolean;
  recommendation_score: number;
  risk_score: number;
  risk_reward_ratio: string;
  description: string;
  final_judgment: AiFinalJudgment;
  debate_summary: AiDebateSummaryEntry[];
}

export interface AiResponse {
  analysis_meta: AiAnalysisMeta;
  three_plans: AiPlan[];
}
