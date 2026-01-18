export type Vote = 'ok' | 'ng';

export interface Project {
  id: string;
  name: string;
  budget: number;
  requiredSkills?: string[];
  status?: string | null;
  difficulty?: string | null;
  description?: string | null;
}

export interface MemberAnalysis {
  patternId: string;
  patternName?: string | null;
  pmRiskScore?: number | null;
  hrRiskScore?: number | null;
  riskRiskScore?: number | null;
  finalDecision?: string | null;
}

export interface Member {
  id: string;
  name: string;
  cost: number;
  availability: number;
  skills: string[];
  notes: string;
  role?: string | null;
  skillLevel?: number | null;
  careerAspiration?: string | null;
  analysis?: MemberAnalysis | null;
}

export interface SimulationRequest {
  projectId: string;
  memberIds: string[];
}

export interface RequirementResult {
  name: string;
  fulfilled: boolean;
}

export interface SimulationEvaluation {
  id: string;
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
  requirementResult: RequirementResult[];
}

export interface SimulationPlan {
  id: string;
  simulationId: string;
  planType: 'A' | 'B' | 'C';
  summary: string;
  prosCons: { pros: string[]; cons: string[] };
  score: number;
  recommended: boolean;
}

export type PlanStreamTone = 'pm' | 'hr' | 'risk' | 'gunshi';

export interface PlanStreamProgress {
  phase: string;
  message: string;
  progress: number;
}

export interface PlanStreamLog {
  agent: string;
  message: string;
  tone: PlanStreamTone;
}

export interface PlanStreamComplete {
  plans: SimulationPlan[];
}

export interface SimulationResult extends SimulationEvaluation {
  plans: SimulationPlan[];
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

export interface DashboardKpi {
  label: string;
  value: number;
  suffix: string;
  delta: string;
  color: string;
  deltaColor: string;
}

export interface DashboardAlert {
  id: string;
  title: string;
  subtitle: string;
  risk: number;
  severity: string;
  status: string;
  projectId?: string | null;
}

export interface DashboardProposal {
  id: number;
  projectId: string;
  planType: string;
  description: string;
  predictedFutureImpact?: string | null;
  recommendationScore: number;
  isRecommended: boolean;
}

export interface DashboardPendingAction {
  id: number;
  proposalId: number;
  actionType: string;
  title: string;
  status: string;
}

export interface DashboardTimelineEntry {
  t: string;
  text: string;
  dot: string;
}

export interface DashboardInitialResponse {
  kpis: DashboardKpi[];
  alerts: DashboardAlert[];
  members: Member[];
  proposals: DashboardProposal[];
  pendingActions: DashboardPendingAction[];
  watchdog: DashboardTimelineEntry[];
  checkpointWaiting: boolean;
}

export interface SlackMeta {
  channel: string;
  message_ts: string;
  thread_ts?: string | null;
}

export interface ApprovalRequestResponse {
  thread_id: string;
  approval_request_id: string;
  status: string;
  action_id: number;
  slack?: SlackMeta | null;
}

export interface ApprovalDecisionResponse {
  job_id: string;
  status: string;
  thread_id: string;
  action_id: number;
}
