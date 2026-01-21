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

export interface ProjectAssignment {
  role?: string | null;
  allocationRate?: number | null;
}

export interface ProjectTeamMember extends Member {
  assignment?: ProjectAssignment | null;
}

export interface SimulationRequest {
  projectId: string;
  memberIds: string[];
}

export interface TeamSuggestionRequest {
  projectId: string;
  excludeMemberIds?: string[];
  minAvailability?: number;
  proposalCount?: number;
  minTeamSize?: number;
  maxTeamSize?: number;
}

export interface TeamSuggestionMember {
  id: string;
  name: string;
  role?: string | null;
  allocationPct?: number | null;
  cost?: number | null;
  availability?: number | null;
}

export interface TeamSuggestion {
  id: string;
  source: 'internal' | 'external';
  applyable: boolean;
  memberIds: string[];
  team: TeamSuggestionMember[];
  why: string;
  metrics?: SimulationEvaluation['metrics'] | null;
  isRecommended: boolean;
  missingSkills: string[];
}

export interface TeamSuggestionsResponse {
  project: { id: string; name: string; budget: number };
  minAvailability: number;
  candidateCount: number;
  suggestions: TeamSuggestion[];
}

export interface TeamSuggestionApplyRequest {
  projectId: string;
  memberIds: string[];
  minAvailability?: number;
}

export interface TeamSuggestionApplyResponse {
  draftId: string;
  projectId: string;
  memberIds: string[];
  minAvailability: number;
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

export interface PlanChatRequest {
  message: string;
  allowMock?: boolean;
}

export interface PlanChatResponse {
  plan: SimulationPlan;
  message: string;
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

export interface SavedPlanSummary {
  id: string;
  simulationId: string;
  title: string;
  projectId?: string | null;
  projectName?: string | null;
  recommendedPlan?: string | null;
  selectedPlan?: 'A' | 'B' | 'C' | null;
  contentText?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface SavedPlanDetail extends SavedPlanSummary {
  content: SimulationResult;
}

export interface SavedPlanCreateRequest {
  content: SimulationResult;
  title?: string;
  selectedPlan?: 'A' | 'B' | 'C' | null;
}

export interface SavedPlanUpdateRequest {
  title?: string;
  selectedPlan?: 'A' | 'B' | 'C' | null;
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
  category?: string | null;
  focusMemberId?: string | null;
}

export interface DashboardProposal {
  id: number;
  projectId: string;
  projectName?: string | null;
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

export interface ProjectTeamResponse {
  projectId: string;
  members: ProjectTeamMember[];
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

export interface DemoStartResponse {
  alertId: string;
  status: string;
  slack?: SlackMeta | null;
}

export interface HistoryEvent {
  event_type: string;
  actor?: string | null;
  correlation_id?: string | null;
  detail?: Record<string, unknown>;
  created_at?: string | null;
}

export interface HistoryEntry {
  thread_id: string;
  action_id: number;
  status?: string | null;
  summary?: string | null;
  project_id?: string | null;
  severity?: string | null;
  updated_at?: string | null;
  events: HistoryEvent[];
}
