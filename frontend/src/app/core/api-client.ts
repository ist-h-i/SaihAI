import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfigService } from './config/app-config.service';
import {
  ApprovalDecisionResponse,
  ApprovalRequestResponse,
  DashboardInitialResponse,
  Member,
  ProjectTeamResponse,
  Project,
  SimulationEvaluation,
  SimulationPlan,
  SimulationRequest,
} from './types';

@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);
  private readonly config = inject(AppConfigService);

  getProjects(): Observable<Project[]> {
    return this.http.get<Project[]>(this.buildUrl('/projects'));
  }

  getMembers(): Observable<Member[]> {
    return this.http.get<Member[]>(this.buildUrl('/members'));
  }

  getProjectTeam(projectId: string): Observable<ProjectTeamResponse> {
    return this.http.get<ProjectTeamResponse>(this.buildUrl(`/projects/${projectId}/team`));
  }

  getMemberDetail(memberId: string): Observable<Member> {
    return this.http.get<Member>(this.buildUrl(`/members/${memberId}`));
  }

  getDashboardInitial(): Observable<DashboardInitialResponse> {
    return this.http.get<DashboardInitialResponse>(this.buildUrl('/dashboard/initial'));
  }

  evaluateSimulation(req: SimulationRequest): Observable<SimulationEvaluation> {
    return this.http.post<SimulationEvaluation>(this.buildUrl('/simulations/evaluate'), req);
  }

  generatePlans(simulationId: string): Observable<SimulationPlan[]> {
    return this.http.post<SimulationPlan[]>(
      this.buildUrl(`/simulations/${simulationId}/plans/generate`),
      {}
    );
  }

  requestNemawashiApproval(actionId: number): Observable<ApprovalRequestResponse> {
    return this.http.post<ApprovalRequestResponse>(
      this.buildUrl(`/nemawashi/${actionId}/request-approval`),
      {}
    );
  }

  approveApproval(approvalId: string): Observable<ApprovalDecisionResponse> {
    return this.http.post<ApprovalDecisionResponse>(
      this.buildUrl(`/approvals/${encodeURIComponent(approvalId)}/approve`),
      {}
    );
  }

  rejectApproval(approvalId: string): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(
      this.buildUrl(`/approvals/${encodeURIComponent(approvalId)}/reject`),
      {}
    );
  }

  private buildUrl(path: string): string {
    return `${this.config.apiBaseUrl}${path}`;
  }
}
