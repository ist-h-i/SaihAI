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
  metrics: { budgetUsed: number; budgetPct: number; skillFitPct: number; careerFitPct: number; riskPct: number };
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
  plans: { id: 'A' | 'B' | 'C'; title: string; pros: string[]; cons: string[]; recommended: boolean }[];
}
