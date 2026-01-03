import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AppConfigService } from './config/app-config.service';
import { Member, Project, SimulationRequest, SimulationResult } from './types';

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

  simulate(req: SimulationRequest): Observable<SimulationResult> {
    return this.http.post<SimulationResult>(this.buildUrl('/simulate'), req);
  }

  private buildUrl(path: string): string {
    return `${this.config.apiBaseUrl}${path}`;
  }
}
