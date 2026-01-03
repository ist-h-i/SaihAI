import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfigService } from './config/app-config.service';
import {
  DashboardInitialResponse,
  Member,
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

  private buildUrl(path: string): string {
    return `${this.config.apiBaseUrl}${path}`;
  }
}
